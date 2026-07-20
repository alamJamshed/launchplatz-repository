from rest_framework import serializers

from deployments.models import Deployment, DeploymentStep
from projects.models import Project


class DeploymentStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeploymentStep
        fields = [
            'id', 'order', 'name', 'status', 'error_category', 'error_message',
            'started_at', 'completed_at', 'duration_ms',
        ]
        read_only_fields = fields


class DeploymentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deployment
        fields = [
            'id', 'project', 'trigger', 'status', 'previous_commit',
            'deployed_commit', 'rollback_status', 'rollback_error_category',
            'error_category', 'started_at', 'completed_at', 'duration_ms',
            'triggered_by', 'created_at', 'project_name_snapshot',
            'server_name_snapshot', 'server_ip_snapshot', 'branch_snapshot',
            'repository_url_snapshot', 'triggered_by_email_snapshot',
        ]
        read_only_fields = fields


class DeploymentSerializer(DeploymentListSerializer):
    steps = DeploymentStepSerializer(many=True, read_only=True)

    class Meta(DeploymentListSerializer.Meta):
        fields = DeploymentListSerializer.Meta.fields + [
            'cancel_requested_at', 'cancel_requested_by',
            'cancel_requested_by_email_snapshot',
            'error_message', 'steps',
        ]
        read_only_fields = fields


class DeploymentFilterSerializer(serializers.Serializer):
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False,
    )
    status = serializers.ChoiceField(
        choices=Deployment.Status.choices, required=False
    )
    ordering = serializers.ChoiceField(
        choices=['newest', 'oldest'], required=False, default='newest'
    )
