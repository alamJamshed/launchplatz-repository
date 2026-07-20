from cryptography.fernet import Fernet
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class EnvironmentVariableMigrationTests(TransactionTestCase):
    migrate_from = ('projects', '0002_project_current_branch_project_current_commit_and_more')
    migrate_to = ('projects', '0003_remove_project_environment_variables_and_more')

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        Server = old_apps.get_model('servers', 'Server')
        Project = old_apps.get_model('projects', 'Project')
        server = Server.objects.create(
            name='Migration VPS', ip_address='192.0.2.30', username='deploy',
            encrypted_private_key='encrypted',
        )
        Project.objects.create(
            server_id=server.pk, name='Migrated Project',
            git_repository_url='https://github.com/example/project.git',
            environment_variables={'DEBUG': 'False', 'EMPTY': ''},
        )
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        )
        super().tearDown()

    def test_plain_json_values_are_encrypted_into_records(self):
        EnvironmentVariable = self.apps.get_model(
            'projects', 'EnvironmentVariable'
        )
        variables = {
            row.key: row.encrypted_value
            for row in EnvironmentVariable.objects.order_by('key')
        }
        cipher = Fernet(settings.ENVIRONMENT_VARIABLE_ENCRYPTION_KEY.encode())
        self.assertEqual(set(variables), {'DEBUG', 'EMPTY'})
        self.assertEqual(cipher.decrypt(variables['DEBUG'].encode()).decode(), 'False')
        self.assertEqual(cipher.decrypt(variables['EMPTY'].encode()).decode(), '')
        self.assertNotIn('False', variables['DEBUG'])
