from django.db import models
from django.db.models import Q

from coreapp.base import BaseModel


class Server(BaseModel):
    class ConnectionStatus(models.TextChoices):
        UNKNOWN = 'Unknown', 'Unknown'
        ONLINE = 'Online', 'Online'
        OFFLINE = 'Offline', 'Offline'

    name = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField(protocol='both', unpack_ipv4=False)
    ssh_port = models.PositiveIntegerField(default=22)
    username = models.CharField(max_length=100)
    encrypted_private_key = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=ConnectionStatus.choices,
        default=ConnectionStatus.UNKNOWN,
    )
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_latency_ms = models.FloatField(null=True, blank=True)
    last_failure_reason = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['ip_address', 'ssh_port', 'username'],
                condition=Q(is_deleted=False),
                name='unique_active_server_endpoint',
            ),
            models.CheckConstraint(
                condition=Q(ssh_port__gte=1, ssh_port__lte=65535),
                name='valid_server_ssh_port',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.username}@{self.ip_address}:{self.ssh_port})'

    def soft_delete(self, user=None):
        self.is_deleted = True
        self.is_active = False
        self.updated_by = user
        self.save(
            update_fields=['is_deleted', 'is_active', 'updated_by', 'updated_at']
        )

    def record_connection_result(self, result, user=None):
        self.status = result['status']
        self.last_checked_at = result['checked_at']
        self.updated_by = user
        if self.status == self.ConnectionStatus.ONLINE:
            self.last_latency_ms = result.get('latency_ms')
            self.last_failure_reason = ''
        else:
            self.last_latency_ms = None
            self.last_failure_reason = result.get('reason', 'ssh_error')
        self.save(
            update_fields=[
                'status', 'last_checked_at', 'last_latency_ms',
                'last_failure_reason', 'updated_by', 'updated_at',
            ]
        )
