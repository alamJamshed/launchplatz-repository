import json
import shlex
import socket
from dataclasses import dataclass

import paramiko
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError

from servers.services import ServerCredentialCipher, SSHKeyParser


class ContainerOperationError(Exception):
    def __init__(self, category, message, status_code=502):
        super().__init__(message)
        self.category = category
        self.message = message
        self.status_code = status_code


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str


class RemoteContainerService:
    def __init__(self, project):
        self.project = project
        self.client = None
        self.sftp = None
        self.home = None
        self.workspace = None
        self.compose_file = None

    def __enter__(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        server = self.project.server
        try:
            key = SSHKeyParser.parse(
                ServerCredentialCipher.decrypt(server.encrypted_private_key)
            )
            timeout = getattr(settings, 'SSH_CONNECTION_TIMEOUT', 30)
            self.client.connect(
                hostname=str(server.ip_address), port=server.ssh_port,
                username=server.username, pkey=key, timeout=timeout,
                banner_timeout=timeout, auth_timeout=timeout,
                look_for_keys=False, allow_agent=False,
            )
            self.sftp = self.client.open_sftp()
            self.home = self.sftp.normalize('.')
            self.workspace = f'{self.home}/launchplatz/projects/{self.project.pk}'
            self.compose_file = f'{self.workspace}/{self.project.docker_compose_path}'
            self._require_path(
                f'{self.workspace}/.git', 'repository_not_cloned',
                'Repository has not been cloned.', directory=True,
            )
            self._require_path(
                self.compose_file, 'compose_file_missing',
                'Docker Compose file was not found.',
            )
            self._run(
                'docker compose version', 'docker_unavailable',
                'Docker Compose is not available on the VPS.',
            )
            return self
        except ContainerOperationError:
            self.__exit__(None, None, None)
            raise
        except (ValidationError, ImproperlyConfigured) as exc:
            self.__exit__(None, None, None)
            raise ContainerOperationError(
                'credential_error', 'A stored VPS credential is invalid.', 400
            ) from exc
        except paramiko.AuthenticationException as exc:
            self.__exit__(None, None, None)
            raise ContainerOperationError(
                'ssh_authentication_failed', 'VPS SSH authentication failed.'
            ) from exc
        except (socket.timeout, TimeoutError) as exc:
            self.__exit__(None, None, None)
            raise ContainerOperationError(
                'timeout', 'VPS SSH connection timed out.', 504
            ) from exc
        except (paramiko.SSHException, OSError) as exc:
            self.__exit__(None, None, None)
            raise ContainerOperationError(
                'ssh_error', 'Could not connect to the VPS.'
            ) from exc

    def __exit__(self, exc_type, exc_value, traceback):
        if self.sftp:
            self.sftp.close()
        if self.client:
            self.client.close()

    def _require_path(self, path, category, message, directory=False):
        flag = '-d' if directory else '-f'
        result = self._run_raw(f'test {flag} {shlex.quote(path)}')
        if result.exit_code != 0:
            raise ContainerOperationError(category, message, 409)

    def _run_raw(self, command):
        timeout = getattr(settings, 'DOCKER_ACTION_TIMEOUT', 60)
        try:
            _, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            output = stdout.read().decode(errors='replace')
            error = stderr.read().decode(errors='replace')
            return CommandResult(
                stdout.channel.recv_exit_status(), output, error
            )
        except (socket.timeout, TimeoutError) as exc:
            raise ContainerOperationError(
                'timeout', 'Docker operation timed out.', 504
            ) from exc
        except (paramiko.SSHException, OSError) as exc:
            raise ContainerOperationError(
                'ssh_error', 'Remote Docker command could not be executed.'
            ) from exc

    def _run(self, command, category='docker_error', message='Docker command failed.'):
        result = self._run_raw(command)
        if result.exit_code != 0:
            raise ContainerOperationError(category, message)
        return result.stdout

    def _compose(self):
        return f'docker compose -f {shlex.quote(self.compose_file)}'

    def declared_services(self):
        output = self._run(
            f'{self._compose()} config --services', 'compose_config_failed',
            'Could not read Docker Compose services.',
        )
        services = [line.strip() for line in output.splitlines() if line.strip()]
        if not services:
            raise ContainerOperationError(
                'compose_config_failed', 'Docker Compose defines no services.', 409
            )
        return services

    def validate_service(self, service):
        if service not in self.declared_services():
            raise ContainerOperationError(
                'service_not_found', 'Docker Compose service was not found.', 404
            )
        return service

    @staticmethod
    def parse_ps_output(output):
        output = output.strip()
        if not output:
            return []
        try:
            parsed = json.loads(output)
            return parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            try:
                return [json.loads(line) for line in output.splitlines() if line.strip()]
            except json.JSONDecodeError as exc:
                raise ContainerOperationError(
                    'docker_status_error', 'Could not parse Docker container status.'
                ) from exc

    @staticmethod
    def _normalize(service, row=None):
        if row is None:
            return {
                'service': service, 'container_id': '', 'container_name': '',
                'image': '', 'state': 'not_created', 'health': '',
                'exit_code': None, 'created_at': '', 'ports': [],
            }
        exit_code = row.get('ExitCode')
        try:
            exit_code = int(exit_code) if exit_code not in {None, ''} else None
        except (TypeError, ValueError):
            exit_code = None
        publishers = row.get('Publishers') or []
        if isinstance(publishers, dict):
            publishers = [publishers]
        return {
            'service': service,
            'container_id': str(row.get('ID') or ''),
            'container_name': str(row.get('Name') or ''),
            'image': str(row.get('Image') or ''),
            'state': str(row.get('State') or 'unknown').lower(),
            'health': str(row.get('Health') or '').lower(),
            'exit_code': exit_code,
            'created_at': str(row.get('CreatedAt') or ''),
            'ports': publishers,
        }

    def list(self):
        declared = self.declared_services()
        output = self._run(
            f'{self._compose()} ps --all --format json',
            'docker_status_error', 'Could not inspect Docker container status.',
        )
        rows = self.parse_ps_output(output)
        by_service = {str(row.get('Service') or ''): row for row in rows}
        return [self._normalize(service, by_service.get(service)) for service in declared]

    def detail(self, service):
        self.validate_service(service)
        return next(item for item in self.list() if item['service'] == service)

    def start(self, service):
        current = self.detail(service)
        if current['state'] == 'not_created':
            raise ContainerOperationError(
                'container_not_created', 'Service container has not been created.', 409
            )
        if current['state'] != 'running':
            self._run(
                f'{self._compose()} start {shlex.quote(service)}',
                'container_start_failed', 'Could not start the service container.',
            )
        return self.detail(service)

    def stop(self, service):
        current = self.detail(service)
        if current['state'] == 'not_created':
            raise ContainerOperationError(
                'container_not_created', 'Service container has not been created.', 409
            )
        if current['state'] not in {'exited', 'stopped', 'created', 'dead'}:
            stop_timeout = getattr(settings, 'DOCKER_STOP_TIMEOUT', 10)
            self._run(
                f'{self._compose()} stop --timeout {int(stop_timeout)} '
                f'{shlex.quote(service)}',
                'container_stop_failed', 'Could not stop the service container.',
            )
        return self.detail(service)

    def restart(self, service):
        current = self.detail(service)
        if current['state'] == 'not_created':
            raise ContainerOperationError(
                'container_not_created', 'Service container has not been created.', 409
            )
        self._run(
            f'{self._compose()} restart {shlex.quote(service)}',
            'container_restart_failed', 'Could not restart the service container.',
        )
        return self.detail(service)

    def remove(self, service):
        current = self.detail(service)
        if current['state'] != 'not_created':
            self._run(
                f'{self._compose()} rm --stop --force {shlex.quote(service)}',
                'container_remove_failed', 'Could not remove the service container.',
            )
        return self.detail(service)

    def logs(self, service, tail):
        current = self.detail(service)
        if current['state'] == 'not_created':
            raise ContainerOperationError(
                'container_not_created', 'Service container has not been created.', 409
            )
        output = self._run(
            f'{self._compose()} logs --no-color --timestamps --tail {int(tail)} '
            f'{shlex.quote(service)}',
            'container_logs_failed', 'Could not retrieve container logs.',
        )
        limit = getattr(settings, 'DOCKER_LOG_MAX_CHARACTERS', 200000)
        output = output[-limit:]
        return {'service': service, 'tail': tail, 'lines': output.splitlines()}
