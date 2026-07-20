from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from coreapp.models import User
from projects.api.serializers import ProjectSerializer
from projects.models import Project
from projects.validators import (
    normalize_and_validate_domain,
    validate_docker_compose_path,
    validate_git_repository_url,
)


class ProjectValidatorUnitTests(SimpleTestCase):
    def test_accepts_supported_git_url_shapes(self):
        for value in [
            'https://github.com/example/project.git',
            'ssh://git@github.com/example/project.git',
            'git@github.com:example/project.git',
        ]:
            with self.subTest(value=value):
                self.assertIsNone(validate_git_repository_url(value))

    def test_rejects_unsupported_or_credentialed_git_urls(self):
        for value in [
            'http://github.com/example/project.git',
            'https://user:password@github.com/example/project.git',
            'github.com/example/project',
            'https://github.com/',
            'https://github.com/example/project.git?token=secret',
        ]:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_git_repository_url(value)

    def test_normalizes_domain_and_rejects_url_or_port(self):
        self.assertEqual(
            normalize_and_validate_domain('App.Example.COM.'),
            'app.example.com',
        )
        self.assertEqual(normalize_and_validate_domain(''), '')
        for value in ['https://example.com', 'example.com/path', 'example.com:8000']:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    normalize_and_validate_domain(value)

    def test_requires_safe_relative_compose_path(self):
        for value in ['docker-compose.yml', 'deploy/compose.yaml']:
            with self.subTest(value=value):
                self.assertIsNone(validate_docker_compose_path(value))
        for value in [
            '/etc/docker-compose.yml', '../docker-compose.yml',
            'deploy/../../compose.yml', 'deploy\\compose.yml', 'deploy/',
        ]:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_docker_compose_path(value)

class ProjectModelAndSerializerUnitTests(SimpleTestCase):
    def test_framework_is_fixed_and_read_only(self):
        serializer = ProjectSerializer()

        self.assertTrue(serializer.fields['framework'].read_only)
        self.assertEqual(
            Project._meta.get_field('framework').default,
            Project.Framework.DJANGO_REACT,
        )

    @patch('projects.models.timezone.now')
    def test_archive_and_restore_are_idempotent(self, now):
        archived_at = Mock()
        now.return_value = archived_at
        project = Project(name='Project')
        project.save = Mock()
        user = User(email='admin@example.com')

        project.archive(user)
        project.archive(user)

        self.assertTrue(project.is_archived)
        self.assertIs(project.archived_at, archived_at)
        self.assertIs(project.archived_by, user)
        self.assertEqual(project.save.call_count, 1)

        project.restore(user)
        project.restore(user)

        self.assertFalse(project.is_archived)
        self.assertIsNone(project.archived_at)
        self.assertIsNone(project.archived_by)
        self.assertEqual(project.save.call_count, 2)

    def test_serializer_rejects_inactive_or_deleted_server(self):
        serializer = ProjectSerializer()
        for server in [
            SimpleNamespace(is_active=False, is_deleted=False),
            SimpleNamespace(is_active=True, is_deleted=True),
        ]:
            with self.subTest(server=server):
                with self.assertRaisesMessage(
                    Exception, 'Select an active, non-deleted server.'
                ):
                    serializer.validate({'server': server})
