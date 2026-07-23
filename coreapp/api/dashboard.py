from django.db.models import Count
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.views import APIView

from coreapp.permissions import IsAdmin
from coreapp.utils.responses import APIResponse
from deployments.api.serializers import DeploymentListSerializer
from deployments.models import Deployment
from projects.models import Project
from servers.models import Server


class StatusCountsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    pending = serializers.IntegerField(required=False)
    running = serializers.IntegerField(required=False)
    cancelling = serializers.IntegerField(required=False)
    cancelled = serializers.IntegerField(required=False)
    success = serializers.IntegerField(required=False)
    failed = serializers.IntegerField(required=False)
    online = serializers.IntegerField(required=False)
    offline = serializers.IntegerField(required=False)
    unknown = serializers.IntegerField(required=False)
    active = serializers.IntegerField(required=False)
    archived = serializers.IntegerField(required=False)


class DashboardSerializer(serializers.Serializer):
    servers = StatusCountsSerializer()
    projects = StatusCountsSerializer()
    deployments = StatusCountsSerializer()
    recent_deployments = DeploymentListSerializer(many=True)


def _counts(queryset, field):
    return {
        row[field]: row['count']
        for row in queryset.values(field).annotate(count=Count('id'))
    }


class DashboardView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses={200: DashboardSerializer})
    def get(self, request):
        servers = Server.objects.filter(is_active=True, is_deleted=False)
        server_counts = _counts(servers, 'status')
        projects = Project.objects.filter(is_active=True, is_deleted=False)
        deployments = Deployment.objects.all()
        deployment_counts = _counts(deployments, 'status')

        data = {
            'servers': {
                'total': servers.count(),
                'online': server_counts.get(Server.ConnectionStatus.ONLINE, 0),
                'offline': server_counts.get(Server.ConnectionStatus.OFFLINE, 0),
                'unknown': server_counts.get(Server.ConnectionStatus.UNKNOWN, 0),
            },
            'projects': {
                'total': projects.count(),
                'active': projects.filter(is_archived=False).count(),
                'archived': projects.filter(is_archived=True).count(),
            },
            'deployments': {
                'total': deployments.count(),
                **{
                    status: deployment_counts.get(status, 0)
                    for status, _ in Deployment.Status.choices
                },
            },
            'recent_deployments': DeploymentListSerializer(
                deployments.select_related('project', 'triggered_by')[:5], many=True
            ).data,
        }
        return APIResponse.success(data, 'Dashboard retrieved successfully')
