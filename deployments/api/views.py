from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action

from coreapp.permissions import IsAdmin
from coreapp.utils.responses import APIResponse
from deployments.models import Deployment

from .serializers import (
    DeploymentFilterSerializer,
    DeploymentListSerializer,
    DeploymentSerializer,
)


class DeploymentViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = DeploymentSerializer
    queryset = Deployment.objects.select_related(
        'project', 'triggered_by', 'cancel_requested_by'
    )

    def get_serializer_class(self):
        if self.action == 'list':
            return DeploymentListSerializer
        return DeploymentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action != 'list':
            return queryset.prefetch_related('steps')
        filters = DeploymentFilterSerializer(data=self.request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data
        if 'project' in values:
            queryset = queryset.filter(project=values['project'])
        if 'status' in values:
            queryset = queryset.filter(status=values['status'])
        ordering = 'created_at' if values['ordering'] == 'oldest' else '-created_at'
        return queryset.order_by(ordering)

    @extend_schema(
        parameters=[DeploymentFilterSerializer],
        responses={200: DeploymentListSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
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
            'Deployment history retrieved successfully',
        )

    @extend_schema(responses={200: DeploymentSerializer})
    def retrieve(self, request, *args, **kwargs):
        return APIResponse.success(
            self.get_serializer(self.get_object()).data,
            'Deployment details retrieved successfully',
        )

    @extend_schema(responses={200: DeploymentSerializer})
    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        return APIResponse.success(
            self.get_serializer(self.get_object()).data,
            'Deployment progress retrieved successfully',
        )

    @extend_schema(request=None, responses={200: DeploymentSerializer})
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        deployment = self.get_object()
        if deployment.status in Deployment.ACTIVE_STATUSES:
            if deployment.cancel_requested_at is None:
                deployment.cancel_requested_at = timezone.now()
                deployment.cancel_requested_by = request.user
                deployment.cancel_requested_by_email_snapshot = request.user.email
            deployment.status = Deployment.Status.CANCELLING
            deployment.save(update_fields=[
                'cancel_requested_at', 'cancel_requested_by',
                'cancel_requested_by_email_snapshot', 'status',
            ])
        return APIResponse.success(
            self.get_serializer(deployment).data,
            'Deployment cancellation processed successfully',
        )
