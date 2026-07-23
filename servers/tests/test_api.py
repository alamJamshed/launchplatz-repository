from unittest.mock import patch

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from coreapp.models import User
from coreapp.roles import UserRoles
from servers.models import Server
from servers.services import ServerCredentialCipher
from servers.tests.helpers import generate_private_key


SERVERS_URL = '/api/v1/servers/'


class ServerAPITests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.private_key = generate_private_key()
        cls.replacement_key = generate_private_key()

    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com', password='password',
            first_name='Admin', last_name='User', role=UserRoles.ADMIN,
        )
        self.user = User.objects.create_user(
            email='user@example.com', password='password',
            first_name='Regular', last_name='User', role=UserRoles.USER,
        )
        self.payload = {
            'name': 'Primary VPS',
            'ip_address': '192.0.2.10',
            'ssh_port': 22,
            'username': 'deploy',
            'private_key': self.private_key,
        }
        self.client.force_authenticate(self.admin)

    def create_server(self, **overrides):
        payload = {**self.payload, **overrides}
        return self.client.post(SERVERS_URL, payload, format='json')

    def test_admin_can_create_without_exposing_plaintext_or_ciphertext(self):
        response = self.create_server()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('private_key', response.data['data'])
        self.assertNotIn('encrypted_private_key', response.data['data'])
        server = Server.objects.get()
        self.assertNotEqual(server.encrypted_private_key, self.private_key)
        self.assertEqual(
            ServerCredentialCipher.decrypt(server.encrypted_private_key),
            self.private_key,
        )
        self.assertEqual(server.created_by, self.admin)
        self.assertEqual(server.updated_by, self.admin)

    def test_admin_can_generate_dedicated_key_during_creation(self):
        payload = {key: value for key, value in self.payload.items() if key != 'private_key'}
        payload['generate_key'] = True

        response = self.client.post(SERVERS_URL, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['data']['public_key'].startswith('ssh-ed25519 '))
        self.assertNotIn('private_key', response.data['data'])
        server = Server.objects.get()
        private_key = ServerCredentialCipher.decrypt(server.encrypted_private_key)
        self.assertIn('BEGIN OPENSSH PRIVATE KEY', private_key)

        listing = self.client.get(SERVERS_URL)
        detail = self.client.get(f'{SERVERS_URL}{server.id}/')
        self.assertNotIn('public_key', listing.data['data']['results'][0])
        self.assertNotIn('public_key', detail.data['data'])

    def test_create_rejects_pasted_and_generated_keys_together(self):
        response = self.create_server(generate_key=True)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('private_key', response.data['errors'])

    def test_non_admin_cannot_access_server_api(self):
        self.client.force_authenticate(self.user)
        forbidden = self.client.get(SERVERS_URL)
        self.client.force_authenticate(None)
        anonymous = self.client.get(SERVERS_URL)

        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(anonymous.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_list_and_retrieve_without_credentials(self):
        created = self.create_server()
        server_id = created.data['data']['id']

        listing = self.client.get(SERVERS_URL)
        detail = self.client.get(f'{SERVERS_URL}{server_id}/')

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data['data']['count'], 1)
        listed_server = listing.data['data']['results'][0]
        self.assertEqual(listed_server['id'], server_id)
        self.assertNotIn('private_key', listed_server)
        self.assertNotIn('encrypted_private_key', listed_server)
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertNotIn('private_key', detail.data['data'])
        self.assertNotIn('encrypted_private_key', detail.data['data'])

    def test_rejects_hostname_invalid_port_invalid_key_and_duplicate(self):
        invalid_host = self.create_server(ip_address='server.example.com')
        invalid_port = self.create_server(ssh_port=70000)
        invalid_key = self.create_server(private_key='invalid')
        created = self.create_server()
        duplicate = self.create_server(name='Duplicate')

        self.assertEqual(invalid_host.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid_port.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(invalid_key.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_preserves_or_replaces_private_key(self):
        created = self.create_server()
        server = Server.objects.get()
        original_ciphertext = server.encrypted_private_key
        detail_url = f'{SERVERS_URL}{created.data["data"]["id"]}/'

        preserved = self.client.patch(detail_url, {'name': 'Renamed'}, format='json')
        server.refresh_from_db()
        self.assertEqual(preserved.status_code, status.HTTP_200_OK)
        self.assertEqual(server.encrypted_private_key, original_ciphertext)

        replaced = self.client.patch(
            detail_url, {'private_key': self.replacement_key}, format='json'
        )
        server.refresh_from_db()
        self.assertEqual(replaced.status_code, status.HTTP_200_OK)
        self.assertNotEqual(server.encrypted_private_key, original_ciphertext)
        self.assertEqual(
            ServerCredentialCipher.decrypt(server.encrypted_private_key),
            self.replacement_key,
        )

    def test_delete_is_soft_and_hides_server_from_crud_and_connection(self):
        created = self.create_server()
        server_id = created.data['data']['id']
        detail_url = f'{SERVERS_URL}{server_id}/'

        deleted = self.client.delete(detail_url)
        detail = self.client.get(detail_url)
        connection = self.client.post(f'{detail_url}test-connection/')
        listing = self.client.get(SERVERS_URL)

        self.assertEqual(deleted.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(connection.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(listing.data['data']['count'], 0)
        server = Server.objects.get(pk=server_id)
        self.assertTrue(server.is_deleted)
        self.assertFalse(server.is_active)
        recreated = self.create_server(name='Replacement VPS')
        self.assertEqual(recreated.status_code, status.HTTP_201_CREATED)

    @patch('servers.api.views.SSHConnectionTester.test')
    def test_connection_returns_and_persists_online_or_offline_result(self, test):
        created = self.create_server()
        url = f'{SERVERS_URL}{created.data["data"]["id"]}/test-connection/'
        checked_at = timezone.now()
        test.return_value = {
            'status': 'Online', 'latency_ms': 12.5, 'checked_at': checked_at,
        }

        online = self.client.post(url)
        self.assertEqual(online.status_code, status.HTTP_200_OK)
        self.assertEqual(online.data['data']['status'], 'Online')
        server = Server.objects.get()
        self.assertEqual(server.status, Server.ConnectionStatus.ONLINE)
        self.assertEqual(server.last_latency_ms, 12.5)
        self.assertEqual(server.last_failure_reason, '')
        self.assertEqual(server.last_checked_at, checked_at)

        test.return_value = {
            'status': 'Offline', 'reason': 'timeout', 'checked_at': checked_at,
        }
        offline = self.client.post(url)
        self.assertEqual(offline.status_code, status.HTTP_200_OK)
        self.assertEqual(offline.data['data']['status'], 'Offline')
        self.assertEqual(offline.data['data']['reason'], 'timeout')
        server.refresh_from_db()
        self.assertEqual(server.status, Server.ConnectionStatus.OFFLINE)
        self.assertIsNone(server.last_latency_ms)
        self.assertEqual(server.last_failure_reason, 'timeout')
        self.assertEqual(server.last_checked_at, checked_at)
