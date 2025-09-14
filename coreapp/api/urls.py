from rest_framework.routers import DefaultRouter
from .admin import views as admin_views
from django.urls import path, include

app_name = 'coreapp_api'

# Admin router
router = DefaultRouter()
router.register(r'users', admin_views.AdminUserViewSet)

urlpatterns = [
    # Auth endpoints
    path('', include('coreapp.api.common.urls'))
]

urlpatterns += router.urls
