import base64
import hashlib
import json
import uuid
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection

from .models import AppSetting, AuditEvent

ROLE_SYSTEM_ADMIN = 'system_admin'
ROLE_SCAN_ADMIN = 'scan_admin'
ROLE_AUDIT_VIEWER = 'audit_viewer'


def audit_log(actor, action: str, obj=None, status: str = AuditEvent.STATUS_SUCCESS, message: str = '', extra: dict | None = None, request=None):
    object_type = ''
    object_id = ''
    object_repr = ''
    if obj is not None:
        object_type = obj.__class__.__name__
        object_id = str(getattr(obj, 'pk', ''))
        object_repr = str(obj)[:255]
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=object_id,
        object_repr=object_repr,
        ip_address=getattr(request, 'audit_ip', None),
        user_agent=getattr(request, 'audit_user_agent', '')[:255],
        request_id=getattr(request, 'request_id', None) or uuid.uuid4(),
        status=status,
        message=message[:255],
        extra=extra or {},
    )


def setting_int(key: str, default: int) -> int:
    setting = AppSetting.objects.filter(key=key).first()
    if not setting:
        return default
    try:
        return int(setting.value)
    except (TypeError, ValueError):
        return default


def ensure_default_settings():
    from .models import default_settings_definitions

    for key, value, value_type, description in default_settings_definitions():
        AppSetting.objects.get_or_create(
            key=key,
            defaults={
                'value': value,
                'value_type': value_type,
                'description': description,
                'is_secret': value_type == AppSetting.TYPE_SECRET,
            },
        )


def bootstrap_roles():
    User = get_user_model()
    user_ct = ContentType.objects.get_for_model(User)
    group_ct = ContentType.objects.get_for_model(Group)
    app_setting_ct = ContentType.objects.get_for_model(AppSetting)
    audit_ct = ContentType.objects.get_for_model(AuditEvent)

    perms = {
        ROLE_SYSTEM_ADMIN: list(Permission.objects.filter(content_type__in=[user_ct, group_ct, app_setting_ct, audit_ct])) + list(
            Permission.objects.filter(codename__in=['add_zappool', 'change_zappool', 'delete_zappool', 'view_zappool'])
        ),
        ROLE_SCAN_ADMIN: list(
            Permission.objects.filter(codename__in=['view_auditevent', 'add_zappool', 'change_zappool', 'view_zappool'])
        ),
        ROLE_AUDIT_VIEWER: list(Permission.objects.filter(codename='view_auditevent')),
    }
    for role_name, role_perms in perms.items():
        group, _ = Group.objects.get_or_create(name=role_name)
        group.permissions.set(role_perms)


def db_connection_sanity() -> bool:
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
        row = cursor.fetchone()
    return bool(row and row[0] == 1)


def _xor_cipher(data: bytes, secret: str) -> bytes:
    key = hashlib.sha256(secret.encode('utf-8')).digest()
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def encrypt_api_key(raw_value: str) -> str:
    secret = getattr(settings, 'ZAP_NODE_KEY_ENCRYPTION_SECRET', '')
    if not secret or not raw_value:
        return raw_value
    try:
        from cryptography.fernet import Fernet

        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode('utf-8')).digest())
        return 'fernet:' + Fernet(key).encrypt(raw_value.encode('utf-8')).decode('utf-8')
    except Exception:
        return 'xor:' + base64.b64encode(_xor_cipher(raw_value.encode('utf-8'), secret)).decode('ascii')


def decrypt_api_key(stored_value: str) -> str:
    secret = getattr(settings, 'ZAP_NODE_KEY_ENCRYPTION_SECRET', '')
    if not secret or not stored_value:
        return stored_value
    if stored_value.startswith('fernet:'):
        token = stored_value.removeprefix('fernet:')
        try:
            from cryptography.fernet import Fernet

            key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode('utf-8')).digest())
            return Fernet(key).decrypt(token.encode('utf-8')).decode('utf-8')
        except Exception:
            return ''
    if stored_value.startswith('xor:'):
        payload = base64.b64decode(stored_value.removeprefix('xor:'))
        return _xor_cipher(payload, secret).decode('utf-8')
    return stored_value
