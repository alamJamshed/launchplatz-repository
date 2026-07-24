from rest_framework import status
from rest_framework.test import APITestCase

from coreapp.models import User
from coreapp.roles import UserRoles
from projects.models import Project
from servers.models import Server


PROJECTS_URL = '/api/v1/projects/'


class ProjectAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', password='password',
            first_name='Admin', last_name='User', role=UserRoles.ADMIN,
        )
        self.user = User.objects.create_user(
            email='user@example.com', password='password',
            first_name='Regular', last_name='User', role=UserRoles.USER,
        )
        self.server = Server.objects.create(
            name='Primary VPS', ip_address='192.0.2.10', ssh_port=22,
            username='deploy', encrypted_private_key='encrypted',
        )
        self.payload = {
            'server': self.server.pk,
            'name': 'Launch Project',
            'git_repository_url': 'https://github.com/example/project.git',
            'branch': 'main',
            'domain': 'App.Example.COM',
            'docker_compose_path': 'deploy/docker-compose.yml',
        }
        self.client.force_authenticate(self.admin)

    def create_project(self, **overrides):
        return self.client.post(
            PROJECTS_URL, {**self.payload, **overrides}, format='json'
        )

    def test_admin_can_create_retrieve_and_update_project(self):
        created = self.create_project(framework='anything')

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        data = created.data['data']
        self.assertEqual(data['framework'], Project.Framework.DJANGO_REACT)
        self.assertEqual(data['framework_display'], 'Django + React')
        self.assertEqual(data['domain'], '')
        self.assertNotIn('environment_variables', data)
        project = Project.objects.get()
        self.assertEqual(project.created_by, self.admin)
        self.assertEqual(project.updated_by, self.admin)

        detail_url = f'{PROJECTS_URL}{project.pk}/'
        retrieved = self.client.get(detail_url)
        updated = self.client.patch(
            detail_url,
            {'name': 'Renamed Project', 'branch': 'develop'},
            format='json',
        )

        self.assertEqual(retrieved.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data['data']['name'], 'Renamed Project')
        self.assertEqual(updated.data['data']['branch'], 'develop')

    def test_non_admin_cannot_access_projects(self):
        self.client.force_authenticate(self.user)
        forbidden = self.client.get(PROJECTS_URL)
        self.client.force_authenticate(None)
        anonymous = self.client.get(PROJECTS_URL)

        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(anonymous.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_requires_active_server_and_unique_project_name(self):
        self.server.is_deleted = True
        self.server.is_active = False
        self.server.save(update_fields=['is_deleted', 'is_active'])
        inactive_server = self.create_project()
        self.assertEqual(inactive_server.status_code, status.HTTP_400_BAD_REQUEST)

        self.server.is_deleted = False
        self.server.is_active = True
        self.server.save(update_fields=['is_deleted', 'is_active'])
        created = self.create_project()
        duplicate = self.create_project()
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_invalid_project_configuration(self):
        cases = [
            {'git_repository_url': 'http://github.com/example/project.git'},
            {'git_repository_url': 'https://user:secret@github.com/a/b.git'},
            {'docker_compose_path': '../docker-compose.yml'},
        ]
        for index, invalid in enumerate(cases):
            with self.subTest(invalid=invalid):
                response = self.create_project(
                    name=f'Invalid Project {index}', **invalid
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_archive_filters_restore_and_idempotency(self):
        first = self.create_project()
        second = self.create_project(
            name='Second Project', domain='second.example.com'
        )
        second_id = second.data['data']['id']
        archive_url = f'{PROJECTS_URL}{second_id}/archive/'
        restore_url = f'{PROJECTS_URL}{second_id}/restore/'

        archived = self.client.post(archive_url)
        first_archived_at = archived.data['data']['archived_at']
        archived_again = self.client.post(archive_url)

        default_list = self.client.get(PROJECTS_URL)
        archived_list = self.client.get(PROJECTS_URL, {'archived': 'true'})
        all_list = self.client.get(PROJECTS_URL, {'archived': 'all'})
        invalid_filter = self.client.get(PROJECTS_URL, {'archived': 'invalid'})

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(archived.status_code, status.HTTP_200_OK)
        self.assertEqual(
            archived_again.data['data']['archived_at'], first_archived_at
        )
        self.assertEqual(default_list.data['data']['count'], 1)
        self.assertEqual(archived_list.data['data']['count'], 1)
        self.assertEqual(all_list.data['data']['count'], 2)
        self.assertEqual(invalid_filter.status_code, status.HTTP_400_BAD_REQUEST)

        restored = self.client.post(restore_url)
        restored_again = self.client.post(restore_url)
        self.assertEqual(restored.status_code, status.HTTP_200_OK)
        self.assertFalse(restored.data['data']['is_archived'])
        self.assertIsNone(restored.data['data']['archived_at'])
        self.assertEqual(restored_again.status_code, status.HTTP_200_OK)

    def test_delete_permanently_removes_project(self):
        created = self.create_project()
        project_id = created.data['data']['id']

        deleted = self.client.delete(f'{PROJECTS_URL}{project_id}/')

        self.assertEqual(deleted.status_code, status.HTTP_200_OK)
        self.assertFalse(Project.objects.filter(pk=project_id).exists())
        self.assertEqual(
            self.client.get(f'{PROJECTS_URL}{project_id}/').status_code,
            status.HTTP_404_NOT_FOUND,
        )
