from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action

from coreapp.permissions import IsAdmin
from coreapp.utils.responses import APIResponse

from .models import Route
from .serializers import ReconciliationEventSerializer, RouteSerializer
from .services import verify_domain_dns


class RouteViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = RouteSerializer
    queryset = Route.objects.select_related(
        'domain__project__server'
    ).filter(is_active=True, is_deleted=False)

    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project')
        return queryset.filter(domain__project_id=project_id) if project_id else queryset

    def list(self, request, *args, **kwargs):
        return APIResponse.success(
            self.get_serializer(self.get_queryset(), many=True).data,
            'Routes retrieved successfully',
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return APIResponse.created(serializer.data, 'Route created successfully')

    def retrieve(self, request, *args, **kwargs):
        return APIResponse.success(
            self.get_serializer(self.get_object()).data,
            'Route retrieved successfully',
        )

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            self.get_object(), data=request.data, partial=kwargs.pop('partial', False)
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return APIResponse.success(serializer.data, 'Route updated successfully')

    def destroy(self, request, *args, **kwargs):
        route = self.get_object()
        route.desired_enabled = False
        route.save(update_fields=['desired_enabled', 'updated_at'])
        self._queue(route)
        return APIResponse.success(
            self.get_serializer(route).data,
            'Route disablement queued; delete it after reconciliation.',
            202,
        )

    @staticmethod
    def _queue(route):
        if not getattr(settings, 'CELERY_BROKER_URL', None):
            return False
        from .tasks import reconcile_route_task
        reconcile_route_task.apply_async(args=[route.pk])
        return True

    @action(detail=True, methods=['post'], url_path='verify-dns')
    def verify_dns(self, request, pk=None):
        route = self.get_object()
        verify_domain_dns(route.domain)
        route.refresh_from_db()
        return APIResponse.success(
            self.get_serializer(route).data, 'DNS verification completed'
        )

    @action(detail=True, methods=['post'])
    def reconcile(self, request, pk=None):
        route = self.get_object()
        if not self._queue(route):
            return APIResponse.error(
                'The routing worker broker is not configured.',
                {'category': 'broker_not_configured'},
                503,
            )
        return APIResponse.success(
            {'queued': True}, 'Routing reconciliation queued', 202
        )

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        events = self.get_object().reconciliation_events.all()[:50]
        return APIResponse.success(
            ReconciliationEventSerializer(events, many=True).data,
            'Reconciliation history retrieved',
        )

