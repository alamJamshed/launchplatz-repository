from rest_framework.routers import DefaultRouter

from .views import RouteViewSet

router = DefaultRouter()
router.register('routes', RouteViewSet, basename='route')
urlpatterns = router.urls

