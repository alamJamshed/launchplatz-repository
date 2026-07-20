from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from coreapp.models import User
from projects.git_services import (
    GitCredentialCipher,
    GitOperationError,
    RemoteGitService,
    sanitize_git_output,
)
from projects.models import Project


TEST_GIT_KEY = 'MTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTE='


class GitCredentialUnitTests(SimpleTestCase):
    @override_settings(GIT_CREDENTIAL_ENCRYPTION_KEY=TEST_GIT_KEY)
    def test_encrypts_and_decrypts_git_key(self):
        encrypted = GitCredentialCipher.encrypt('private-key')

        self.assertNotEqual(encrypted, 'private-key')
        self.assertEqual(GitCredentialCipher.decrypt(encrypted), 'private-key')

    @override_settings(GIT_CREDENTIAL_ENCRYPTION_KEY=None)
    def test_requires_separate_configured_key(self):
        with self.assertRaises(ImproperlyConfigured):
            GitCredentialCipher.encrypt('private-key')


class GitCommandUnitTests(SimpleTestCase):
    def test_sanitizes_ansi_nulls_and_truncates_output(self):
        output = '\x1b[31msecret\x1b[0m\x00' + ('x' * 50)

        sanitized = sanitize_git_output(output, limit=20)

        self.assertNotIn('\x1b', sanitized)
        self.assertNotIn('\x00', sanitized)
        self.assertEqual(len(sanitized), 20)

    def test_validates_branch_names(self):
        self.assertEqual(RemoteGitService.validate_branch('feature/api-v2'), 'feature/api-v2')
        for branch in ['../main', 'feature branch', 'main..old', 'bad~name', 'name.lock']:
            with self.subTest(branch=branch):
                with self.assertRaises(GitOperationError):
                    RemoteGitService.validate_branch(branch)

    def test_parses_and_sorts_unique_remote_branches(self):
        output = (
            'abc\trefs/heads/main\n'
            'def\trefs/heads/feature/api\n'
            'ghi\trefs/tags/v1\n'
            'abc\trefs/heads/main\n'
        )

        self.assertEqual(
            RemoteGitService.parse_branches(output),
            ['feature/api', 'main'],
        )

    @patch('projects.git_services.ServerCredentialCipher.decrypt')
    @patch('projects.git_services.SSHKeyParser.parse')
    @patch.object(RemoteGitService, '_prepare_git_credential')
    @patch.object(RemoteGitService, '_run')
    @patch('projects.git_services.paramiko.SSHClient')
    def test_builds_project_workspace_under_remote_home(
        self, ssh_client_class, run, prepare, parse_key, decrypt
    ):
        client = ssh_client_class.return_value
        client.open_sftp.return_value.normalize.return_value = '/home/deploy'
        project = SimpleNamespace(
            pk=42,
            server=SimpleNamespace(
                encrypted_private_key='encrypted', ip_address='192.0.2.10',
                ssh_port=22, username='deploy',
            ),
        )

        with RemoteGitService(project) as service:
            self.assertEqual(service.workspace, '/home/deploy/launchplatz/projects/42')
            self.assertEqual(
                service.git_key_path,
                '/home/deploy/.launchplatz/keys/project-42',
            )

        client.close.assert_called_once()

    def test_clone_shell_quotes_repository_and_workspace(self):
        project = SimpleNamespace(
            pk=7,
            branch='main',
            git_repository_url='https://example.com/org/repo;name.git',
            record_git_state=Mock(),
        )
        service = RemoteGitService(project)
        service.workspace = '/home/deploy/launchplatz/projects/7'
        service._git_environment = Mock(return_value='')
        service._run_raw = Mock(return_value=SimpleNamespace(exit_code=1))
        service._run = Mock(return_value=SimpleNamespace(output='cloned'))
        service._state = Mock(return_value=('main', 'a' * 40))

        service.clone()

        command = service._run.call_args_list[0].args[0]
        self.assertIn("'https://example.com/org/repo;name.git'", command)


class ProjectGitStateUnitTests(SimpleTestCase):
    @patch('projects.models.timezone.now')
    def test_records_cached_git_state_and_clone_time_once(self, now):
        first_time = Mock()
        second_time = Mock()
        now.side_effect = [first_time, second_time]
        project = Project(name='Project')
        project.save = Mock()
        user = User(email='admin@example.com')

        project.record_git_state('main', 'a' * 40, cloned=True, user=user)
        project.record_git_state('main', 'b' * 40, cloned=True, user=user)

        self.assertIs(project.git_cloned_at, first_time)
        self.assertEqual(project.current_commit, 'b' * 40)
        self.assertIs(project.last_git_synced_at, second_time)
        self.assertEqual(project.save.call_count, 2)
