from rest_framework import viewsets
from coreapp.models import User
from .serializers import AdminUserSerializer
from ...permissions import IsAdmin
from coreapp.utils.responses import APIResponse

class AdminUserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdmin]
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginator = self.paginator
            return APIResponse.paginated(
                data=serializer.data,
                count=paginator.count,
                next_url=paginator.get_next_link(),
                previous_url=paginator.get_previous_link()
            )
        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(serializer.data, "Users retrieved successfully")