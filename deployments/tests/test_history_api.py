from types import SimpleNamespace
from unittest.mock import patch

from django.urls import Resolver404, resolve
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from coreapp.models import User
from coreapp.roles import UserRoles
from deployments.models import Deployment
from deployments.services import create_deployment_steps
from projects.models import Project
from servers.models import Server


class DeploymentHistoryAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', password='password', role=UserRoles.ADMIN
        )
        self.other_admin = User.objects.create_user(
            email='other-admin@example.com', password='password',
            role=UserRoles.ADMIN,
        )
        self.user = User.objects.create_user(
            email='user@example.com', password='password', role=UserRoles.USER
        )
        self.server = Server.objects.create(
            name='History VPS', ip_address='192.0.2.70', username='deploy',
            encrypted_private_key='encrypted',
        )
        self.project = Project.objects.create(
            server=self.server, name='History Project',
            git_repository_url='https://github.com/example/history.git',
            branch='main', git_cloned_at=timezone.now(),
        )
        self.other_project = Project.objects.create(
            server=self.server, name='Other History Project',
            git_repository_url='https://github.com/example/other.git',
            git_cloned_at=timezone.now(),
        )
        self.client.force_authenticate(self.admin)

    def make_deployment(self, project=None, status_value=Deployment.Status.SUCCESS):
        deployment = Deployment.objects.create(
            project=project or self.project,
            trigger=Deployment.Trigger.DEPLOY,
            status=status_value,
            triggered_by=self.admin,
            deployed_commit='a' * 40,
        )
        create_deployment_steps(deployment)
        return deployment

    def test_list_is_paginated_compact_and_supports_filters_and_ordering(self):
        first = self.make_deployment(status_value=Deployment.Status.SUCCESS)
        second = self.make_deployment(status_value=Deployment.Status.FAILED)
        self.make_deployment(
            project=self.other_project, status_value=Deployment.Status.FAILED
        )

        filtered = self.client.get('/api/v1/deployments/', {
            'project': self.project.pk, 'status': Deployment.Status.FAILED,
        })
        oldest = self.client.get('/api/v1/deployments/', {
            'project': self.project.pk, 'ordering': 'oldest',
        })

        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertEqual(filtered.data['data']['count'], 1)
        row = filtered.data['data']['results'][0]
        self.assertEqual(row['id'], second.pk)
        self.assertNotIn('steps', row)
        self.assertNotIn('celery_task_id', row)
        self.assertEqual(oldest.data['data']['results'][0]['id'], first.pk)

    def test_detail_and_progress_are_compatible_and_include_steps(self):
        deployment = self.make_deployment()
        detail = self.client.get(f'/api/v1/deployments/{deployment.pk}/')
        progress = self.client.get(
            f'/api/v1/deployments/{deployment.pk}/progress/'
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data['data'], progress.data['data'])
        self.assertEqual(len(detail.data['data']['steps']), 10)
        self.assertNotIn('celery_task_id', detail.data['data'])

    @patch('deployments.tasks.run_deployment.apply_async')
    def test_new_deployment_snapshots_are_immutable(self, apply_async):
        apply_async.return_value = SimpleNamespace(id='snapshot-task')
        response = self.client.post(
            f'/api/v1/projects/{self.project.pk}/deploy/'
        )
        deployment_id = response.data['data']['id']

        self.project.name = 'Renamed Project'
        self.project.branch = 'develop'
        self.project.git_repository_url = 'https://github.com/example/changed.git'
        self.project.save(update_fields=['name', 'branch', 'git_repository_url'])
        self.server.name = 'Renamed VPS'
        self.server.ip_address = '192.0.2.71'
        self.server.save(update_fields=['name', 'ip_address'])
        self.admin.email = 'renamed@example.com'
        self.admin.save(update_fields=['email'])

        data = self.client.get(
            f'/api/v1/deployments/{deployment_id}/'
        ).data['data']
        self.assertEqual(data['project_name_snapshot'], 'History Project')
        self.assertEqual(data['server_name_snapshot'], 'History VPS')
        self.assertEqual(data['server_ip_snapshot'], '192.0.2.70')
        self.assertEqual(data['branch_snapshot'], 'main')
        self.assertEqual(
            data['repository_url_snapshot'],
            'https://github.com/example/history.git',
        )
        self.assertEqual(data['triggered_by_email_snapshot'], 'admin@example.com')

    def test_pre_module_history_snapshots_remain_blank(self):
        deployment = self.make_deployment()
        data = self.client.get(
            f'/api/v1/deployments/{deployment.pk}/'
        ).data['data']
        for field in [
            'project_name_snapshot', 'server_name_snapshot',
            'server_ip_snapshot', 'branch_snapshot',
            'repository_url_snapshot', 'triggered_by_email_snapshot',
        ]:
            self.assertEqual(data[field], '')

    def test_first_cancelling_admin_is_preserved(self):
        deployment = self.make_deployment(status_value=Deployment.Status.RUNNING)
        url = f'/api/v1/deployments/{deployment.pk}/cancel/'
        first = self.client.post(url)
        self.client.force_authenticate(self.other_admin)
        second = self.client.post(url)

        self.assertEqual(first.data['data']['cancel_requested_by'], self.admin.pk)
        self.assertEqual(
            first.data['data']['cancel_requested_by_email_snapshot'],
            'admin@example.com',
        )
        self.assertEqual(second.data['data']['cancel_requested_by'], self.admin.pk)
        self.assertEqual(
            second.data['data']['cancel_requested_by_email_snapshot'],
            'admin@example.com',
        )

    def test_invalid_filters_non_admin_and_unsupported_methods(self):
        deployment = self.make_deployment()
        self.assertEqual(
            self.client.get('/api/v1/deployments/', {'project': 'bad'}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.get('/api/v1/deployments/', {'status': 'unknown'}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.delete(f'/api/v1/deployments/{deployment.pk}/').status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        with self.assertRaises(Resolver404):
            resolve(f'/api/v1/deployments/{deployment.pk}/retry/')
        self.client.force_authenticate(self.user)
        self.assertEqual(
            self.client.get('/api/v1/deployments/').status_code,
            status.HTTP_403_FORBIDDEN,
        )
