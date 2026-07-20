from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from coreapp.models import User
from coreapp.roles import UserRoles
from projects.environment_services import (
    EnvironmentCredentialCipher,
    EnvironmentOperationError,
)
from projects.models import EnvironmentVariable, Project
from servers.models import Server


class EnvironmentVariableAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', password='password', role=UserRoles.ADMIN
        )
        self.user = User.objects.create_user(
            email='user@example.com', password='password', role=UserRoles.USER
        )
        self.server = Server.objects.create(
            name='VPS', ip_address='192.0.2.20', username='deploy',
            encrypted_private_key='encrypted',
        )
        self.project = Project.objects.create(
            server=self.server, name='Environment Project',
            git_repository_url='https://github.com/example/project.git',
        )
        self.other_project = Project.objects.create(
            server=self.server, name='Other Project',
            git_repository_url='https://github.com/example/other.git',
        )
        self.list_url = (
            f'/api/v1/projects/{self.project.pk}/environment-variables/'
        )
        self.client.force_authenticate(self.admin)

    def test_admin_crud_returns_plaintext_but_stores_ciphertext(self):
        created = self.client.post(
            self.list_url,
            {'key': 'DATABASE_URL', 'value': 'postgres://secret', 'is_secret': True},
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created['Cache-Control'], 'no-store')
        self.assertEqual(created.data['data']['value'], 'postgres://secret')
        variable = EnvironmentVariable.objects.get()
        self.assertNotIn('postgres://secret', variable.encrypted_value)
        self.assertEqual(
            EnvironmentCredentialCipher.decrypt(variable.encrypted_value),
            'postgres://secret',
        )
        self.assertEqual(variable.created_by, self.admin)
        self.assertEqual(variable.updated_by, self.admin)

        detail_url = f'{self.list_url}{variable.pk}/'
        updated = self.client.patch(
            detail_url, {'value': 'new\nvalue'}, format='json'
        )
        retrieved = self.client.get(detail_url)
        deleted = self.client.delete(detail_url)
        self.assertEqual(updated.data['data']['value'], 'new\nvalue')
        self.assertEqual(retrieved.data['data']['value'], 'new\nvalue')
        self.assertEqual(deleted.status_code, status.HTTP_200_OK)
        self.assertFalse(EnvironmentVariable.objects.filter(pk=variable.pk).exists())

    def test_validation_uniqueness_and_project_isolation(self):
        first = self.client.post(
            self.list_url, {'key': 'DEBUG', 'value': ''}, format='json'
        )
        duplicate = self.client.post(
            self.list_url, {'key': 'DEBUG', 'value': 'true'}, format='json'
        )
        invalid = self.client.post(
            self.list_url, {'key': 'debug', 'value': 'true'}, format='json'
        )
        variable_id = first.data['data']['id']
        wrong_project = self.client.get(
            f'/api/v1/projects/{self.other_project.pk}/environment-variables/{variable_id}/'
        )
        self.assertFalse(first.data['data']['is_secret'])
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(wrong_project.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_admin_is_forbidden(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(
            self.client.get(self.list_url).status_code, status.HTTP_403_FORBIDDEN
        )

    def test_archived_project_is_read_only(self):
        self.project.archive(self.admin)
        read = self.client.get(self.list_url)
        create = self.client.post(
            self.list_url, {'key': 'DEBUG', 'value': 'false'}, format='json'
        )
        generate = self.client.post(self.list_url + 'generate-env/')
        self.assertEqual(read.status_code, status.HTTP_200_OK)
        self.assertEqual(create.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(generate.status_code, status.HTTP_409_CONFLICT)

    @patch('projects.api.views.RemoteEnvironmentService')
    def test_generate_env_maps_success_and_sanitized_failure(self, service_class):
        service = service_class.return_value.__enter__.return_value
        service.generate.return_value = {
            'variable_count': 0, 'generated_at': '2026-07-18T10:00:00Z'
        }
        generated = self.client.post(self.list_url + 'generate-env/')
        self.assertEqual(generated.status_code, status.HTTP_200_OK)
        self.assertEqual(generated.data['data']['variable_count'], 0)
        self.assertEqual(generated['Cache-Control'], 'no-store')

        service_class.return_value.__enter__.side_effect = EnvironmentOperationError(
            'filesystem_error', 'Could not write the remote environment file.'
        )
        failed = self.client.post(self.list_url + 'generate-env/')
        self.assertEqual(failed.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(failed.data['errors']['category'], 'filesystem_error')

