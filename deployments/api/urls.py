from rest_framework.routers import DefaultRouter

from .views import DeploymentViewSet


router = DefaultRouter()
router.register('', DeploymentViewSet, basename='deployment')

urlpatterns = router.urls
