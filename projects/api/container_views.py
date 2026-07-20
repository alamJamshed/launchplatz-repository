from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from containers.services import ContainerOperationError, RemoteContainerService
from coreapp.permissions import IsAdmin
from coreapp.utils.responses import APIResponse
from deployments.models import Deployment
from projects.models import Project

from .container_serializers import (
    ContainerLogQuerySerializer,
    ContainerLogsSerializer,
    ContainerStatusSerializer,
)


class ContainerBaseView(APIView):
    permission_classes = [IsAdmin]

    def project(self, project_id):
        return get_object_or_404(
            Project.objects.select_related('server'),
            pk=project_id, is_active=True, is_deleted=False,
        )

    @staticmethod
    def mutation_error(project):
        if project.is_archived:
            return APIResponse.error(
                'Archived projects cannot change containers.',
                {'category': 'project_archived'}, 409,
            )
        if project.deployments.filter(status__in=Deployment.ACTIVE_STATUSES).exists():
            return APIResponse.error(
                'Containers cannot be changed during an active deployment.',
                {'category': 'deployment_in_progress'}, 409,
            )
        return None

    @staticmethod
    def execute(project, callback):
        try:
            with RemoteContainerService(project) as service:
                return callback(service)
        except ContainerOperationError as exc:
            return APIResponse.error(
                exc.message, {'category': exc.category}, exc.status_code
            )


class ContainerListView(ContainerBaseView):
    @extend_schema(responses={200: ContainerStatusSerializer(many=True)})
    def get(self, request, project_id):
        project = self.project(project_id)
        result = self.execute(project, lambda service: service.list())
        if hasattr(result, 'status_code'):
            return result
        return APIResponse.success(result, 'Containers retrieved successfully')


class ContainerDetailView(ContainerBaseView):
    @extend_schema(responses={200: ContainerStatusSerializer})
    def get(self, request, project_id, service):
        project = self.project(project_id)
        result = self.execute(project, lambda remote: remote.detail(service))
        if hasattr(result, 'status_code'):
            return result
        return APIResponse.success(result, 'Container retrieved successfully')

    @extend_schema(responses={200: ContainerStatusSerializer})
    def delete(self, request, project_id, service):
        project = self.project(project_id)
        blocked = self.mutation_error(project)
        if blocked:
            return blocked
        result = self.execute(project, lambda remote: remote.remove(service))
        if hasattr(result, 'status_code'):
            return result
        return APIResponse.success(result, 'Container removed successfully')


class ContainerActionView(ContainerBaseView):
    action_name = None

    @extend_schema(request=None, responses={200: ContainerStatusSerializer})
    def post(self, request, project_id, service):
        project = self.project(project_id)
        blocked = self.mutation_error(project)
        if blocked:
            return blocked
        result = self.execute(
            project, lambda remote: getattr(remote, self.action_name)(service)
        )
        if hasattr(result, 'status_code'):
            return result
        return APIResponse.success(
            result, f'Container {self.action_name} completed successfully'
        )


class ContainerStartView(ContainerActionView):
    action_name = 'start'


class ContainerStopView(ContainerActionView):
    action_name = 'stop'


class ContainerRestartView(ContainerActionView):
    action_name = 'restart'


class ContainerLogsView(ContainerBaseView):
    @extend_schema(
        parameters=[ContainerLogQuerySerializer],
        responses={200: ContainerLogsSerializer},
    )
    def get(self, request, project_id, service):
        query = ContainerLogQuerySerializer(
            data=request.query_params,
            context={'maximum': getattr(settings, 'DOCKER_LOG_MAX_LINES', 1000)},
        )
        query.is_valid(raise_exception=True)
        project = self.project(project_id)
        result = self.execute(
            project,
            lambda remote: remote.logs(service, query.validated_data['tail']),
        )
        if hasattr(result, 'status_code'):
            response = result
        else:
            response = APIResponse.success(
                result, 'Container logs retrieved successfully'
            )
        response['Cache-Control'] = 'no-store'
        response['Pragma'] = 'no-cache'
        return response
