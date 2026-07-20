from django.conf import settings
from django.db import models
from django.db.models import Q

from projects.models import Project


class Deployment(models.Model):
    class Trigger(models.TextChoices):
        DEPLOY = 'deploy', 'Deploy'
        REDEPLOY = 'redeploy', 'Redeploy'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        CANCELLING = 'cancelling', 'Cancelling'
        CANCELLED = 'cancelled', 'Cancelled'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'

    class RollbackStatus(models.TextChoices):
        NOT_REQUIRED = 'not_required', 'Not required'
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'

    ACTIVE_STATUSES = (Status.PENDING, Status.RUNNING, Status.CANCELLING)

    project = models.ForeignKey(
        Project, on_delete=models.PROTECT, related_name='deployments'
    )
    trigger = models.CharField(max_length=10, choices=Trigger.choices)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    celery_task_id = models.CharField(max_length=255, blank=True)
    previous_commit = models.CharField(max_length=64, blank=True)
    deployed_commit = models.CharField(max_length=64, blank=True)
    project_name_snapshot = models.CharField(max_length=150, blank=True)
    server_name_snapshot = models.CharField(max_length=150, blank=True)
    server_ip_snapshot = models.CharField(max_length=45, blank=True)
    branch_snapshot = models.CharField(max_length=255, blank=True)
    repository_url_snapshot = models.CharField(max_length=500, blank=True)
    triggered_by_email_snapshot = models.EmailField(blank=True)
    cancel_requested_at = models.DateTimeField(null=True, blank=True)
    cancel_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deployments_cancelled',
    )
    cancel_requested_by_email_snapshot = models.EmailField(blank=True)
    rollback_status = models.CharField(
        max_length=15,
        choices=RollbackStatus.choices,
        default=RollbackStatus.NOT_REQUIRED,
    )
    rollback_error_category = models.CharField(max_length=50, blank=True)
    error_category = models.CharField(max_length=50, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveBigIntegerField(default=0)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='deployments_triggered',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['project'],
                condition=Q(status__in=['pending', 'running', 'cancelling']),
                name='unique_active_project_deployment',
            )
        ]
        indexes = [
            models.Index(
                fields=['project', '-created_at'], name='deploy_proj_created_idx'
            ),
            models.Index(
                fields=['status', '-created_at'], name='deploy_status_created_idx'
            ),
        ]


class DeploymentStep(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
        SKIPPED = 'skipped', 'Skipped'

    deployment = models.ForeignKey(
        Deployment, on_delete=models.CASCADE, related_name='steps'
    )
    order = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=50)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    error_category = models.CharField(max_length=50, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveBigIntegerField(default=0)

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(
                fields=['deployment', 'order'], name='unique_deployment_step_order'
            )
        ]


DEPLOYMENT_STATUS_CHOICES = Deployment.Status.choices
