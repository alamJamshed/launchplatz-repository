import json
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase, override_settings

from containers.services import ContainerOperationError, RemoteContainerService


class RemoteContainerServiceUnitTests(SimpleTestCase):
    def service(self):
        project = SimpleNamespace(
            pk=7, docker_compose_path='deploy/docker-compose.yml'
        )
        service = RemoteContainerService(project)
        service.workspace = '/home/deploy/a project'
        service.compose_file = service.workspace + '/deploy/docker-compose.yml'
        return service

    def test_compose_path_is_shell_quoted(self):
        self.assertEqual(
            self.service()._compose(),
            "docker compose -f '/home/deploy/a project/deploy/docker-compose.yml'",
        )

    def test_parses_array_and_newline_json(self):
        rows = [
            {'Service': 'backend', 'State': 'running'},
            {'Service': 'frontend', 'State': 'exited'},
        ]
        self.assertEqual(
            RemoteContainerService.parse_ps_output(json.dumps(rows)), rows
        )
        self.assertEqual(
            RemoteContainerService.parse_ps_output(
                '\n'.join(json.dumps(row) for row in rows)
            ),
            rows,
        )

    def test_list_merges_declared_and_missing_services(self):
        service = self.service()
        service.declared_services = Mock(return_value=['backend', 'frontend'])
        service._run = Mock(return_value=json.dumps([{
            'Service': 'backend', 'ID': 'abc', 'Name': 'demo-backend-1',
            'Image': 'demo-backend', 'State': 'running', 'Health': 'healthy',
            'ExitCode': 0, 'CreatedAt': 'today',
            'Publishers': [{'PublishedPort': 8001, 'TargetPort': 8000}],
        }]))

        result = service.list()

        self.assertEqual(result[0]['state'], 'running')
        self.assertEqual(result[0]['health'], 'healthy')
        self.assertEqual(result[0]['exit_code'], 0)
        self.assertEqual(result[1]['service'], 'frontend')
        self.assertEqual(result[1]['state'], 'not_created')

    def test_service_must_be_declared(self):
        service = self.service()
        service.declared_services = Mock(return_value=['backend'])
        with self.assertRaises(ContainerOperationError) as raised:
            service.validate_service('other')
        self.assertEqual(raised.exception.category, 'service_not_found')
        self.assertEqual(raised.exception.status_code, 404)

    def test_start_and_stop_are_idempotent(self):
        service = self.service()
        running = {'service': 'backend', 'state': 'running'}
        service.detail = Mock(return_value=running)
        service._run = Mock()
        self.assertEqual(service.start('backend'), running)
        service._run.assert_not_called()

        stopped = {'service': 'backend', 'state': 'exited'}
        service.detail = Mock(return_value=stopped)
        self.assertEqual(service.stop('backend'), stopped)
        service._run.assert_not_called()

    def test_removed_container_start_conflicts_and_remove_is_idempotent(self):
        service = self.service()
        missing = {'service': 'backend', 'state': 'not_created'}
        service.detail = Mock(return_value=missing)
        service._run = Mock()
        with self.assertRaises(ContainerOperationError) as raised:
            service.start('backend')
        self.assertEqual(raised.exception.category, 'container_not_created')
        self.assertEqual(service.remove('backend'), missing)
        service._run.assert_not_called()

    def test_restart_and_remove_commands_preserve_volumes(self):
        service = self.service()
        running = {'service': 'backend', 'state': 'running'}
        service.detail = Mock(side_effect=[running, running, running, {
            'service': 'backend', 'state': 'not_created'
        }])
        service._run = Mock()
        service.restart('backend')
        self.assertIn('restart backend', service._run.call_args_list[0].args[0])
        service.remove('backend')
        remove_command = service._run.call_args_list[1].args[0]
        self.assertIn('rm --stop --force backend', remove_command)
        self.assertNotIn(' -v', remove_command)

    @override_settings(DOCKER_LOG_MAX_CHARACTERS=20)
    def test_logs_are_timestamped_bounded_and_split(self):
        service = self.service()
        service.detail = Mock(return_value={'service': 'backend', 'state': 'running'})
        service._run = Mock(return_value='old line\n2026-07-20T10:00:00Z recent\n')
        result = service.logs('backend', 5)
        self.assertEqual(result['tail'], 5)
        self.assertLessEqual(len('\n'.join(result['lines'])), 20)
        self.assertIn('--timestamps --tail 5 backend', service._run.call_args.args[0])

