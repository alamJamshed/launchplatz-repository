from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from coreapp.api.common.cookies import REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH
from coreapp.models import User
from coreapp.roles import UserRoles


LOGIN_URL = '/api/v1/auth/login/'
REFRESH_URL = '/api/v1/auth/refresh/'
LOGOUT_URL = '/api/v1/auth/logout/'
PROFILE_URL = '/api/v1/auth/profile/'


class AuthenticationAPITests(APITestCase):
    password = 'StrongPassword123!'

    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com',
            password=self.password,
            first_name='Launch',
            last_name='Admin',
            role=UserRoles.ADMIN,
        )
        self.user = User.objects.create_user(
            email='user@example.com',
            password=self.password,
            first_name='Regular',
            last_name='User',
            role=UserRoles.USER,
        )

    def login_admin(self):
        return self.client.post(
            LOGIN_URL,
            {'email': self.admin.email, 'password': self.password},
            format='json',
        )

    @override_settings(DEBUG=True)
    def test_admin_can_login_and_receives_refresh_cookie(self):
        response = self.login_admin()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data['data'])
        self.assertNotIn('refresh', response.data['data'])
        self.assertEqual(response.data['data']['user']['email'], self.admin.email)

        cookie = response.cookies[REFRESH_COOKIE_NAME]
        self.assertTrue(cookie['httponly'])
        self.assertFalse(cookie['secure'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['path'], REFRESH_COOKIE_PATH)
        self.assertEqual(cookie['max-age'], 7 * 24 * 60 * 60)

    @override_settings(DEBUG=False)
    def test_refresh_cookie_is_secure_outside_debug_mode(self):
        response = self.login_admin()

        self.assertTrue(response.cookies[REFRESH_COOKIE_NAME]['secure'])

    def test_invalid_inactive_and_non_admin_users_cannot_login(self):
        invalid = self.client.post(
            LOGIN_URL,
            {'email': self.admin.email, 'password': 'wrong'},
            format='json',
        )
        non_admin = self.client.post(
            LOGIN_URL,
            {'email': self.user.email, 'password': self.password},
            format='json',
        )
        self.admin.is_active = False
        self.admin.save(update_fields=['is_active'])
        inactive = self.client.post(
            LOGIN_URL,
            {'email': self.admin.email, 'password': self.password},
            format='json',
        )

        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(non_admin.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(inactive.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_rotates_and_blacklists_previous_token(self):
        login = self.login_admin()
        old_token = login.cookies[REFRESH_COOKIE_NAME].value
        old_jti = RefreshToken(old_token)['jti']
        self.client.cookies[REFRESH_COOKIE_NAME] = old_token

        response = self.client.post(REFRESH_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data['data'])
        self.assertNotEqual(
            response.cookies[REFRESH_COOKIE_NAME].value,
            old_token,
        )
        self.assertTrue(
            BlacklistedToken.objects.filter(token__jti=old_jti).exists()
        )

    def test_refresh_rejects_missing_malformed_and_blacklisted_tokens(self):
        missing = self.client.post(REFRESH_URL)
        self.assertEqual(missing.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.cookies[REFRESH_COOKIE_NAME] = 'not-a-token'
        malformed = self.client.post(REFRESH_URL)
        self.assertEqual(malformed.status_code, status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(self.admin)
        refresh.blacklist()
        self.client.cookies[REFRESH_COOKIE_NAME] = str(refresh)
        blacklisted = self.client.post(REFRESH_URL)
        self.assertEqual(blacklisted.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(blacklisted.cookies[REFRESH_COOKIE_NAME]['max-age'], 0)

    def test_refresh_rejects_user_who_is_no_longer_an_admin(self):
        refresh = RefreshToken.for_user(self.admin)
        self.admin.role = UserRoles.USER
        self.admin.save(update_fields=['role'])
        self.client.cookies[REFRESH_COOKIE_NAME] = str(refresh)

        response = self.client.post(REFRESH_URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_token_clears_cookie_and_is_idempotent(self):
        login = self.login_admin()
        raw_token = login.cookies[REFRESH_COOKIE_NAME].value
        jti = RefreshToken(raw_token)['jti']
        self.client.cookies[REFRESH_COOKIE_NAME] = raw_token

        response = self.client.post(LOGOUT_URL)
        repeated = self.client.post(LOGOUT_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.cookies[REFRESH_COOKIE_NAME]['max-age'], 0)
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=jti).exists())
        self.assertEqual(repeated.status_code, status.HTTP_200_OK)

    def test_admin_can_read_profile(self):
        login = self.login_admin()
        access = login.data['data']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        response = self.client.get(PROFILE_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data['data']),
            {
                'id', 'first_name', 'last_name', 'email', 'phone', 'role',
                'is_verified', 'is_approved', 'is_active',
            },
        )

    def test_profile_requires_admin_access_token(self):
        anonymous = self.client.get(PROFILE_URL)
        access = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        non_admin = self.client.get(PROFILE_URL)

        self.assertEqual(anonymous.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(non_admin.status_code, status.HTTP_403_FORBIDDEN)
