from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import SimpleTestCase, override_settings

from projects.environment_services import (
    EnvironmentCredentialCipher,
    EnvironmentOperationError,
    RemoteEnvironmentService,
    quote_dotenv_value,
    serialize_dotenv,
)
from projects.validators import validate_environment_variable_key


TEST_KEY = 'MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjI='


class EnvironmentVariableUnitTests(SimpleTestCase):
    @override_settings(ENVIRONMENT_VARIABLE_ENCRYPTION_KEY=TEST_KEY)
    def test_cipher_round_trip_and_ciphertext_secrecy(self):
        encrypted = EnvironmentCredentialCipher.encrypt('super-secret')
        self.assertNotIn('super-secret', encrypted)
        self.assertEqual(EnvironmentCredentialCipher.decrypt(encrypted), 'super-secret')

    @override_settings(ENVIRONMENT_VARIABLE_ENCRYPTION_KEY=None)
    def test_cipher_requires_key(self):
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            'ENVIRONMENT_VARIABLE_ENCRYPTION_KEY must be configured.',
        ):
            EnvironmentCredentialCipher.encrypt('value')

    def test_portable_key_validation(self):
        for key in ['DEBUG', '_INTERNAL', 'DATABASE_URL', 'PORT_2']:
            self.assertIsNone(validate_environment_variable_key(key))
        for key in ['', 'debug', '2_PORT', 'HAS-DASH', 'HAS SPACE']:
            with self.subTest(key=key), self.assertRaises(ValidationError):
                validate_environment_variable_key(key)

    @override_settings(ENVIRONMENT_VARIABLE_ENCRYPTION_KEY=TEST_KEY)
    def test_dotenv_serialization_is_sorted_and_escaped(self):
        variables = [
            SimpleNamespace(
                key='MULTILINE',
                encrypted_value=EnvironmentCredentialCipher.encrypt('one\ntwo"$\\'),
            ),
            SimpleNamespace(
                key='EMPTY', encrypted_value=EnvironmentCredentialCipher.encrypt('')
            ),
        ]
        self.assertEqual(quote_dotenv_value('a\nb'), '"a\\nb"')
        self.assertEqual(
            serialize_dotenv(variables),
            b'EMPTY=""\nMULTILINE="one\\ntwo\\"\\$\\\\"\n',
        )

    @override_settings(ENVIRONMENT_VARIABLE_ENCRYPTION_KEY=TEST_KEY)
    def test_remote_generation_uses_temp_file_mode_and_atomic_rename(self):
        project = SimpleNamespace(pk=7)
        service = RemoteEnvironmentService(project)
        service.workspace = '/home/deploy/launchplatz/projects/7'
        service.sftp = MagicMock()
        file_handle = Mock()
        service.sftp.file.return_value.__enter__.return_value = file_handle
        variables = [SimpleNamespace(
            key='DEBUG', encrypted_value=EnvironmentCredentialCipher.encrypt('False')
        )]

        result = service.generate(variables)

        temporary = service.sftp.file.call_args.args[0]
        self.assertTrue(temporary.startswith(service.workspace + '/.env.tmp-'))
        file_handle.write.assert_called_once_with(b'DEBUG="False"\n')
        service.sftp.chmod.assert_called_once_with(temporary, 0o600)
        service.sftp.posix_rename.assert_called_once_with(
            temporary, service.workspace + '/.env'
        )
        self.assertEqual(result['variable_count'], 1)

    def test_missing_workspace_is_categorized(self):
        service = RemoteEnvironmentService(SimpleNamespace(pk=1))
        service.workspace = '/workspace'
        service.sftp = Mock()
        service.sftp.stat.side_effect = OSError(2, 'missing')
        with self.assertRaises(EnvironmentOperationError) as raised:
            service._require_workspace()
        self.assertEqual(raised.exception.category, 'repository_not_cloned')
