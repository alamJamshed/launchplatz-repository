import hashlib
import json
import shlex
import socket
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from projects.git_services import RemoteGitService

from .models import ReconciliationEvent, Route, ServerRoutingLease


OVERRIDE_FILENAME = '.launchplatz-routing.yml'
PROXY_NETWORK = 'launchplatz-proxy'


class RoutingOperationError(Exception):
    def __init__(self, category, message, status_code=502):
        super().__init__(message)
        self.category = category
        self.message = message
        self.status_code = status_code


def route_names(route):
    stem = f'launchplatz-p{route.domain.project_id}-r{route.pk}'
    return {'router': stem, 'service': stem}


def render_compose_override(route):
    names = route_names(route)
    hostname = route.domain.normalized_hostname
    labels = {
        'traefik.enable': 'true',
        'traefik.docker.network': PROXY_NETWORK,
        f'traefik.http.routers.{names["router"]}.entrypoints': 'web',
        f'traefik.http.routers.{names["router"]}.rule': f'Host(`{hostname}`)',
        f'traefik.http.routers.{names["router"]}.service': names['service'],
        f'traefik.http.services.{names["service"]}.loadbalancer.server.port': str(
            route.internal_port
        ),
    }
    if route.tls_enabled:
        labels.update({
            f'traefik.http.routers.{names["router"]}-tls.entrypoints': 'websecure',
            f'traefik.http.routers.{names["router"]}-tls.rule': f'Host(`{hostname}`)',
            f'traefik.http.routers.{names["router"]}-tls.service': names['service'],
            f'traefik.http.routers.{names["router"]}-tls.tls': 'true',
            f'traefik.http.routers.{names["router"]}-tls.tls.certresolver': 'pebble',
        })
    label_lines = '\n'.join(
        f'        {json.dumps(key)}: {json.dumps(value)}'
        for key, value in sorted(labels.items())
    )
    return (
        'services:\n'
        f'  {route.service_name}:\n'
        '    labels:\n'
        f'{label_lines}\n'
        '    networks:\n'
        f'      - {PROXY_NETWORK}\n'
        'networks:\n'
        f'  {PROXY_NETWORK}:\n'
        '    external: true\n'
    )


def override_revision(content):
    return hashlib.sha256(content.encode()).hexdigest()


def acquire_route_lease(route_id, owner, seconds=180):
    now = timezone.now()
    with transaction.atomic():
        route = Route.objects.select_related('domain__project').get(pk=route_id)
        lease, _ = ServerRoutingLease.objects.select_for_update().get_or_create(
            server_id=route.domain.project.server_id
        )
        if (
            lease.owner
            and lease.owner != owner
            and lease.expires_at
            and lease.expires_at > now
        ):
            return None
        lease.owner = owner
        lease.expires_at = now + timedelta(seconds=seconds)
        lease.save(update_fields=['owner', 'expires_at'])
        route.lease_owner = owner
        route.lease_expires_at = now + timedelta(seconds=seconds)
        route.save(update_fields=['lease_owner', 'lease_expires_at'])
        return route


class RemoteRoutingService(RemoteGitService):
    def __init__(self, route):
        super().__init__(route.domain.project)
        self.route = route

    @property
    def override_path(self):
        return f'{self.workspace}/{OVERRIDE_FILENAME}'

    def _compose(self):
        compose_file = f'{self.workspace}/{self.project.docker_compose_path}'
        return (
            f'docker compose -f {shlex.quote(compose_file)} '
            f'-f {shlex.quote(self.override_path)}'
        )

    def inspect_services(self):
        output = self._run(
            f'docker compose -f '
            f'{shlex.quote(self.workspace + "/" + self.project.docker_compose_path)} '
            'config --services'
        ).stdout.splitlines()
        if self.route.service_name not in output:
            raise RoutingOperationError(
                'service_missing',
                'The selected service is not declared by the Compose project.',
                409,
            )

    def ensure_proxy(self):
        directory = f'{self.home}/.launchplatz/proxy'
        destination = f'{directory}/compose.yml'
        temporary = f'{destination}.tmp-{uuid.uuid4().hex}'
        self._run(f'mkdir -p {shlex.quote(directory)} && chmod 700 {shlex.quote(directory)}')
        content = render_proxy_stack()
        try:
            with self.sftp.file(temporary, 'wb') as target:
                target.write(content)
                target.flush()
            self.sftp.chmod(temporary, 0o600)
            self.sftp.posix_rename(temporary, destination)
        except Exception as exc:
            raise RoutingOperationError(
                'proxy_install_failed', 'Could not install the Traefik stack.'
            ) from exc
        self._run(
            f'docker network inspect {PROXY_NETWORK} >/dev/null 2>&1 || '
            f'docker network create {PROXY_NETWORK}'
        )
        result = self._run_raw(
            f'docker compose -f {shlex.quote(destination)} up -d'
        )
        if result.exit_code:
            raise RoutingOperationError(
                'proxy_install_failed', 'Could not start the Traefik stack.'
            )

    def write_override(self, content):
        temporary = f'{self.override_path}.tmp-{uuid.uuid4().hex}'
        try:
            with self.sftp.file(temporary, 'wb') as target:
                target.write(content)
                target.flush()
            self.sftp.chmod(temporary, 0o600)
            self.sftp.posix_rename(temporary, self.override_path)
        except Exception as exc:
            try:
                self.sftp.remove(temporary)
            except Exception:
                pass
            raise RoutingOperationError(
                'override_write_failed',
                'Could not install the managed routing configuration.',
            ) from exc

    def reconcile(self):
        self._require_clone()
        self.inspect_services()
        content = render_compose_override(self.route)
        revision = override_revision(content)
        self.ensure_proxy()
        self.write_override(content)
        validation = self._run_raw(f'{self._compose()} config --quiet')
        if validation.exit_code:
            raise RoutingOperationError(
                'compose_invalid', 'The generated routing configuration is invalid.'
            )
        self._run(
            f'{self._compose()} up -d --no-deps --force-recreate '
            f'{shlex.quote(self.route.service_name)}'
        )
        self._run('docker inspect --format "{{.State.Running}}" launchplatz-traefik')
        probe = self._run_raw(
            f'curl --fail --silent --show-error --max-time 10 '
            f'-H {shlex.quote("Host: " + self.route.domain.normalized_hostname)} '
            'http://127.0.0.1/'
        )
        if probe.exit_code:
            raise RoutingOperationError(
                'http_unhealthy',
                'Traefik configured the route, but its HTTP health probe failed.',
            )
        return revision

    def disable(self):
        try:
            self.sftp.remove(self.override_path)
        except OSError:
            pass
        self._run_raw(
            f'docker compose -f '
            f'{shlex.quote(self.workspace + "/" + self.project.docker_compose_path)} '
            f'up -d --no-deps --force-recreate {shlex.quote(self.route.service_name)}'
        )


def reconcile_route(route_id, owner=None):
    owner = owner or uuid.uuid4().hex
    route = acquire_route_lease(route_id, owner)
    if route is None:
        raise RoutingOperationError(
            'reconciliation_locked', 'Another reconciliation is already running.', 409
        )
    server_id = route.domain.project.server_id
    status = Route.ObservedStatus.FAILED
    error = ''
    revision = ''
    try:
        route = Route.objects.select_related(
            'domain__project__server'
        ).get(pk=route_id)
        if (
            not route.desired_enabled
            or route.domain.project.is_archived
            or not route.is_active
            or route.is_deleted
        ):
            with RemoteRoutingService(route) as remote:
                remote.disable()
            status = Route.ObservedStatus.DISABLED
        else:
            with RemoteRoutingService(route) as remote:
                revision = remote.reconcile()
            status = Route.ObservedStatus.HEALTHY
        return status
    except RoutingOperationError as exc:
        error = exc.message[:500]
        raise
    except Exception as exc:
        error = 'Routing reconciliation failed.'
        raise RoutingOperationError('reconciliation_failed', error) from exc
    finally:
        Route.objects.filter(pk=route_id, lease_owner=owner).update(
            observed_status=status,
            configuration_revision=revision,
            last_reconciled_at=timezone.now(),
            last_error=error,
            lease_owner='',
            lease_expires_at=None,
        )
        ServerRoutingLease.objects.filter(
            server_id=server_id, owner=owner,
        ).update(owner='', expires_at=None)
        ReconciliationEvent.objects.create(
            route_id=route_id, status=status, revision=revision, error=error
        )


def verify_domain_dns(domain):
    expected = str(domain.project.server.ip_address)
    try:
        addresses = sorted({
            item[4][0] for item in socket.getaddrinfo(
                domain.normalized_hostname, None, type=socket.SOCK_STREAM
            )
        })
        matches = expected in addresses
        domain.resolved_addresses = addresses
        domain.dns_error = (
            '' if matches else f'DNS must resolve to the server address {expected}.'
        )
        domain.consecutive_dns_successes = (
            domain.consecutive_dns_successes + 1 if matches else 0
        )
        domain.dns_status = (
            domain.DNSStatus.VERIFIED
            if matches and domain.consecutive_dns_successes >= 2
            else domain.DNSStatus.PENDING if matches
            else domain.DNSStatus.FAILED
        )
    except socket.gaierror:
        domain.resolved_addresses = []
        domain.consecutive_dns_successes = 0
        domain.dns_status = domain.DNSStatus.FAILED
        domain.dns_error = 'The hostname could not be resolved by the internal resolver.'
    domain.dns_last_checked_at = timezone.now()
    domain.save(update_fields=[
        'resolved_addresses', 'consecutive_dns_successes', 'dns_status',
        'dns_error', 'dns_last_checked_at', 'updated_at',
    ])
    return domain


PROXY_STACK = """services:
  socket-proxy:
    image: tecnativa/docker-socket-proxy:0.3.0
    container_name: launchplatz-socket-proxy
    restart: unless-stopped
    environment:
      CONTAINERS: 1
      EVENTS: 1
      NETWORKS: 1
      PING: 1
      VERSION: 1
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks: [socket]
  traefik:
    image: traefik:v3.3.6
    container_name: launchplatz-traefik
    restart: unless-stopped
    depends_on: [socket-proxy]
    command:
      - --api.dashboard=false
      - --api.insecure=false
      - --ping=true
      - --log.format=json
      - --accesslog=true
      - --accesslog.format=json
      - --providers.docker.endpoint=tcp://socket-proxy:2375
      - --providers.docker.exposedbydefault=false
      - --providers.docker.network=launchplatz-proxy
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      - --certificatesresolvers.pebble.acme.email=internal-test@launchplatz.invalid
      - --certificatesresolvers.pebble.acme.storage=/acme/acme.json
      - --certificatesresolvers.pebble.acme.httpchallenge.entrypoint=web
      - --certificatesresolvers.pebble.acme.caserver=ACME_CA_SERVER
    ports:
      - 80:80
      - 443:443
    volumes:
      - acme:/acme
    networks: [socket, launchplatz-proxy]
    healthcheck:
      test: [CMD, traefik, healthcheck, --ping]
      interval: 10s
      timeout: 3s
      retries: 5
networks:
  socket:
    internal: true
  launchplatz-proxy:
    external: true
volumes:
  acme:
"""


def render_proxy_stack():
    ca_server = getattr(
        settings,
        'ROUTING_ACME_CA_SERVER',
        'https://pebble:14000/dir',
    )
    return PROXY_STACK.replace('ACME_CA_SERVER', ca_server)
