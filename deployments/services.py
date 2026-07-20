import json
import shlex
import socket
import time
import uuid
from time import perf_counter

import paramiko
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from projects.environment_services import serialize_dotenv
from projects.git_services import GitOperationError, RemoteGitService

from .models import Deployment, DeploymentStep


STEP_NAMES = [
    'connect', 'pull_code', 'generate_env', 'build_images', 'start_containers',
    'run_migrations', 'collect_static', 'restart_services', 'health_check',
    'complete',
]


class DeploymentPipelineError(Exception):
    def __init__(self, category, message, status_code=502):
        super().__init__(message)
        self.category = category
        self.message = message
        self.status_code = status_code


class DeploymentCancelled(DeploymentPipelineError):
    def __init__(self):
        super().__init__('cancelled', 'Deployment cancellation was requested.', 409)


class RemoteDeploymentService(RemoteGitService):
    def __init__(self, project, deployment):
        super().__init__(project)
        self.deployment = deployment
        self.pid_file = None
        self.ignore_cancellation = False

    def __enter__(self):
        try:
            super().__enter__()
            self.pid_file = (
                f'{self.home}/.launchplatz/run/deployment-{self.deployment.pk}.pid'
            )
            self._run(
                f'mkdir -p {shlex.quote(self.home + "/.launchplatz/run")} && '
                f'chmod 700 {shlex.quote(self.home + "/.launchplatz/run")}'
            )
            self._require_clone()
            self._require_clean_workspace()
            self._require_compose_file()
            self._run_cancellable(
                'docker compose version', 'docker_unavailable',
                'Docker Compose is not available on the VPS.',
            )
            return self
        except GitOperationError as exc:
            self.__exit__(None, None, None)
            raise DeploymentPipelineError(
                exc.category, exc.message, exc.status_code
            ) from exc

    def _cancel_requested(self):
        if self.ignore_cancellation:
            return False
        close_old_connections()
        value = Deployment.objects.filter(pk=self.deployment.pk).values_list(
            'cancel_requested_at', flat=True
        ).first()
        return value is not None

    def _terminate_remote_process(self):
        if not self.client or not self.pid_file:
            return
        command = (
            f'if test -f {shlex.quote(self.pid_file)}; then '
            f'kill -TERM -- -$(cat {shlex.quote(self.pid_file)}) 2>/dev/null || true; fi'
        )
        try:
            self.client.exec_command(command, timeout=5)
        except Exception:
            pass

    def _run_cancellable(self, command, category, message, timeout=None):
        if self._cancel_requested():
            raise DeploymentCancelled()
        timeout = timeout or getattr(settings, 'DEPLOYMENT_COMMAND_TIMEOUT', 600)
        # --wait makes setsid propagate the wrapped command's exit status. Without
        # it, setsid may fork and return 0 before the real command completes.
        wrapped = (
            f'setsid --wait sh -c '
            f'{shlex.quote(f"echo $$ > {shlex.quote(self.pid_file)}; exec {command}")}'
        )
        started = perf_counter()
        try:
            _, stdout, _ = self.client.exec_command(wrapped, timeout=timeout)
            stdout.channel.set_combine_stderr(True)
            while not stdout.channel.exit_status_ready():
                if self._cancel_requested():
                    self._terminate_remote_process()
                    raise DeploymentCancelled()
                if perf_counter() - started > timeout:
                    self._terminate_remote_process()
                    raise DeploymentPipelineError('timeout', 'Deployment command timed out.', 504)
                time.sleep(0.25)
            output = stdout.read().decode(errors='replace')
            exit_code = stdout.channel.recv_exit_status()
        except DeploymentPipelineError:
            raise
        except (socket.timeout, TimeoutError) as exc:
            self._terminate_remote_process()
            raise DeploymentPipelineError('timeout', 'Deployment command timed out.', 504) from exc
        finally:
            try:
                self.sftp.remove(self.pid_file)
            except (OSError, AttributeError):
                pass
        if exit_code != 0:
            raise DeploymentPipelineError(category, message)
        return output

    def _require_clean_workspace(self):
        output = self._run(
            f'git -C {shlex.quote(self.workspace)} status --porcelain'
        ).stdout.strip()
        if output:
            raise DeploymentPipelineError(
                'working_tree_dirty', 'Working tree contains local changes.', 409
            )

    def _require_compose_file(self):
        compose_file = f'{self.workspace}/{self.project.docker_compose_path}'
        result = self._run_raw(f'test -f {shlex.quote(compose_file)}')
        if result.exit_code != 0:
            raise DeploymentPipelineError(
                'compose_file_missing', 'Docker Compose file was not found.', 409
            )

    def _compose(self):
        compose_file = f'{self.workspace}/{self.project.docker_compose_path}'
        return f'docker compose -f {shlex.quote(compose_file)}'

    def pull_code(self):
        previous = self._run(
            f'git -C {shlex.quote(self.workspace)} rev-parse HEAD'
        ).stdout.strip()
        branch = self.validate_branch(self.project.branch)
        self._run_cancellable(
            f'{self._git_environment()}git -C {shlex.quote(self.workspace)} '
            f'pull --ff-only origin {shlex.quote(branch)}',
            'git_error', 'Could not pull the selected Git branch.',
        )
        branch, current = self._state()
        return previous, current, branch

    def generate_env(self):
        variables = list(self.project.environment_variables.filter(
            is_active=True, is_deleted=False
        ))
        content = serialize_dotenv(variables)
        destination = f'{self.workspace}/.env'
        temporary = f'{destination}.tmp-{uuid.uuid4().hex}'
        try:
            with self.sftp.file(temporary, 'wb') as env_file:
                env_file.write(content)
                env_file.flush()
            self.sftp.chmod(temporary, 0o600)
            self.sftp.posix_rename(temporary, destination)
        except (OSError, paramiko.SSHException) as exc:
            try:
                self.sftp.remove(temporary)
            except OSError:
                pass
            raise DeploymentPipelineError(
                'environment_error', 'Could not generate the remote environment file.'
            ) from exc

    def build(self):
        self._run_cancellable(
            f'{self._compose()} build', 'docker_build_failed',
            'Docker image build failed.',
        )

    def up(self):
        self._run_cancellable(
            f'{self._compose()} up -d', 'compose_up_failed',
            'Docker Compose could not start the services.',
        )

    def django_command(self, arguments, category, message):
        service = shlex.quote(self.project.django_service_name)
        self._run_cancellable(
            f'{self._compose()} exec -T {service} python manage.py {arguments}',
            category, message,
        )

    def restart(self):
        self._run_cancellable(
            f'{self._compose()} restart', 'restart_failed',
            'Docker Compose could not restart the services.',
        )

    @staticmethod
    def _parse_compose_ps(output):
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
                raise DeploymentPipelineError(
                    'health_check_failed', 'Could not parse Docker health status.'
                ) from exc

    def health_check(self):
        timeout = getattr(settings, 'DEPLOYMENT_HEALTH_TIMEOUT', 120)
        deadline = perf_counter() + timeout
        expected = set(self._run_cancellable(
            f'{self._compose()} config --services', 'health_check_failed',
            'Could not inspect Docker Compose services.', timeout=min(timeout, 30),
        ).splitlines())
        if not expected:
            raise DeploymentPipelineError(
                'health_check_failed', 'Docker Compose defines no services.'
            )
        while perf_counter() < deadline:
            output = self._run_cancellable(
                f'{self._compose()} ps --all --format json', 'health_check_failed',
                'Could not inspect Docker service health.', timeout=min(timeout, 30),
            )
            services = self._parse_compose_ps(output)
            returned = {str(item.get('Service', '')) for item in services}
            if returned == expected and all(
                str(item.get('State', '')).lower() == 'running'
                and str(item.get('Health', '')).lower() == 'healthy'
                for item in services
            ):
                return
            time.sleep(2)
        raise DeploymentPipelineError(
            'health_check_failed',
            'Every Compose service must define and pass a healthcheck.',
            504,
        )

    def rollback(self, previous_commit):
        self.ignore_cancellation = True
        try:
            commit = shlex.quote(previous_commit)
            self._run_cancellable(
                f'git -C {shlex.quote(self.workspace)} reset --hard {commit}',
                'rollback_git_failed', 'Could not restore the previous Git commit.',
            )
            self.build()
            self.up()
            self.django_command(
                'collectstatic --noinput', 'rollback_static_failed',
                'Rollback static collection failed.',
            )
            self.restart()
            self.health_check()
        finally:
            self.ignore_cancellation = False


class DeploymentRunner:
    def __init__(self, deployment, service_class=RemoteDeploymentService):
        self.deployment = deployment
        self.project = deployment.project
        self.service_class = service_class
        self.service = None
        self.started_timer = None
        self.code_changed = False

    def _cancel_requested(self):
        self.deployment.refresh_from_db(fields=['cancel_requested_at'])
        return self.deployment.cancel_requested_at is not None

    def _run_step(self, name, callback):
        step = self.deployment.steps.get(name=name)
        if self._cancel_requested():
            raise DeploymentCancelled()
        step.status = DeploymentStep.Status.RUNNING
        step.started_at = timezone.now()
        step.save(update_fields=['status', 'started_at'])
        timer = perf_counter()
        try:
            result = callback()
        except DeploymentPipelineError as exc:
            step.status = (
                DeploymentStep.Status.CANCELLED
                if isinstance(exc, DeploymentCancelled)
                else DeploymentStep.Status.FAILED
            )
            step.error_category = exc.category
            step.error_message = exc.message
            step.completed_at = timezone.now()
            step.duration_ms = round((perf_counter() - timer) * 1000)
            step.save()
            raise
        step.status = DeploymentStep.Status.SUCCESS
        step.completed_at = timezone.now()
        step.duration_ms = round((perf_counter() - timer) * 1000)
        step.save()
        return result

    def _skip_remaining(self):
        self.deployment.steps.filter(status=DeploymentStep.Status.PENDING).update(
            status=DeploymentStep.Status.SKIPPED
        )

    def _rollback(self):
        if not self.code_changed or not self.deployment.previous_commit or not self.service:
            self.deployment.rollback_status = Deployment.RollbackStatus.NOT_REQUIRED
            return
        self.deployment.rollback_status = Deployment.RollbackStatus.RUNNING
        self.deployment.save(update_fields=['rollback_status'])
        try:
            self.service.rollback(self.deployment.previous_commit)
            self.deployment.rollback_status = Deployment.RollbackStatus.SUCCEEDED
        except DeploymentPipelineError as exc:
            self.deployment.rollback_status = Deployment.RollbackStatus.FAILED
            self.deployment.rollback_error_category = exc.category

    def run(self):
        self.started_timer = perf_counter()
        self.deployment.status = Deployment.Status.RUNNING
        self.deployment.started_at = timezone.now()
        self.deployment.save(update_fields=['status', 'started_at'])
        final_status = Deployment.Status.SUCCESS
        failure = None
        try:
            self.service = self.service_class(self.project, self.deployment)
            self._run_step('connect', self.service.__enter__)
            previous, current, branch = self._run_step(
                'pull_code', self.service.pull_code
            )
            self.deployment.previous_commit = previous
            self.deployment.deployed_commit = current
            self.code_changed = previous != current
            self.deployment.save(
                update_fields=['previous_commit', 'deployed_commit']
            )
            self._run_step('generate_env', self.service.generate_env)
            self._run_step('build_images', self.service.build)
            self._run_step('start_containers', self.service.up)
            self._run_step(
                'run_migrations',
                lambda: self.service.django_command(
                    'migrate --noinput', 'migration_failed',
                    'Django migrations failed.',
                ),
            )
            self._run_step(
                'collect_static',
                lambda: self.service.django_command(
                    'collectstatic --noinput', 'collectstatic_failed',
                    'Django static collection failed.',
                ),
            )
            self._run_step('restart_services', self.service.restart)
            self._run_step('health_check', self.service.health_check)
            self._run_step('complete', lambda: None)
            self.project.record_git_state(
                branch, current, user=self.deployment.triggered_by
            )
        except DeploymentPipelineError as exc:
            failure = exc
            final_status = (
                Deployment.Status.CANCELLED
                if isinstance(exc, DeploymentCancelled)
                else Deployment.Status.FAILED
            )
            self._skip_remaining()
            self.deployment.rollback_status = (
                Deployment.RollbackStatus.PENDING
                if self.code_changed else Deployment.RollbackStatus.NOT_REQUIRED
            )
            self.deployment.save(update_fields=['rollback_status'])
            self._rollback()
        finally:
            if self.service:
                self.service.__exit__(None, None, None)
        self.deployment.status = final_status
        self.deployment.error_category = failure.category if failure else ''
        self.deployment.error_message = failure.message if failure else ''
        self.deployment.completed_at = timezone.now()
        self.deployment.duration_ms = round(
            (perf_counter() - self.started_timer) * 1000
        )
        self.deployment.save()
        return self.deployment


def create_deployment_steps(deployment):
    DeploymentStep.objects.bulk_create([
        DeploymentStep(deployment=deployment, order=index, name=name)
        for index, name in enumerate(STEP_NAMES, start=1)
    ])
