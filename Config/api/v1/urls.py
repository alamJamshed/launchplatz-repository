from django.urls import path, include
from coreapp.api.dashboard import DashboardView

app_name = 'api_v1'

urlpatterns = [
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('auth/', include('coreapp.api.urls')),
    path('utility/', include('utility.api.urls')),
    path('servers/', include('servers.api.urls')),
    path('projects/', include('projects.api.urls')),
    path('deployments/', include('deployments.api.urls')),
]
