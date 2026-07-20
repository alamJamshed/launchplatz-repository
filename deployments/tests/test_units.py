import json
from unittest.mock import Mock

from django.test import TestCase, override_settings

from coreapp.models import User
from coreapp.roles import UserRoles
from deployments.models import Deployment, DeploymentStep
from deployments.services import (
    DeploymentCancelled,
    DeploymentPipelineError,
    DeploymentRunner,
    RemoteDeploymentService,
    STEP_NAMES,
    create_deployment_steps,
)
from projects.models import Project
from projects.validators import validate_compose_service_name
from servers.models import Server


class DeploymentPipelineUnitTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', password='password', role=UserRoles.ADMIN
        )
        self.server = Server.objects.create(
            name='VPS', ip_address='192.0.2.40', username='deploy',
            encrypted_private_key='encrypted',
        )
        self.project = Project.objects.create(
            server=self.server, name='Deploy Project',
            git_repository_url='https://github.com/example/project.git',
        )

    def deployment(self):
        deployment = Deployment.objects.create(
            project=self.project, trigger=Deployment.Trigger.DEPLOY,
            triggered_by=self.admin,
        )
        create_deployment_steps(deployment)
        return deployment

    def service(self):
        service = Mock()
        service.__enter__ = Mock(return_value=service)
        service.__exit__ = Mock()
        service.pull_code.return_value = ('a' * 40, 'b' * 40, 'main')
        return service

    def test_compose_service_validation_and_default(self):
        for value in ['backend', 'django-api', 'api_v2']:
            self.assertIsNone(validate_compose_service_name(value))
        self.assertEqual(
            Project._meta.get_field('django_service_name').default, 'backend'
        )

    def test_compose_health_parser_supports_array_and_lines(self):
        rows = [{'Service': 'backend', 'State': 'running', 'Health': 'healthy'}]
        self.assertEqual(
            RemoteDeploymentService._parse_compose_ps(json.dumps(rows)), rows
        )
        self.assertEqual(
            RemoteDeploymentService._parse_compose_ps(
                '\n'.join(json.dumps(item) for item in rows)
            ),
            rows,
        )

    def test_remote_compose_command_quotes_workspace_path(self):
        service = RemoteDeploymentService(self.project, Mock(pk=1))
        service.workspace = '/home/deploy/a project'
        self.assertEqual(
            service._compose(),
            "docker compose -f '/home/deploy/a project/docker-compose.yml'",
        )

    def test_cancellable_commands_wait_for_process_group_exit(self):
        service = RemoteDeploymentService(self.project, Mock(pk=1))
        service.pid_file = '/tmp/deployment.pid'
        service.client = Mock()
        service.sftp = Mock()
        service._cancel_requested = Mock(return_value=False)
        channel = Mock()
        channel.exit_status_ready.return_value = True
        channel.recv_exit_status.return_value = 0
        stdout = Mock(channel=channel)
        stdout.read.return_value = b'ok'
        service.client.exec_command.return_value = (Mock(), stdout, Mock())

        service._run_cancellable('docker compose version', 'docker_error', 'failed')

        command = service.client.exec_command.call_args.args[0]
        self.assertIn('setsid --wait sh -c', command)

    def test_health_requires_explicit_healthy_state(self):
        service = RemoteDeploymentService(self.project, Mock(pk=1))
        service.workspace = '/workspace'
        service._run_cancellable = Mock(side_effect=[
            'backend\n',
            json.dumps([
                {'Service': 'backend', 'State': 'running', 'Health': 'healthy'}
            ]),
        ])
        service.health_check()

        service._run_cancellable = Mock(side_effect=[
            'backend\n',
            json.dumps([
                {'Service': 'backend', 'State': 'running', 'Health': ''}
            ]),
        ])
        with self.settings(DEPLOYMENT_HEALTH_TIMEOUT=0):
            with self.assertRaises(DeploymentPipelineError) as raised:
                service.health_check()
        self.assertEqual(raised.exception.category, 'health_check_failed')

    def test_success_runs_steps_in_order_and_updates_commit(self):
        deployment = self.deployment()
        service = self.service()
        runner = DeploymentRunner(deployment, service_class=Mock(return_value=service))

        runner.run()

        deployment.refresh_from_db()
        self.project.refresh_from_db()
        self.assertEqual(deployment.status, Deployment.Status.SUCCESS)
        self.assertEqual(deployment.previous_commit, 'a' * 40)
        self.assertEqual(deployment.deployed_commit, 'b' * 40)
        self.assertEqual(
            list(deployment.steps.values_list('name', flat=True)), STEP_NAMES
        )
        self.assertFalse(
            deployment.steps.exclude(status=DeploymentStep.Status.SUCCESS).exists()
        )
        service.django_command.assert_any_call(
            'migrate --noinput', 'migration_failed', 'Django migrations failed.'
        )
        service.django_command.assert_any_call(
            'collectstatic --noinput', 'collectstatic_failed',
            'Django static collection failed.',
        )

    def test_failure_rolls_back_code_and_containers(self):
        deployment = self.deployment()
        service = self.service()
        service.build.side_effect = DeploymentPipelineError(
            'docker_build_failed', 'Docker image build failed.'
        )
        service.rollback.side_effect = None

        DeploymentRunner(
            deployment, service_class=Mock(return_value=service)
        ).run()

        deployment.refresh_from_db()
        self.assertEqual(deployment.status, Deployment.Status.FAILED)
        self.assertEqual(
            deployment.rollback_status, Deployment.RollbackStatus.SUCCEEDED
        )
        self.assertEqual(deployment.error_category, 'docker_build_failed')
        service.rollback.assert_called_once_with('a' * 40)
        self.assertEqual(
            deployment.steps.get(name='build_images').status,
            DeploymentStep.Status.FAILED,
        )
        self.assertEqual(
            deployment.steps.get(name='run_migrations').status,
            DeploymentStep.Status.SKIPPED,
        )

    def test_cancellation_rolls_back_and_preserves_cancelled_status(self):
        deployment = self.deployment()
        service = self.service()
        service.generate_env.side_effect = DeploymentCancelled()

        DeploymentRunner(
            deployment, service_class=Mock(return_value=service)
        ).run()

        deployment.refresh_from_db()
        self.assertEqual(deployment.status, Deployment.Status.CANCELLED)
        self.assertEqual(
            deployment.rollback_status, Deployment.RollbackStatus.SUCCEEDED
        )

    def test_rollback_failure_is_recorded_separately(self):
        deployment = self.deployment()
        service = self.service()
        service.build.side_effect = DeploymentPipelineError(
            'docker_build_failed', 'Docker image build failed.'
        )
        service.rollback.side_effect = DeploymentPipelineError(
            'rollback_git_failed', 'Could not restore the previous Git commit.'
        )

        DeploymentRunner(
            deployment, service_class=Mock(return_value=service)
        ).run()

        deployment.refresh_from_db()
        self.assertEqual(deployment.error_category, 'docker_build_failed')
        self.assertEqual(
            deployment.rollback_status, Deployment.RollbackStatus.FAILED
        )
        self.assertEqual(deployment.rollback_error_category, 'rollback_git_failed')
