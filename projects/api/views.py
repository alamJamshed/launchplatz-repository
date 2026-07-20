from time import perf_counter

from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.conf import settings
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers, viewsets
from rest_framework.decorators import action

from coreapp.permissions import IsAdmin
from coreapp.utils.responses import APIResponse
from projects.environment_services import (
    EnvironmentOperationError,
    RemoteEnvironmentService,
)
from projects.git_services import GitOperationError, RemoteGitService
from projects.models import EnvironmentVariable, GitOperation, Project
from deployments.models import Deployment
from deployments.services import create_deployment_steps
from deployments.api.serializers import DeploymentSerializer

from .serializers import (
    BranchSelectionSerializer,
    GitActionResultSerializer,
    GitOperationSerializer,
    ProjectSerializer,
    EnvironmentGenerationResultSerializer,
    EnvironmentVariableSerializer,
)


class ArchiveFilterSerializer(serializers.Serializer):
    archived = serializers.ChoiceField(
        choices=['false', 'true', 'all'], required=False, default='false'
    )


@extend_schema_view(
    list=extend_schema(
        parameters=[ArchiveFilterSerializer],
        description='List projects, filtered by archive state.',
    ),
    create=extend_schema(description='Create a Django + React project.'),
    retrieve=extend_schema(description='Retrieve a project.'),
    update=extend_schema(description='Replace a project configuration.'),
    partial_update=extend_schema(description='Partially update a project.'),
    destroy=extend_schema(description='Permanently delete a project.'),
)
class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [IsAdmin]
    queryset = Project.objects.filter(is_active=True, is_deleted=False)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        if self.action in {
            'environment_variables', 'environment_variable_detail', 'generate_env'
        }:
            response['Cache-Control'] = 'no-store'
            response['Pragma'] = 'no-cache'
        return response

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action != 'list':
            return queryset

        filter_serializer = ArchiveFilterSerializer(data=self.request.query_params)
        filter_serializer.is_valid(raise_exception=True)
        archived = filter_serializer.validated_data['archived']
        if archived == 'true':
            return queryset.filter(is_archived=True)
        if archived == 'false':
            return queryset.filter(is_archived=False)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return APIResponse.paginated(
                serializer.data,
                count=self.paginator.count,
                next_url=self.paginator.get_next_link(),
                previous_url=self.paginator.get_previous_link(),
            )
        return APIResponse.success(
            self.get_serializer(queryset, many=True).data,
            'Projects retrieved successfully',
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user, updated_by=request.user)
        return APIResponse.created(serializer.data, 'Project created successfully')

    def retrieve(self, request, *args, **kwargs):
        return APIResponse.success(
            self.get_serializer(self.get_object()).data,
            'Project retrieved successfully',
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(
            self.get_object(), data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return APIResponse.success(serializer.data, 'Project updated successfully')

    def destroy(self, request, *args, **kwargs):
        try:
            self.get_object().delete()
        except ProtectedError:
            return APIResponse.error(
                'Projects with deployment history cannot be deleted.',
                {'category': 'deployment_history_exists'}, 409,
            )
        return APIResponse.success(None, 'Project deleted permanently')

    def _start_deployment(self, request, trigger):
        project = self.get_object()
        if project.is_archived:
            return APIResponse.error(
                'Archived projects cannot be deployed.',
                {'category': 'project_archived'}, 409,
            )
        if not project.server.is_active or project.server.is_deleted:
            return APIResponse.error(
                'The project server is not active.',
                {'category': 'server_inactive'}, 409,
            )
        if not project.git_cloned_at:
            return APIResponse.error(
                'Repository has not been cloned.',
                {'category': 'repository_not_cloned'}, 409,
            )
        if not getattr(settings, 'CELERY_BROKER_URL', None):
            return APIResponse.error(
                'The deployment worker broker is not configured.',
                {'category': 'broker_not_configured'}, 503,
            )
        try:
            with transaction.atomic():
                deployment = Deployment.objects.create(
                    project=project,
                    trigger=trigger,
                    triggered_by=request.user,
                    project_name_snapshot=project.name,
                    server_name_snapshot=project.server.name,
                    server_ip_snapshot=str(project.server.ip_address),
                    branch_snapshot=project.branch,
                    repository_url_snapshot=project.git_repository_url,
                    triggered_by_email_snapshot=request.user.email,
                )
                create_deployment_steps(deployment)
        except IntegrityError:
            return APIResponse.error(
                'A deployment is already active for this project.',
                {'category': 'deployment_in_progress'}, 409,
            )
        from deployments.tasks import run_deployment
        try:
            task = run_deployment.apply_async(args=[deployment.pk])
        except Exception:
            deployment.status = Deployment.Status.FAILED
            deployment.error_category = 'broker_unavailable'
            deployment.error_message = 'Could not queue the deployment.'
            deployment.completed_at = timezone.now()
            deployment.save()
            return APIResponse.error(
                deployment.error_message,
                {'category': deployment.error_category}, 503,
            )
        deployment.celery_task_id = task.id or ''
        deployment.save(update_fields=['celery_task_id'])
        return APIResponse.success(
            DeploymentSerializer(deployment).data,
            'Deployment queued successfully', 202,
        )

    @extend_schema(request=None, responses={202: DeploymentSerializer})
    @action(detail=True, methods=['post'])
    def deploy(self, request, pk=None):
        return self._start_deployment(request, Deployment.Trigger.DEPLOY)

    @extend_schema(request=None, responses={202: DeploymentSerializer})
    @action(detail=True, methods=['post'])
    def redeploy(self, request, pk=None):
        return self._start_deployment(request, Deployment.Trigger.REDEPLOY)

    @extend_schema(responses={200: DeploymentSerializer})
    @action(detail=True, methods=['get'], url_path='deployment-status')
    def deployment_status(self, request, pk=None):
        deployment = self.get_object().deployments.prefetch_related('steps').first()
        return APIResponse.success(
            DeploymentSerializer(deployment).data if deployment else None,
            'Deployment status retrieved successfully',
        )

    @staticmethod
    def _sensitive_response(response):
        response['Cache-Control'] = 'no-store'
        response['Pragma'] = 'no-cache'
        return response

    def _environment_project(self):
        return self.get_object()

    def _environment_variable(self, project, variable_id):
        return get_object_or_404(
            EnvironmentVariable,
            pk=variable_id, project=project, is_active=True, is_deleted=False
        )

    @extend_schema(
        methods=['GET'], responses={200: EnvironmentVariableSerializer(many=True)}
    )
    @extend_schema(methods=['POST'], request=EnvironmentVariableSerializer,
                   responses={201: EnvironmentVariableSerializer})
    @action(detail=True, methods=['get', 'post'], url_path='environment-variables')
    def environment_variables(self, request, pk=None):
        project = self._environment_project()
        if request.method == 'GET':
            queryset = project.environment_variables.filter(
                is_active=True, is_deleted=False
            )
            response = APIResponse.success(
                EnvironmentVariableSerializer(queryset, many=True).data,
                'Environment variables retrieved successfully',
            )
            return self._sensitive_response(response)
        if project.is_archived:
            return APIResponse.error(
                'Archived projects cannot change environment variables.',
                {'category': 'project_archived'}, 409,
            )
        serializer = EnvironmentVariableSerializer(
            data=request.data, context={'project': project, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(
            project=project, created_by=request.user, updated_by=request.user
        )
        return self._sensitive_response(APIResponse.created(
            serializer.data, 'Environment variable created successfully'
        ))

    @extend_schema(
        methods=['GET'], responses={200: EnvironmentVariableSerializer}
    )
    @extend_schema(
        methods=['PATCH'], request=EnvironmentVariableSerializer,
        responses={200: EnvironmentVariableSerializer},
    )
    @extend_schema(methods=['DELETE'], responses={200: None})
    @action(
        detail=True, methods=['get', 'patch', 'delete'],
        url_path=r'environment-variables/(?P<variable_id>[0-9]+)',
        url_name='environment-variable-detail',
    )
    def environment_variable_detail(self, request, pk=None, variable_id=None):
        project = self._environment_project()
        variable = self._environment_variable(project, variable_id)
        if request.method == 'GET':
            return self._sensitive_response(APIResponse.success(
                EnvironmentVariableSerializer(variable).data,
                'Environment variable retrieved successfully',
            ))
        if project.is_archived:
            return APIResponse.error(
                'Archived projects cannot change environment variables.',
                {'category': 'project_archived'}, 409,
            )
        if request.method == 'DELETE':
            variable.delete()
            return self._sensitive_response(APIResponse.success(
                None, 'Environment variable deleted successfully'
            ))
        serializer = EnvironmentVariableSerializer(
            variable, data=request.data, partial=True,
            context={'project': project, 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return self._sensitive_response(APIResponse.success(
            serializer.data, 'Environment variable updated successfully'
        ))

    @extend_schema(request=None, responses={200: EnvironmentGenerationResultSerializer})
    @action(
        detail=True, methods=['post'],
        url_path='environment-variables/generate-env', url_name='generate-env',
    )
    def generate_env(self, request, pk=None):
        project = self._environment_project()
        if project.is_archived:
            return APIResponse.error(
                'Archived projects cannot generate environment files.',
                {'category': 'project_archived'}, 409,
            )
        variables = list(project.environment_variables.filter(
            is_active=True, is_deleted=False
        ))
        try:
            with RemoteEnvironmentService(project) as service:
                result = service.generate(variables)
        except EnvironmentOperationError as exc:
            return APIResponse.error(
                exc.message, {'category': exc.category}, exc.status_code
            )
        return self._sensitive_response(APIResponse.success(
            result, 'Environment file generated successfully'
        ))

    def _git_action(self, request, action_name, callback, mutating=False):
        project = self.get_object()
        if mutating and project.is_archived:
            return APIResponse.error(
                message='Archived projects cannot run mutating Git operations.',
                errors={'category': 'project_archived'},
                status_code=409,
            )

        started_at = timezone.now()
        timer = perf_counter()
        try:
            with RemoteGitService(project) as service:
                result = callback(service, project)
            output = result.pop('_output', '')
            completed_at = timezone.now()
            GitOperation.objects.create(
                project=project,
                action=action_name,
                status=GitOperation.Status.SUCCESS,
                output=output,
                commit_hash=result.get('commit', ''),
                duration_ms=round((perf_counter() - timer) * 1000),
                started_at=started_at,
                completed_at=completed_at,
                initiated_by=request.user,
            )
            return APIResponse.success(result, 'Git operation completed')
        except GitOperationError as exc:
            completed_at = timezone.now()
            GitOperation.objects.create(
                project=project,
                action=action_name,
                status=GitOperation.Status.FAILED,
                output=exc.output,
                error_category=exc.category,
                duration_ms=round((perf_counter() - timer) * 1000),
                started_at=started_at,
                completed_at=completed_at,
                initiated_by=request.user,
            )
            return APIResponse.error(
                message=exc.message,
                errors={'category': exc.category},
                status_code=exc.status_code,
            )

    @extend_schema(request=None, responses={200: ProjectSerializer})
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        project = self.get_object()
        project.archive(request.user)
        return APIResponse.success(
            self.get_serializer(project).data, 'Project archived successfully'
        )

    @extend_schema(request=None, responses={200: ProjectSerializer})
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        project = self.get_object()
        project.restore(request.user)
        return APIResponse.success(
            self.get_serializer(project).data, 'Project restored successfully'
        )

    @extend_schema(request=None, responses={200: GitActionResultSerializer})
    @action(detail=True, methods=['post'], url_path='git/clone')
    def git_clone(self, request, pk=None):
        return self._git_action(
            request,
            GitOperation.Action.CLONE,
            lambda service, project: service.clone(request.user),
            mutating=True,
        )

    @extend_schema(request=None, responses={200: GitActionResultSerializer})
    @action(detail=True, methods=['post'], url_path='git/pull')
    def git_pull(self, request, pk=None):
        return self._git_action(
            request,
            GitOperation.Action.PULL,
            lambda service, project: service.pull(request.user),
            mutating=True,
        )

    @extend_schema(request=None, responses={200: GitActionResultSerializer})
    @action(detail=True, methods=['get'], url_path='git/current-commit')
    def git_current_commit(self, request, pk=None):
        return self._git_action(
            request,
            GitOperation.Action.CURRENT_COMMIT,
            lambda service, project: service.current_commit(request.user),
        )

    @extend_schema(request=None, responses={200: GitActionResultSerializer})
    @action(detail=True, methods=['get'], url_path='git/branches')
    def git_branches(self, request, pk=None):
        return self._git_action(
            request,
            GitOperation.Action.LIST_BRANCHES,
            lambda service, project: service.branches(),
        )

    @extend_schema(
        request=BranchSelectionSerializer,
        responses={200: GitActionResultSerializer},
    )
    @action(detail=True, methods=['post'], url_path='git/select-branch')
    def git_select_branch(self, request, pk=None):
        serializer = BranchSelectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        branch = serializer.validated_data['branch']
        return self._git_action(
            request,
            GitOperation.Action.SELECT_BRANCH,
            lambda service, project: service.select_branch(branch, request.user),
            mutating=True,
        )

    @extend_schema(request=None, responses={200: GitOperationSerializer(many=True)})
    @action(detail=True, methods=['get'], url_path='git/operations')
    def git_operations(self, request, pk=None):
        queryset = self.get_object().git_operations.all()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = GitOperationSerializer(page, many=True)
            return APIResponse.paginated(
                serializer.data,
                count=self.paginator.count,
                next_url=self.paginator.get_next_link(),
                previous_url=self.paginator.get_previous_link(),
            )
        return APIResponse.success(
            GitOperationSerializer(queryset, many=True).data,
            'Git operations retrieved successfully',
        )
