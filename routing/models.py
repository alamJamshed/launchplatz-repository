from django.db import models
from django.db.models import Q

from coreapp.base import BaseModel
from projects.models import Project
from servers.models import Server

from .validators import normalize_hostname, validate_service_name


class Domain(BaseModel):
    class DNSStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        VERIFIED = 'verified', 'Verified'
        FAILED = 'failed', 'Failed'

    project = models.OneToOneField(
        Project, on_delete=models.CASCADE, related_name='routing_domain'
    )
    hostname = models.CharField(max_length=253)
    normalized_hostname = models.CharField(max_length=253, unique=True)
    dns_status = models.CharField(
        max_length=10, choices=DNSStatus.choices, default=DNSStatus.PENDING
    )
    dns_last_checked_at = models.DateTimeField(null=True, blank=True)
    resolved_addresses = models.JSONField(default=list, blank=True)
    dns_error = models.CharField(max_length=500, blank=True)
    consecutive_dns_successes = models.PositiveSmallIntegerField(default=0)

    def clean(self):
        super().clean()
        self.normalized_hostname = normalize_hostname(self.hostname)

    def save(self, *args, **kwargs):
        self.normalized_hostname = normalize_hostname(self.hostname)
        super().save(*args, **kwargs)


class Route(BaseModel):
    class ObservedStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIGURED = 'configured', 'Configured'
        HEALTHY = 'healthy', 'Healthy'
        FAILED = 'failed', 'Failed'
        DISABLED = 'disabled', 'Disabled'

    domain = models.OneToOneField(
        Domain, on_delete=models.CASCADE, related_name='route'
    )
    service_name = models.CharField(max_length=100, validators=[validate_service_name])
    internal_port = models.PositiveIntegerField()
    desired_enabled = models.BooleanField(default=True)
    tls_enabled = models.BooleanField(default=False)
    observed_status = models.CharField(
        max_length=12,
        choices=ObservedStatus.choices,
        default=ObservedStatus.PENDING,
    )
    configuration_revision = models.CharField(max_length=64, blank=True)
    last_reconciled_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    lease_owner = models.CharField(max_length=64, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(internal_port__gte=1, internal_port__lte=65535),
                name='routing_valid_internal_port',
            )
        ]


class ReconciliationEvent(models.Model):
    route = models.ForeignKey(
        Route, on_delete=models.CASCADE, related_name='reconciliation_events'
    )
    status = models.CharField(max_length=12, choices=Route.ObservedStatus.choices)
    revision = models.CharField(max_length=64, blank=True)
    error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ServerRoutingLease(models.Model):
    server = models.OneToOneField(
        Server, on_delete=models.CASCADE, related_name='routing_lease'
    )
    owner = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
