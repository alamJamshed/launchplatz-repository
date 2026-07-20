from tempfile import TemporaryDirectory
from pathlib import Path

from cryptography.fernet import Fernet
from django.test import SimpleTestCase

from scripts.setup_docker_env import generate_values, write_environment


class DockerEnvironmentSetupTests(SimpleTestCase):
    FERNET_FIELDS = (
        'SMTP_ENCRYPTION_KEY',
        'SERVER_CREDENTIAL_ENCRYPTION_KEY',
        'GIT_CREDENTIAL_ENCRYPTION_KEY',
        'ENVIRONMENT_VARIABLE_ENCRYPTION_KEY',
    )

    def test_generates_required_distinct_valid_keys_and_container_hosts(self):
        values = generate_values()

        self.assertEqual(values['DB_HOST'], 'db')
        self.assertEqual(values['CELERY_BROKER_URL'], 'redis://redis:6379/0')
        self.assertEqual(values['DB_PASSWORD'], values['POSTGRES_PASSWORD'])
        keys = [values[field] for field in self.FERNET_FIELDS]
        self.assertEqual(len(set(keys)), len(keys))
        for key in keys:
            Fernet(key.encode())

    def test_existing_environment_is_preserved_without_force(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / '.env.docker'
            output.write_text('ORIGINAL=true\n', encoding='utf-8')

            self.assertFalse(write_environment(output))
            self.assertEqual(output.read_text(encoding='utf-8'), 'ORIGINAL=true\n')

    def test_force_replaces_existing_environment(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / '.env.docker'
            output.write_text('ORIGINAL=true\n', encoding='utf-8')

            self.assertTrue(write_environment(output, force=True))
            content = output.read_text(encoding='utf-8')
            self.assertIn('DJANGO_ENV=development\n', content)
            self.assertNotIn('ORIGINAL=true', content)
