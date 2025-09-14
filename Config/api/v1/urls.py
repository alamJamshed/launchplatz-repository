from django.urls import path, include

app_name = 'api_v1'

urlpatterns = [
    path('auth/', include('coreapp.api.urls')),
    path('utility/', include('utility.api.urls')),
]