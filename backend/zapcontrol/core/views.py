import os

import redis
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect, render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

OPS_ENABLED = os.getenv('ENABLE_OPS_AGENT', 'false').lower() in {'1', 'true', 'yes', 'on'}
OPS_AGENT_URL = os.getenv('OPS_AGENT_URL', 'http://ops:8091')
OPS_AGENT_TOKEN = os.getenv('OPS_AGENT_TOKEN', '')
OPS_SERVICES = ['nginx', 'web', 'worker', 'beat', 'db', 'redis', 'zap', 'pdf', 'ops']


def _is_admin(user) -> bool:
    return user.is_authenticated and (user.is_superuser or getattr(user, 'role', '') == 'admin')


def _admin_only(request: HttpRequest):
    if not _is_admin(request.user):
        messages.error(request, 'Admin role required for operations pages.')
        return redirect('dashboard')
    return None


def _ops_headers() -> dict[str, str]:
    return {'X-OPS-TOKEN': OPS_AGENT_TOKEN} if OPS_AGENT_TOKEN else {}


def _ops_get(path: str, **kwargs):
    return requests.get(f'{OPS_AGENT_URL}{path}', headers=_ops_headers(), timeout=10, **kwargs)


def _ops_post(path: str, **kwargs):
    return requests.post(f'{OPS_AGENT_URL}{path}', headers=_ops_headers(), timeout=120, **kwargs)


def health(request):
    return JsonResponse({'status': 'ok'})


def setup(request):
    return JsonResponse({'status': 'pending', 'message': 'Wizard not implemented yet'})


@login_required
def dashboard(request):
    return render(request, 'core/dashboard.html')


@login_required
def ops_overview(request):
    denied = _admin_only(request)
    if denied:
        return denied

    status_rows = []
    checks = connectivity_checks()

    if OPS_ENABLED:
        try:
            response = _ops_get('/compose/services')
            response.raise_for_status()
            service_map = {row.get('Service'): row for row in response.json().get('services', [])}
            for service in OPS_SERVICES:
                row = service_map.get(service, {})
                status_rows.append(
                    {
                        'service': service,
                        'state': row.get('State', 'unknown'),
                        'status': row.get('Status', 'n/a'),
                    }
                )
        except Exception as exc:
            messages.warning(request, f'Ops agent unavailable: {exc}')
    else:
        status_rows = [{'service': s, 'state': 'disabled', 'status': 'Enable ENABLE_OPS_AGENT=true + COMPOSE_PROFILES=ops'} for s in OPS_SERVICES]

    return render(
        request,
        'core/ops_overview.html',
        {
            'ops_enabled': OPS_ENABLED,
            'status_rows': status_rows,
            'checks': checks,
        },
    )


@login_required
def ops_logs(request, service):
    denied = _admin_only(request)
    if denied:
        return denied

    logs = 'Ops agent disabled. Enable ENABLE_OPS_AGENT=true and COMPOSE_PROFILES=ops.'
    if OPS_ENABLED:
        try:
            response = _ops_get(f'/compose/logs/{service}', params={'tail': request.GET.get('tail', 200)})
            response.raise_for_status()
            logs = response.json().get('logs', '')
        except Exception as exc:
            logs = f'Failed to retrieve logs: {exc}'

    return render(request, 'core/ops_logs.html', {'service': service, 'logs': logs, 'ops_enabled': OPS_ENABLED})


@login_required
def ops_actions(request):
    denied = _admin_only(request)
    if denied:
        return denied

    if request.method == 'POST':
        if not request.user.check_password(request.POST.get('password', '')):
            messages.error(request, 'Password confirmation failed. Action cancelled.')
            return redirect('ops-actions')

        if not OPS_ENABLED:
            messages.warning(request, 'Ops agent disabled. This page is read-only until ENABLE_OPS_AGENT=true.')
            return redirect('ops-actions')

        action = request.POST.get('action')
        services = [s.strip() for s in request.POST.get('services', '').split(',') if s.strip()]
        service = request.POST.get('service', '').strip()

        try:
            if action == 'restart' and service:
                response = _ops_post(f'/compose/restart/{service}')
            elif action == 'rebuild':
                response = _ops_post('/compose/rebuild', json={'services': services})
            elif action == 'redeploy':
                response = _ops_post('/compose/redeploy', json={'services': services})
            else:
                messages.error(request, 'Invalid action payload.')
                return redirect('ops-actions')

            response.raise_for_status()
            messages.success(request, f'{action} executed successfully.')
        except Exception as exc:
            messages.error(request, f'Action failed: {exc}')

        return redirect('ops-actions')

    return render(request, 'core/ops_actions.html', {'ops_enabled': OPS_ENABLED, 'services': OPS_SERVICES})


@api_view(['GET'])
@permission_classes([AllowAny])
def api_version(request):
    return Response({'name': 'zapcontrol', 'version': settings.APP_VERSION})


def connectivity_checks() -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []

    try:
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        checks.append({'name': 'DB ping', 'status': 'ok', 'hint': 'Database reachable'})
    except Exception as exc:
        checks.append({'name': 'DB ping', 'status': 'failed', 'hint': str(exc)})

    try:
        redis_url = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
        redis.Redis.from_url(redis_url).ping()
        checks.append({'name': 'Redis ping', 'status': 'ok', 'hint': 'Redis reachable'})
    except Exception as exc:
        checks.append({'name': 'Redis ping', 'status': 'failed', 'hint': str(exc)})

    try:
        response = requests.get('http://zap:8090', timeout=5)
        checks.append({'name': 'Internal ZAP ping', 'status': 'ok', 'hint': f'HTTP {response.status_code}'})
    except Exception as exc:
        checks.append({'name': 'Internal ZAP ping', 'status': 'failed', 'hint': str(exc)})

    return checks
