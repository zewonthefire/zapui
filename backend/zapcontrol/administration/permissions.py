from rest_framework.permissions import BasePermission

from .services import ROLE_AUDITOR, ROLE_SCANNER, ROLE_ADMIN, user_in_role


def is_system_admin(user) -> bool:
    return bool(user.is_authenticated and (user.is_superuser or user_in_role(user, ROLE_ADMIN)))


def is_scan_admin(user) -> bool:
    return bool(user.is_authenticated and (is_system_admin(user) or user_in_role(user, ROLE_SCANNER)))


def is_audit_reader(user) -> bool:
    return bool(user.is_authenticated and (is_scan_admin(user) or user_in_role(user, ROLE_AUDITOR)))


class IsSystemAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_system_admin(request.user)


class IsScanAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_scan_admin(request.user)


class IsAuditReader(BasePermission):
    def has_permission(self, request, view):
        return is_audit_reader(request.user)
