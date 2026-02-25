from django.contrib.auth.models import Group
from rest_framework.permissions import BasePermission

from .services import ROLE_AUDIT_VIEWER, ROLE_SCAN_ADMIN, ROLE_SYSTEM_ADMIN


def in_group(user, name: str) -> bool:
    return user.is_authenticated and user.groups.filter(name=name).exists()


def is_system_admin(user) -> bool:
    return bool(user.is_authenticated and (user.is_superuser or in_group(user, ROLE_SYSTEM_ADMIN)))


def is_scan_admin(user) -> bool:
    return bool(user.is_authenticated and (is_system_admin(user) or in_group(user, ROLE_SCAN_ADMIN)))


def is_audit_reader(user) -> bool:
    return bool(user.is_authenticated and (is_scan_admin(user) or in_group(user, ROLE_AUDIT_VIEWER)))


class IsSystemAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_system_admin(request.user)


class IsScanAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_scan_admin(request.user)


class IsAuditReader(BasePermission):
    def has_permission(self, request, view):
        return is_audit_reader(request.user)
