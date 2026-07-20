from types import SimpleNamespace
from unittest.mock import patch

from django.db.models.deletion import ProtectedError
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from coreapp.models import User
from coreapp.roles import UserRoles
from deployments.models import Deployment
from deployments.services import create_deployment_steps
from projects.models import Project
from servers.models import Server


class DeploymentAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', password='password', role=UserRoles.ADMIN
        )
        self.user = User.objects.create_user(
            email='user@example.com', password='password', role=UserRoles.USER
        )
        self.server = Server.objects.create(
            name='VPS', ip_address='192.0.2.50', username='deploy',
            encrypted_private_key='encrypted',
        )
        self.project = Project.objects.create(
            server=self.server, name='API Deploy Project',
            git_repository_url='https://github.com/example/project.git',
            git_cloned_at=timezone.now(), current_commit='a' * 40,
        )
        self.base_url = f'/api/v1/projects/{self.project.pk}/'
        self.client.force_authenticate(self.admin)

    @patch('deployments.tasks.run_deployment.apply_async')
    def test_deploy_and_progress(self, apply_async):
        apply_async.return_value = SimpleNamespace(id='task-123')
        response = self.client.post(self.base_url + 'deploy/')

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        deployment = Deployment.objects.get()
        self.assertEqual(deployment.trigger, Deployment.Trigger.DEPLOY)
        self.assertEqual(deployment.celery_task_id, 'task-123')
        self.assertEqual(deployment.steps.count(), 10)
        self.assertNotIn('celery_task_id', response.data['data'])
        progress = self.client.get(
            f'/api/v1/deployments/{deployment.pk}/progress/'
        )
        latest = self.client.get(self.base_url + 'deployment-status/')
        self.assertEqual(progress.status_code, status.HTTP_200_OK)
        self.assertEqual(len(progress.data['data']['steps']), 10)
        self.assertEqual(latest.data['data']['id'], deployment.pk)

    @patch('deployments.tasks.run_deployment.apply_async')
    def test_redeploy_trigger_and_concurrency_conflict(self, apply_async):
        apply_async.return_value = SimpleNamespace(id='task-1')
        first = self.client.post(self.base_url + 'redeploy/')
        second = self.client.post(self.base_url + 'deploy/')
        self.assertEqual(first.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(first.data['data']['trigger'], 'redeploy')
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)

    def test_uncloned_archived_and_inactive_projects_are_rejected(self):
        self.project.git_cloned_at = None
        self.project.save(update_fields=['git_cloned_at'])
        uncloned = self.client.post(self.base_url + 'deploy/')
        self.project.git_cloned_at = timezone.now()
        self.project.is_archived = True
        self.project.save(update_fields=['git_cloned_at', 'is_archived'])
        archived = self.client.post(self.base_url + 'deploy/')
        self.project.is_archived = False
        self.project.save(update_fields=['is_archived'])
        self.server.is_active = False
        self.server.save(update_fields=['is_active'])
        inactive = self.client.post(self.base_url + 'deploy/')
        self.assertEqual(uncloned.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(archived.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(inactive.status_code, status.HTTP_409_CONFLICT)

    def test_non_admin_cannot_deploy(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(
            self.client.post(self.base_url + 'deploy/').status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_cancel_is_idempotent_and_completed_state_is_unchanged(self):
        deployment = Deployment.objects.create(
            project=self.project, trigger=Deployment.Trigger.DEPLOY,
            triggered_by=self.admin,
        )
        create_deployment_steps(deployment)
        url = f'/api/v1/deployments/{deployment.pk}/cancel/'
        first = self.client.post(url)
        first_time = first.data['data']['cancel_requested_at']
        second = self.client.post(url)
        self.assertEqual(second.data['data']['cancel_requested_at'], first_time)
        deployment.status = Deployment.Status.SUCCESS
        deployment.save(update_fields=['status'])
        late = self.client.post(url)
        self.assertEqual(late.data['data']['status'], Deployment.Status.SUCCESS)

    def test_project_with_deployment_history_cannot_be_deleted(self):
        Deployment.objects.create(
            project=self.project, trigger=Deployment.Trigger.DEPLOY,
            triggered_by=self.admin, status=Deployment.Status.SUCCESS,
        )
        response = self.client.delete(self.base_url)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())
