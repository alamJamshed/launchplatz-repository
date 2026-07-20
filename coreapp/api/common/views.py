from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from coreapp.models import City, Country, State
from coreapp.permissions import IsAdmin
from coreapp.roles import UserRoles
from coreapp.utils.responses import APIResponse

from .cookies import (
    REFRESH_COOKIE_NAME,
    clear_refresh_cookie,
    set_refresh_cookie,
)
from .serializers import (
    CitySerializer,
    CountrySerializer,
    LoginSerializer,
    StateSerializer,
    UserProfileSerializer,
)


User = get_user_model()


class LoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    user = UserProfileSerializer()


class AccessTokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField()


def _admin_for_refresh(refresh):
    user = User.objects.get(pk=refresh['user_id'])
    if not user.is_active or user.role != UserRoles.ADMIN:
        raise TokenError('Token is not valid for an active admin')
    return user


@extend_schema(
    request=LoginSerializer,
    responses={200: LoginResponseSerializer},
    description=(
        'Authenticate an active Admin. The access token is returned in the '
        'response and the refresh token is stored in an HttpOnly cookie.'
    ),
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return APIResponse.error(
            message='Login failed',
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = serializer.validated_data['user']
    refresh = RefreshToken.for_user(user)
    response = APIResponse.success(
        {
            'access': str(refresh.access_token),
            'user': UserProfileSerializer(user).data,
        },
        'Login successful',
    )
    return set_refresh_cookie(response, refresh)


@extend_schema(
    request=None,
    responses={
        200: AccessTokenResponseSerializer,
        401: OpenApiResponse(description='Refresh token is missing or invalid.'),
    },
    description='Rotate the refresh-token cookie and return a new access token.',
)
@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token_view(request):
    raw_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
    if not raw_token:
        response = APIResponse.unauthorized('Refresh token not found. Please login again.')
        return clear_refresh_cookie(response)

    try:
        old_refresh = RefreshToken(raw_token)
        user = _admin_for_refresh(old_refresh)
        old_refresh.blacklist()
        new_refresh = RefreshToken.for_user(user)
    except (TokenError, User.DoesNotExist, KeyError):
        response = APIResponse.unauthorized('Refresh token is invalid. Please login again.')
        return clear_refresh_cookie(response)

    response = APIResponse.success(
        {'access': str(new_refresh.access_token)},
        'Token refreshed successfully',
    )
    return set_refresh_cookie(response, new_refresh)


@extend_schema(
    request=None,
    responses={200: OpenApiResponse(description='Logged out successfully.')},
    description='Blacklist the current refresh token and clear its cookie.',
)
@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    raw_token = request.COOKIES.get(REFRESH_COOKIE_NAME)
    if raw_token:
        try:
            RefreshToken(raw_token).blacklist()
        except TokenError:
            pass

    response = APIResponse.success(None, 'Logout successful')
    return clear_refresh_cookie(response)


class ProfileView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAdmin]

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return APIResponse.success(serializer.data, 'Profile retrieved successfully')


class CountryListView(generics.ListAPIView):
    queryset = Country.objects.filter(is_active=True)
    serializer_class = CountrySerializer
    permission_classes = [IsAdmin]

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return APIResponse.success(serializer.data, 'Countries retrieved successfully')


class StateListView(generics.ListAPIView):
    serializer_class = StateSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return State.objects.filter(
            country_id=self.kwargs.get('country_id'), is_active=True
        )

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return APIResponse.success(serializer.data, 'States retrieved successfully')


class CityListView(generics.ListAPIView):
    serializer_class = CitySerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return City.objects.filter(
            state_id=self.kwargs.get('state_id'), is_active=True
        )

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return APIResponse.success(serializer.data, 'Cities retrieved successfully')
