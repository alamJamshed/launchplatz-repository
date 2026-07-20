from unittest.mock import patch

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from containers.services import ContainerOperationError
from coreapp.models import User
from coreapp.roles import UserRoles
from deployments.models import Deployment
from projects.models import Project
from servers.models import Server


class ContainerManagementAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', password='password', role=UserRoles.ADMIN
        )
        self.user = User.objects.create_user(
            email='user@example.com', password='password', role=UserRoles.USER
        )
        self.server = Server.objects.create(
            name='VPS', ip_address='192.0.2.60', username='deploy',
            encrypted_private_key='encrypted',
        )
        self.project = Project.objects.create(
            server=self.server, name='Container Project',
            git_repository_url='https://github.com/example/project.git',
            git_cloned_at=timezone.now(),
        )
        self.base = f'/api/v1/projects/{self.project.pk}/containers/'
        self.container = {
            'service': 'backend', 'container_id': 'abc',
            'container_name': 'demo-backend-1', 'image': 'demo-backend',
            'state': 'running', 'health': 'healthy', 'exit_code': 0,
            'created_at': 'today', 'ports': [],
        }
        self.client.force_authenticate(self.admin)

    def remote(self, service_class):
        return service_class.return_value.__enter__.return_value

    @patch('projects.api.container_views.RemoteContainerService')
    def test_list_detail_and_actions_use_project_service(self, service_class):
        remote = self.remote(service_class)
        remote.list.return_value = [self.container]
        remote.detail.return_value = self.container
        remote.start.return_value = self.container
        remote.stop.return_value = {**self.container, 'state': 'exited'}
        remote.restart.return_value = self.container
        remote.remove.return_value = {**self.container, 'state': 'not_created'}

        self.assertEqual(self.client.get(self.base).status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.get(self.base + 'backend/').data['data']['service'], 'backend'
        )
        for action in ['start', 'stop', 'restart']:
            response = self.client.post(self.base + f'backend/{action}/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        removed = self.client.delete(self.base + 'backend/')
        self.assertEqual(removed.data['data']['state'], 'not_created')
        service_class.assert_called_with(self.project)

    @patch('projects.api.container_views.RemoteContainerService')
    def test_logs_validate_tail_and_disable_cache(self, service_class):
        remote = self.remote(service_class)
        remote.logs.return_value = {
            'service': 'backend', 'tail': 25,
            'lines': ['2026-07-20T10:00:00Z ready'],
        }
        response = self.client.get(self.base + 'backend/logs/', {'tail': 25})
        invalid = self.client.get(self.base + 'backend/logs/', {'tail': 1001})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('projects.api.container_views.RemoteContainerService')
    def test_remote_errors_are_sanitized(self, service_class):
        service_class.return_value.__enter__.side_effect = ContainerOperationError(
            'service_not_found', 'Docker Compose service was not found.', 404
        )
        response = self.client.get(self.base + 'other/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['errors']['category'], 'service_not_found')

    @patch('projects.api.container_views.RemoteContainerService')
    def test_archived_and_active_deployment_are_read_only(self, service_class):
        remote = self.remote(service_class)
        remote.list.return_value = [self.container]
        self.project.is_archived = True
        self.project.save(update_fields=['is_archived'])
        self.assertEqual(self.client.get(self.base).status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.post(self.base + 'backend/stop/').status_code,
            status.HTTP_409_CONFLICT,
        )
        self.project.is_archived = False
        self.project.save(update_fields=['is_archived'])
        Deployment.objects.create(
            project=self.project, trigger=Deployment.Trigger.DEPLOY,
            status=Deployment.Status.RUNNING, triggered_by=self.admin,
        )
        self.assertEqual(self.client.get(self.base).status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.post(self.base + 'backend/restart/').status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_non_admin_and_unknown_project_are_rejected(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(self.base).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.get('/api/v1/projects/999/containers/').status_code,
            status.HTTP_404_NOT_FOUND,
        )
