import socket
from types import SimpleNamespace
from unittest.mock import Mock, patch

import paramiko
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import SimpleTestCase, override_settings
from rest_framework import serializers

from coreapp.models import User
from servers.api.serializers import ServerSerializer
from servers.models import Server
from servers.services import (
    SSHKeyPairGenerator,
    SSHConnectionTester,
    SSHKeyParser,
    ServerCredentialCipher,
)
from servers.tests.helpers import generate_private_key


TEST_FERNET_KEY = 'MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA='


class SSHKeyPairGeneratorUnitTests(SimpleTestCase):
    def test_generates_matching_parseable_ed25519_pair(self):
        private_key, public_key = SSHKeyPairGenerator.generate()

        parsed = SSHKeyParser.parse(private_key)
        self.assertIsInstance(parsed, paramiko.Ed25519Key)
        self.assertTrue(public_key.startswith('ssh-ed25519 '))
        self.assertTrue(public_key.endswith(' launchplatz'))


class ServerCredentialCipherUnitTests(SimpleTestCase):
    @override_settings(SERVER_CREDENTIAL_ENCRYPTION_KEY=TEST_FERNET_KEY)
    def test_encrypts_and_decrypts_without_storing_plaintext(self):
        plaintext = 'private-key-value'

        encrypted = ServerCredentialCipher.encrypt(plaintext)

        self.assertNotEqual(encrypted, plaintext)
        self.assertEqual(ServerCredentialCipher.decrypt(encrypted), plaintext)

    @override_settings(SERVER_CREDENTIAL_ENCRYPTION_KEY=None)
    def test_requires_configured_encryption_key(self):
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            'SERVER_CREDENTIAL_ENCRYPTION_KEY must be configured.',
        ):
            ServerCredentialCipher.encrypt('private-key-value')

    @override_settings(SERVER_CREDENTIAL_ENCRYPTION_KEY=TEST_FERNET_KEY)
    def test_rejects_tampered_ciphertext(self):
        with self.assertRaisesMessage(
            ValidationError, 'Stored server credential could not be decrypted.'
        ):
            ServerCredentialCipher.decrypt('tampered')


class SSHKeyParserUnitTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.private_key = generate_private_key()

    def test_parses_supported_unencrypted_key(self):
        parsed = SSHKeyParser.parse(self.private_key)

        self.assertIsInstance(parsed, paramiko.RSAKey)

    def test_rejects_invalid_key(self):
        with self.assertRaisesMessage(
            ValidationError,
            'Private key must be a valid RSA, ECDSA, or Ed25519 key.',
        ):
            SSHKeyParser.parse('not-a-private-key')


class ServerValidationUnitTests(SimpleTestCase):
    def test_rejects_hostname_and_out_of_range_port(self):
        ip_field = ServerSerializer().fields['ip_address']
        serializer = ServerSerializer()

        with self.assertRaises(serializers.ValidationError):
            ip_field.run_validation('server.example.com')
        with self.assertRaises(serializers.ValidationError):
            serializer.validate_ssh_port(0)
        with self.assertRaises(serializers.ValidationError):
            serializer.validate_ssh_port(65536)

    def test_soft_delete_sets_flags_and_audit_user(self):
        server = Server(
            name='Primary', ip_address='192.0.2.10', username='deploy',
            encrypted_private_key='encrypted',
        )
        server.save = Mock()
        user = User(email='admin@example.com')

        server.soft_delete(user)

        self.assertTrue(server.is_deleted)
        self.assertFalse(server.is_active)
        self.assertIs(server.updated_by, user)
        server.save.assert_called_once_with(
            update_fields=['is_deleted', 'is_active', 'updated_by', 'updated_at']
        )

    def test_records_online_and_offline_connection_results(self):
        server = Server(
            name='Primary', ip_address='192.0.2.10', username='deploy',
            encrypted_private_key='encrypted',
        )
        server.save = Mock()
        user = User(email='admin@example.com')
        checked_at = Mock()

        server.record_connection_result(
            {
                'status': 'Online', 'latency_ms': 12.5,
                'checked_at': checked_at,
            },
            user,
        )
        self.assertEqual(server.status, Server.ConnectionStatus.ONLINE)
        self.assertEqual(server.last_latency_ms, 12.5)
        self.assertEqual(server.last_failure_reason, '')
        self.assertIs(server.last_checked_at, checked_at)

        server.record_connection_result(
            {
                'status': 'Offline', 'reason': 'timeout',
                'checked_at': checked_at,
            },
            user,
        )
        self.assertEqual(server.status, Server.ConnectionStatus.OFFLINE)
        self.assertIsNone(server.last_latency_ms)
        self.assertEqual(server.last_failure_reason, 'timeout')
        self.assertEqual(server.save.call_count, 2)


@override_settings(
    SERVER_CREDENTIAL_ENCRYPTION_KEY=TEST_FERNET_KEY,
    SSH_CONNECTION_TIMEOUT=30,
)
class SSHConnectionTesterUnitTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        private_key = generate_private_key()
        cls.server = SimpleNamespace(
            ip_address='192.0.2.10',
            ssh_port=22,
            username='deploy',
            encrypted_private_key=ServerCredentialCipher.encrypt(private_key),
        )

    @patch('servers.services.paramiko.SSHClient')
    def test_maps_success_and_uses_configured_timeout(self, ssh_client_class):
        client = ssh_client_class.return_value

        result = SSHConnectionTester.test(self.server)

        self.assertEqual(result['status'], 'Online')
        self.assertIn('latency_ms', result)
        policy = client.set_missing_host_key_policy.call_args.args[0]
        self.assertIsInstance(policy, paramiko.AutoAddPolicy)
        client.connect.assert_called_once()
        kwargs = client.connect.call_args.kwargs
        self.assertEqual(kwargs['timeout'], 30)
        self.assertEqual(kwargs['banner_timeout'], 30)
        self.assertEqual(kwargs['auth_timeout'], 30)
        self.assertFalse(kwargs['look_for_keys'])
        self.assertFalse(kwargs['allow_agent'])
        client.close.assert_called_once()

    @patch('servers.services.paramiko.SSHClient')
    def test_maps_authentication_failure_without_raw_exception(self, ssh_client_class):
        ssh_client_class.return_value.connect.side_effect = (
            paramiko.AuthenticationException('sensitive remote detail')
        )

        result = SSHConnectionTester.test(self.server)

        self.assertEqual(
            result, {
                'status': 'Offline',
                'reason': 'authentication_failed',
                'checked_at': result['checked_at'],
            }
        )
        self.assertNotIn('sensitive remote detail', str(result))

    @patch('servers.services.paramiko.SSHClient')
    def test_maps_timeout_and_unreachable_host(self, ssh_client_class):
        client = ssh_client_class.return_value
        for exception, reason in [
            (socket.timeout(), 'timeout'),
            (OSError('network detail'), 'host_unreachable'),
        ]:
            with self.subTest(reason=reason):
                client.connect.side_effect = exception
                result = SSHConnectionTester.test(self.server)
                self.assertEqual(result['status'], 'Offline')
                self.assertEqual(result['reason'], reason)
