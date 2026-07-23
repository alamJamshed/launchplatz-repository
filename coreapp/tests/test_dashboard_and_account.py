from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from coreapp.api.common.cookies import REFRESH_COOKIE_NAME
from coreapp.models import User
from coreapp.roles import UserRoles
from deployments.models import Deployment
from projects.models import Project
from servers.models import Server
from servers.tests.helpers import generate_private_key


class DashboardAndAccountAPITests(APITestCase):
    password = 'StrongPassword123!'

    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', password=self.password,
            first_name='Launch', last_name='Admin', role=UserRoles.ADMIN,
        )
        self.user = User.objects.create_user(
            email='user@example.com', password=self.password,
            first_name='Normal', last_name='User', role=UserRoles.USER,
        )
        self.client.force_authenticate(self.admin)

    def test_profile_patch_updates_only_editable_fields(self):
        response = self.client.patch(
            '/api/v1/auth/profile/',
            {'first_name': 'Updated', 'phone': '+880123', 'email': 'ignored@example.com'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.first_name, 'Updated')
        self.assertEqual(self.admin.phone, '+880123')
        self.assertEqual(self.admin.email, 'admin@example.com')

    def test_password_change_requires_current_password_and_clears_refresh(self):
        refresh = RefreshToken.for_user(self.admin)
        self.client.cookies[REFRESH_COOKIE_NAME] = str(refresh)
        invalid = self.client.post(
            '/api/v1/auth/change-password/',
            {'current_password': 'wrong', 'new_password': 'NewStrongPassword456!',
             'new_password_confirmation': 'NewStrongPassword456!'}, format='json',
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            '/api/v1/auth/change-password/',
            {'current_password': self.password, 'new_password': 'NewStrongPassword456!',
             'new_password_confirmation': 'NewStrongPassword456!'}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.cookies[REFRESH_COOKIE_NAME]['max-age'], 0)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password('NewStrongPassword456!'))

    def test_dashboard_returns_operational_summary_and_recent_deployments(self):
        server = Server.objects.create(
            name='VPS', ip_address='192.0.2.10', ssh_port=22, username='root',
            encrypted_private_key=generate_private_key(), status='Online',
        )
        project = Project.objects.create(
            server=server, name='Demo', git_repository_url='https://example.com/repo.git'
        )
        Deployment.objects.create(
            project=project, trigger=Deployment.Trigger.DEPLOY,
            status=Deployment.Status.SUCCESS, triggered_by=self.admin,
        )
        response = self.client.get('/api/v1/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data['data']
        self.assertEqual(data['servers']['online'], 1)
        self.assertEqual(data['projects']['active'], 1)
        self.assertEqual(data['deployments']['success'], 1)
        self.assertEqual(len(data['recent_deployments']), 1)

    def test_non_admin_cannot_use_dashboard_or_account_mutations(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/v1/dashboard/').status_code, 403)
        self.assertEqual(self.client.patch('/api/v1/auth/profile/', {}).status_code, 403)
        self.assertEqual(
            self.client.post('/api/v1/auth/change-password/', {}).status_code, 403
        )
