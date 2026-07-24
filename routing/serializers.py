from django.db import IntegrityError, transaction
from rest_framework import serializers

from projects.models import Project

from .models import Domain, ReconciliationEvent, Route
from .validators import normalize_hostname


class ReconciliationEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReconciliationEvent
        fields = ['id', 'status', 'revision', 'error', 'created_at']
        read_only_fields = fields


class RouteSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.filter(is_active=True, is_deleted=False),
        source='domain.project',
        write_only=True,
    )
    project_id = serializers.IntegerField(source='domain.project_id', read_only=True)
    hostname = serializers.CharField(source='domain.hostname', max_length=253)
    normalized_hostname = serializers.CharField(
        source='domain.normalized_hostname', read_only=True
    )
    dns_status = serializers.CharField(source='domain.dns_status', read_only=True)
    dns_last_checked_at = serializers.DateTimeField(
        source='domain.dns_last_checked_at', read_only=True
    )
    resolved_addresses = serializers.ListField(
        source='domain.resolved_addresses',
        child=serializers.CharField(),
        read_only=True,
    )
    dns_error = serializers.CharField(source='domain.dns_error', read_only=True)
    expected_address = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = [
            'id', 'project', 'project_id', 'hostname', 'normalized_hostname',
            'service_name', 'internal_port', 'desired_enabled', 'tls_enabled',
            'dns_status', 'dns_last_checked_at', 'resolved_addresses',
            'dns_error', 'expected_address', 'observed_status',
            'configuration_revision', 'last_reconciled_at', 'last_error',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'observed_status', 'configuration_revision',
            'last_reconciled_at', 'last_error', 'created_at', 'updated_at',
        ]

    def get_expected_address(self, obj):
        return str(obj.domain.project.server.ip_address)

    def validate_hostname(self, value):
        return normalize_hostname(value)

    def validate_internal_port(self, value):
        if not 1 <= value <= 65535:
            raise serializers.ValidationError('Port must be between 1 and 65535.')
        return value

    def validate(self, attrs):
        domain_data = attrs.get('domain', {})
        project = domain_data.get('project') or (
            self.instance.domain.project if self.instance else None
        )
        if project and project.is_archived:
            raise serializers.ValidationError(
                {'project': 'Archived projects cannot change routing.'}
            )
        if self.instance and 'project' in domain_data:
            if project.pk != self.instance.domain.project_id:
                raise serializers.ValidationError(
                    {'project': 'A route cannot be moved to another project.'}
                )
        if attrs.get('tls_enabled') and (
            not self.instance
            or self.instance.domain.dns_status != Domain.DNSStatus.VERIFIED
        ):
            raise serializers.ValidationError(
                {'tls_enabled': 'Verify DNS before enabling test HTTPS.'}
            )
        return attrs

    def create(self, validated_data):
        domain_data = validated_data.pop('domain')
        project = domain_data['project']
        hostname = domain_data['hostname']
        request = self.context.get('request')
        try:
            with transaction.atomic():
                domain = Domain.objects.create(
                    project=project,
                    hostname=hostname,
                    created_by=request.user if request else None,
                    updated_by=request.user if request else None,
                )
                return Route.objects.create(
                    domain=domain,
                    created_by=request.user if request else None,
                    updated_by=request.user if request else None,
                    **validated_data,
                )
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {'hostname': 'This hostname or project already has a route.'}
            ) from exc

    def update(self, instance, validated_data):
        domain_data = validated_data.pop('domain', {})
        if 'hostname' in domain_data:
            instance.domain.hostname = domain_data['hostname']
            instance.domain.dns_status = Domain.DNSStatus.PENDING
            instance.domain.consecutive_dns_successes = 0
            instance.domain.resolved_addresses = []
            instance.domain.dns_error = ''
            try:
                instance.domain.save()
            except IntegrityError as exc:
                raise serializers.ValidationError(
                    {'hostname': 'This hostname is already in use.'}
                ) from exc
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.observed_status = Route.ObservedStatus.PENDING
        instance.configuration_revision = ''
        request = self.context.get('request')
        instance.updated_by = request.user if request else None
        instance.save()
        return instance


class RouteReconcileSerializer(serializers.Serializer):
    queued = serializers.BooleanField()
