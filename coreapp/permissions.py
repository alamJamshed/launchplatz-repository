from rest_framework.permissions import BasePermission
from coreapp.roles import UserRoles


class IsAdmin(BasePermission):
    """
    Allows access only to Admins.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser and request.user.is_staff and request.user.is_authenticated and request.user.role == UserRoles.ADMIN)

class IsAdminStaff(BasePermission):
    """
    Allows access only to Admin Staff.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == UserRoles.ADMIN_STAFF)

class IsUser(BasePermission):
    """
    Allows access only to Users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == UserRoles.USER)