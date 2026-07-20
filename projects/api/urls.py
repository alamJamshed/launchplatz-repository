from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ProjectViewSet
from .container_views import (
    ContainerDetailView,
    ContainerListView,
    ContainerLogsView,
    ContainerRestartView,
    ContainerStartView,
    ContainerStopView,
)


router = DefaultRouter()
router.register('', ProjectViewSet, basename='project')

urlpatterns = [
    path('<int:project_id>/containers/', ContainerListView.as_view()),
    path(
        '<int:project_id>/containers/<str:service>/logs/',
        ContainerLogsView.as_view(),
    ),
    path(
        '<int:project_id>/containers/<str:service>/start/',
        ContainerStartView.as_view(),
    ),
    path(
        '<int:project_id>/containers/<str:service>/stop/',
        ContainerStopView.as_view(),
    ),
    path(
        '<int:project_id>/containers/<str:service>/restart/',
        ContainerRestartView.as_view(),
    ),
    path(
        '<int:project_id>/containers/<str:service>/',
        ContainerDetailView.as_view(),
    ),
] + router.urls
