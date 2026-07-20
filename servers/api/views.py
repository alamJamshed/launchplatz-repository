from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action

from coreapp.permissions import IsAdmin
from coreapp.utils.responses import APIResponse
from servers.models import Server
from servers.services import SSHConnectionTester

from .serializers import ConnectionTestResultSerializer, ServerSerializer


@extend_schema_view(
    list=extend_schema(description='List active, non-deleted servers.'),
    create=extend_schema(description='Create a server with an encrypted SSH key.'),
    retrieve=extend_schema(description='Retrieve a server without its SSH key.'),
    update=extend_schema(description='Replace a server configuration.'),
    partial_update=extend_schema(description='Partially update a server configuration.'),
    destroy=extend_schema(description='Soft-delete a server.'),
)
class ServerViewSet(viewsets.ModelViewSet):
    serializer_class = ServerSerializer
    permission_classes = [IsAdmin]
    queryset = Server.objects.filter(is_deleted=False, is_active=True)

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
            'Servers retrieved successfully',
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user, updated_by=request.user)
        return APIResponse.created(serializer.data, 'Server created successfully')

    def retrieve(self, request, *args, **kwargs):
        return APIResponse.success(
            self.get_serializer(self.get_object()).data,
            'Server retrieved successfully',
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(
            self.get_object(), data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return APIResponse.success(serializer.data, 'Server updated successfully')

    def destroy(self, request, *args, **kwargs):
        server = self.get_object()
        server.soft_delete(request.user)
        return APIResponse.success(None, 'Server deleted successfully')

    @extend_schema(
        request=None,
        responses={200: ConnectionTestResultSerializer},
        description='Test SSH authentication without executing a remote command.',
    )
    @action(detail=True, methods=['post'], url_path='test-connection')
    def test_connection(self, request, pk=None):
        server = self.get_object()
        result = SSHConnectionTester.test(server)
        server.record_connection_result(result, request.user)
        return APIResponse.success(result, 'Connection test completed')
