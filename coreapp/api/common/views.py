from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .serializers import UserProfileSerializer, LoginSerializer, CountrySerializer, StateSerializer, CitySerializer
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema
from coreapp.utils.responses import APIResponse
from coreapp.utils.email_utils import send_welcome_email
from ...models import Country, City, State


class LoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = serializers.DictField()

@extend_schema(
    request=LoginSerializer,
    responses={200: LoginResponseSerializer},
    description='Login with email and password to get JWT tokens'
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        # Send welcome email on first login
        if not hasattr(user, 'last_login') or user.last_login is None:
            send_welcome_email(
                user_email=user.email,
                user_name=user.first_name or user.email
            )

        data = {
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role
            }
        }
        
        response = APIResponse.success(data, "Login successful")
        # Store refresh token in secure HTTP-only cookie
        response.set_cookie(
            'refresh_token',
            str(refresh),
            max_age=7*24*60*60,  # 7 days
            httponly=True,
            secure=True,
            samesite='Strict'
        )
        return response
    return APIResponse.error(serializer.errors, "Login failed", status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token_view(request):
    refresh_token = request.COOKIES.get('refresh_token')
    
    if not refresh_token:
        return APIResponse.error({}, "Refresh token not found. Please login again.", status.HTTP_401_UNAUTHORIZED)
    
    try:
        refresh = RefreshToken(refresh_token)
        data = {'access': str(refresh.access_token)}
        return APIResponse.success(data, "Token refreshed successfully")
    except TokenError:
        response = APIResponse.error({}, "Refresh token expired. Please login again.", status.HTTP_401_UNAUTHORIZED)
        response.delete_cookie('refresh_token')
        return response


class ProfileView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return APIResponse.success(serializer.data, "Profile retrieved successfully")



class CountryListView(generics.ListAPIView):
    queryset = Country.objects.filter(is_active=True)
    serializer_class = CountrySerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(serializer.data, "Countries retrieved successfully")


class StateListView(generics.ListAPIView):
    serializer_class = StateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        country_id = self.kwargs.get('country_id')
        return State.objects.filter(country_id=country_id, is_active=True)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(serializer.data, "States retrieved successfully")


class CityListView(generics.ListAPIView):
    serializer_class = CitySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        state_id = self.kwargs.get('state_id')
        return City.objects.filter(state_id=state_id, is_active=True)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return APIResponse.success(serializer.data, "Cities retrieved successfully")