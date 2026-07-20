from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.http import HttpResponse
from django.test import SimpleTestCase, override_settings
from rest_framework_simplejwt.exceptions import TokenError

from coreapp.api.common.cookies import (
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_PATH,
    clear_refresh_cookie,
    set_refresh_cookie,
)
from coreapp.api.common.serializers import LoginSerializer
from coreapp.api.common.views import _admin_for_refresh
from coreapp.permissions import IsAdmin
from coreapp.roles import UserRoles


class IsAdminUnitTests(SimpleTestCase):
    def setUp(self):
        self.permission = IsAdmin()
        self.view = Mock()

    def request_for(self, user):
        return SimpleNamespace(user=user)

    def test_allows_active_authenticated_admin_role(self):
        user = SimpleNamespace(
            is_authenticated=True,
            is_active=True,
            role=UserRoles.ADMIN,
        )

        allowed = self.permission.has_permission(self.request_for(user), self.view)

        self.assertTrue(allowed)

    def test_rejects_inactive_anonymous_and_non_admin_users(self):
        inactive = SimpleNamespace(
            is_authenticated=True,
            is_active=False,
            role=UserRoles.ADMIN,
        )
        anonymous = SimpleNamespace(
            is_authenticated=False,
            is_active=True,
            role=UserRoles.ADMIN,
        )
        non_admin = SimpleNamespace(
            is_authenticated=True,
            is_active=True,
            role=UserRoles.USER,
        )

        self.assertFalse(
            self.permission.has_permission(self.request_for(inactive), self.view)
        )
        self.assertFalse(
            self.permission.has_permission(self.request_for(anonymous), self.view)
        )
        self.assertFalse(
            self.permission.has_permission(self.request_for(non_admin), self.view)
        )


class LoginSerializerUnitTests(SimpleTestCase):
    credentials = {'email': 'admin@example.com', 'password': 'secret'}

    @patch('coreapp.api.common.serializers.authenticate')
    def test_accepts_active_admin(self, authenticate):
        admin = SimpleNamespace(is_active=True, role=UserRoles.ADMIN)
        authenticate.return_value = admin
        serializer = LoginSerializer(data=self.credentials)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIs(serializer.validated_data['user'], admin)
        authenticate.assert_called_once_with(
            email=self.credentials['email'],
            password=self.credentials['password'],
        )

    @patch('coreapp.api.common.serializers.authenticate')
    def test_rejects_invalid_inactive_and_non_admin_accounts(self, authenticate):
        rejected_users = [
            None,
            SimpleNamespace(is_active=False, role=UserRoles.ADMIN),
            SimpleNamespace(is_active=True, role=UserRoles.USER),
        ]

        for user in rejected_users:
            with self.subTest(user=user):
                authenticate.return_value = user
                serializer = LoginSerializer(data=self.credentials)
                self.assertFalse(serializer.is_valid())
                self.assertIn('non_field_errors', serializer.errors)


class RefreshAdminUnitTests(SimpleTestCase):
    refresh = {'user_id': 42}

    @patch('coreapp.api.common.views.User.objects.get')
    def test_returns_active_admin(self, get_user):
        admin = SimpleNamespace(is_active=True, role=UserRoles.ADMIN)
        get_user.return_value = admin

        result = _admin_for_refresh(self.refresh)

        self.assertIs(result, admin)
        get_user.assert_called_once_with(pk=42)

    @patch('coreapp.api.common.views.User.objects.get')
    def test_rejects_inactive_or_non_admin_user(self, get_user):
        rejected_users = [
            SimpleNamespace(is_active=False, role=UserRoles.ADMIN),
            SimpleNamespace(is_active=True, role=UserRoles.USER),
        ]

        for user in rejected_users:
            with self.subTest(user=user):
                get_user.return_value = user
                with self.assertRaises(TokenError):
                    _admin_for_refresh(self.refresh)


@override_settings(
    SIMPLE_JWT={'REFRESH_TOKEN_LIFETIME': timedelta(days=7)},
)
class RefreshCookieUnitTests(SimpleTestCase):
    @override_settings(DEBUG=True)
    def test_sets_development_cookie_from_jwt_lifetime(self):
        response = HttpResponse()

        result = set_refresh_cookie(response, 'refresh-value')

        cookie = response.cookies[REFRESH_COOKIE_NAME]
        self.assertIs(result, response)
        self.assertEqual(cookie.value, 'refresh-value')
        self.assertEqual(cookie['max-age'], 604800)
        self.assertEqual(cookie['path'], REFRESH_COOKIE_PATH)
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertTrue(cookie['httponly'])
        self.assertFalse(cookie['secure'])

    @override_settings(DEBUG=False)
    def test_sets_secure_cookie_outside_debug_mode(self):
        response = HttpResponse()

        set_refresh_cookie(response, 'refresh-value')

        self.assertTrue(response.cookies[REFRESH_COOKIE_NAME]['secure'])

    def test_clear_cookie_uses_the_same_name_and_path(self):
        response = HttpResponse()

        result = clear_refresh_cookie(response)

        cookie = response.cookies[REFRESH_COOKIE_NAME]
        self.assertIs(result, response)
        self.assertEqual(cookie['max-age'], 0)
        self.assertEqual(cookie['path'], REFRESH_COOKIE_PATH)
        self.assertEqual(cookie['samesite'], 'Lax')
