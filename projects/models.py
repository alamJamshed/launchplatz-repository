from django.conf import settings
from django.db import models
from django.utils import timezone

from coreapp.base import BaseModel
from servers.models import Server

from .validators import (
    validate_docker_compose_path,
    validate_git_repository_url,
    validate_environment_variable_key,
    validate_compose_service_name,
)


class Project(BaseModel):
    class Framework(models.TextChoices):
        DJANGO_REACT = 'django_react', 'Django + React'

    server = models.ForeignKey(
        Server, on_delete=models.PROTECT, related_name='projects'
    )
    name = models.CharField(max_length=150, unique=True)
    framework = models.CharField(
        max_length=30,
        choices=Framework.choices,
        default=Framework.DJANGO_REACT,
    )
    git_repository_url = models.CharField(
        max_length=500, validators=[validate_git_repository_url]
    )
    branch = models.CharField(max_length=255, default='main')
    domain = models.CharField(max_length=253, blank=True)
    docker_compose_path = models.CharField(
        max_length=500,
        default='docker-compose.yml',
        validators=[validate_docker_compose_path],
    )
    django_service_name = models.CharField(
        max_length=100, default='backend', validators=[validate_compose_service_name]
    )
    encrypted_git_private_key = models.TextField(blank=True)
    git_cloned_at = models.DateTimeField(null=True, blank=True)
    current_branch = models.CharField(max_length=255, blank=True)
    current_commit = models.CharField(max_length=64, blank=True)
    last_git_synced_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='projects_archived',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def archive(self, user=None):
        if self.is_archived:
            return
        self.is_archived = True
        self.archived_at = timezone.now()
        self.archived_by = user
        self.updated_by = user
        self.save(
            update_fields=[
                'is_archived', 'archived_at', 'archived_by',
                'updated_by', 'updated_at',
            ]
        )

    def restore(self, user=None):
        if not self.is_archived:
            return
        self.is_archived = False
        self.archived_at = None
        self.archived_by = None
        self.updated_by = user
        self.save(
            update_fields=[
                'is_archived', 'archived_at', 'archived_by',
                'updated_by', 'updated_at',
            ]
        )

    def record_git_state(self, branch, commit_hash, cloned=False, user=None):
        now = timezone.now()
        self.current_branch = branch
        self.current_commit = commit_hash
        self.last_git_synced_at = now
        self.updated_by = user
        fields = [
            'current_branch', 'current_commit', 'last_git_synced_at',
            'updated_by', 'updated_at',
        ]
        if cloned and self.git_cloned_at is None:
            self.git_cloned_at = now
            fields.append('git_cloned_at')
        self.save(update_fields=fields)


class GitOperation(models.Model):
    class Action(models.TextChoices):
        CLONE = 'clone', 'Clone'
        PULL = 'pull', 'Pull'
        CURRENT_COMMIT = 'current_commit', 'Current commit'
        LIST_BRANCHES = 'list_branches', 'List branches'
        SELECT_BRANCH = 'select_branch', 'Select branch'

    class Status(models.TextChoices):
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='git_operations'
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    status = models.CharField(max_length=10, choices=Status.choices)
    output = models.TextField(blank=True)
    error_category = models.CharField(max_length=50, blank=True)
    commit_hash = models.CharField(max_length=64, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField()
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='git_operations',
    )

    class Meta:
        ordering = ['-started_at']


class EnvironmentVariable(BaseModel):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='environment_variables'
    )
    key = models.CharField(max_length=255, validators=[validate_environment_variable_key])
    encrypted_value = models.TextField()
    is_secret = models.BooleanField(default=False)

    class Meta:
        ordering = ['key']
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'key'], name='unique_project_environment_key'
            )
        ]

    def __str__(self):
        return f'{self.project_id}:{self.key}'
