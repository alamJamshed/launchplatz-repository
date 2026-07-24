from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from coreapp.models import User
from coreapp.roles import UserRoles
from projects.models import Project
from servers.models import Server

from routing.models import Domain, Route
from routing.services import override_revision, render_compose_override, verify_domain_dns
from routing.validators import normalize_hostname


class HostnameValidationTests(SimpleTestCase):
    def test_normalizes_case_trailing_dot_and_idna(self):
        self.assertEqual(
            normalize_hostname('BÜCHER.Example.'),
            'xn--bcher-kva.example',
        )

    def test_rejects_non_hostname_inputs(self):
        for value in [
            'https://example.test', 'example.test:8000', '*.example.test',
            '192.0.2.10', 'example', 'bad_label.example',
        ]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                normalize_hostname(value)


class RoutingAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', password='password',
            first_name='Admin', last_name='User', role=UserRoles.ADMIN,
        )
        self.server = Server.objects.create(
            name='Test server', ip_address='192.0.2.10', username='deploy',
            encrypted_private_key='encrypted',
        )
        self.project = Project.objects.create(
            server=self.server,
            name='App',
            git_repository_url='https://example.com/app.git',
            django_service_name='backend',
        )
        self.client.force_authenticate(self.admin)

    def create_route(self, **overrides):
        return self.client.post('/api/v1/routing/routes/', {
            'project': self.project.pk,
            'hostname': 'App.Internal.Test.',
            'service_name': 'backend',
            'internal_port': 8000,
            **overrides,
        }, format='json')

    def test_create_normalizes_and_prevents_second_project_route(self):
        created = self.create_route()
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            created.data['data']['normalized_hostname'], 'app.internal.test'
        )
        duplicate = self.create_route(hostname='other.internal.test')
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tls_requires_verified_dns(self):
        response = self.create_route(tls_enabled=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_project_domain_is_read_only_compatibility_data(self):
        response = self.client.patch(
            f'/api/v1/projects/{self.project.pk}/',
            {'domain': 'ignored.internal.test'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db()
        self.assertEqual(self.project.domain, '')


class RoutingServiceTests(APITestCase):
    def setUp(self):
        server = Server.objects.create(
            name='Test server', ip_address='192.0.2.10', username='deploy',
            encrypted_private_key='encrypted',
        )
        project = Project.objects.create(
            server=server, name='App',
            git_repository_url='https://example.com/app.git',
        )
        domain = Domain.objects.create(
            project=project, hostname='app.internal.test'
        )
        self.route = Route.objects.create(
            domain=domain, service_name='backend', internal_port=8000
        )

    def test_override_is_deterministic_and_uses_internal_port(self):
        first = render_compose_override(self.route)
        second = render_compose_override(self.route)
        self.assertEqual(first, second)
        self.assertEqual(override_revision(first), override_revision(second))
        self.assertIn('launchplatz-proxy', first)
        self.assertIn('8000', first)
        self.assertIn('Host(`app.internal.test`)', first)

    @patch('routing.services.socket.getaddrinfo')
    def test_dns_requires_two_stable_successes(self, getaddrinfo):
        getaddrinfo.return_value = [
            (None, None, None, None, ('192.0.2.10', 0))
        ]
        verify_domain_dns(self.route.domain)
        self.route.domain.refresh_from_db()
        self.assertEqual(self.route.domain.dns_status, Domain.DNSStatus.PENDING)
        verify_domain_dns(self.route.domain)
        self.route.domain.refresh_from_db()
        self.assertEqual(self.route.domain.dns_status, Domain.DNSStatus.VERIFIED)
