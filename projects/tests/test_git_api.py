from unittest.mock import Mock, patch

from rest_framework import status
from rest_framework.test import APITestCase

from coreapp.models import User
from coreapp.roles import UserRoles
from projects.git_services import GitCredentialCipher, GitOperationError
from projects.models import GitOperation, Project
from servers.models import Server
from servers.tests.helpers import generate_private_key


class ProjectGitAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', password='password',
            first_name='Admin', last_name='User', role=UserRoles.ADMIN,
        )
        self.user = User.objects.create_user(
            email='user@example.com', password='password',
            first_name='User', last_name='User', role=UserRoles.USER,
        )
        self.server = Server.objects.create(
            name='VPS', ip_address='192.0.2.10', username='deploy',
            encrypted_private_key='encrypted',
        )
        self.project = Project.objects.create(
            server=self.server,
            name='Project',
            git_repository_url='git@example.com:org/project.git',
            branch='main',
        )
        self.base_url = f'/api/v1/projects/{self.project.pk}/'
        self.client.force_authenticate(self.admin)

    def test_git_private_key_is_encrypted_and_write_only(self):
        private_key = generate_private_key()

        response = self.client.patch(
            self.base_url, {'git_private_key': private_key}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('git_private_key', response.data['data'])
        self.assertNotIn('encrypted_git_private_key', response.data['data'])
        self.project.refresh_from_db()
        self.assertNotEqual(self.project.encrypted_git_private_key, private_key)
        self.assertEqual(
            GitCredentialCipher.decrypt(self.project.encrypted_git_private_key),
            private_key,
        )

    def test_branch_must_use_select_action_after_clone(self):
        from django.utils import timezone

        self.project.git_cloned_at = timezone.now()
        self.project.current_branch = 'main'
        self.project.save(update_fields=['git_cloned_at', 'current_branch'])

        response = self.client.patch(
            self.base_url, {'branch': 'develop'}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('branch', response.data['errors'])

    @patch('projects.api.views.RemoteGitService')
    def test_all_git_actions_and_operation_history(self, service_class):
        service = service_class.return_value.__enter__.return_value
        service.clone.return_value = {
            'branch': 'main', 'commit': 'a' * 40,
            'workspace': '~/launchplatz/projects/1', '_output': 'cloned',
        }
        service.pull.return_value = {
            'branch': 'main', 'commit': 'b' * 40, '_output': 'pulled',
        }
        service.current_commit.return_value = {
            'branch': 'main', 'commit': 'b' * 40, '_output': '',
        }
        service.branches.return_value = {
            'branches': ['develop', 'main'], '_output': 'refs',
        }
        service.select_branch.return_value = {
            'branch': 'develop', 'commit': 'c' * 40, '_output': 'switched',
        }

        responses = [
            self.client.post(f'{self.base_url}git/clone/'),
            self.client.post(f'{self.base_url}git/pull/'),
            self.client.get(f'{self.base_url}git/current-commit/'),
            self.client.get(f'{self.base_url}git/branches/'),
            self.client.post(
                f'{self.base_url}git/select-branch/',
                {'branch': 'develop'},
                format='json',
            ),
        ]

        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(responses[3].data['data']['branches'], ['develop', 'main'])
        self.assertEqual(responses[4].data['data']['branch'], 'develop')
        self.assertEqual(GitOperation.objects.count(), 5)
        operations = self.client.get(f'{self.base_url}git/operations/')
        self.assertEqual(operations.status_code, status.HTTP_200_OK)
        self.assertEqual(operations.data['data']['count'], 5)
        self.assertNotIn('private', str(operations.data))

    @patch('projects.api.views.RemoteGitService')
    def test_failure_is_categorized_and_logged(self, service_class):
        service = service_class.return_value.__enter__.return_value
        service.pull.side_effect = GitOperationError(
            'working_tree_dirty', 'Working tree contains local changes.', 409,
            'sanitized output',
        )

        response = self.client.post(f'{self.base_url}git/pull/')

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['errors']['category'], 'working_tree_dirty')
        operation = GitOperation.objects.get()
        self.assertEqual(operation.status, GitOperation.Status.FAILED)
        self.assertEqual(operation.error_category, 'working_tree_dirty')
        self.assertEqual(operation.output, 'sanitized output')

    @patch('projects.api.views.RemoteGitService')
    def test_archived_project_blocks_mutating_but_allows_read_actions(self, service_class):
        self.project.is_archived = True
        self.project.save(update_fields=['is_archived'])
        service = service_class.return_value.__enter__.return_value
        service.current_commit.return_value = {
            'branch': 'main', 'commit': 'a' * 40, '_output': '',
        }

        clone = self.client.post(f'{self.base_url}git/clone/')
        pull = self.client.post(f'{self.base_url}git/pull/')
        select = self.client.post(
            f'{self.base_url}git/select-branch/', {'branch': 'develop'}, format='json'
        )
        current = self.client.get(f'{self.base_url}git/current-commit/')

        self.assertEqual(clone.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(pull.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(select.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(current.status_code, status.HTTP_200_OK)
        service.clone.assert_not_called()

    def test_non_admin_cannot_run_git_actions(self):
        self.client.force_authenticate(self.user)
        forbidden = self.client.post(f'{self.base_url}git/clone/')
        self.client.force_authenticate(None)
        anonymous = self.client.post(f'{self.base_url}git/clone/')

        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(anonymous.status_code, status.HTTP_401_UNAUTHORIZED)
