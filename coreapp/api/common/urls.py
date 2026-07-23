from django.urls import path
from . import views
from .views import login_view, logout_view, refresh_token_view, CountryListView, StateListView, CityListView

urlpatterns = [
    # Auth endpoints
    path('login/', login_view, name='login'),
    path('refresh/', refresh_token_view, name='refresh'),
    path('logout/', logout_view, name='logout'),
    # Profile endpoint
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('common/countries/', CountryListView.as_view(), name='countries'),
    path('common/states/<int:country_id>/', StateListView.as_view(), name='states'),
    path('common/cities/<int:state_id>/', CityListView.as_view(), name='cities'),

]
