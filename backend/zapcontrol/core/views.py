import os
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import redis
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from targets.models import Project, RiskSnapshot, Target, ZapNode

from .models import Setting, SetupState

OPS_ENABLED = os.getenv('ENABLE_OPS_AGENT', 'false').lower() in {'1', 'true', 'yes', 'on'}
OPS_AGENT_URL = os.getenv('OPS_AGENT_URL', 'http://ops:8091')
OPS_AGENT_TOKEN = os.getenv('OPS_AGENT_TOKEN', '')
OPS_SERVICES = ['nginx', 'web', 'worker', 'beat', 'db', 'redis', 'zap', 'pdf', 'ops']
SETUP_FLAG_PATH = Path('/nginx-state/setup_complete')
CERT_DIR = Path('/certs')
EXTERNAL_DB_CONFIG_PATH = Path('/nginx-state/external_db_config.env')


def _setup_state() -> SetupState:
    state, _ = SetupState.objects.get_or_create(pk=1)
    return state


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


def _save_setting(key: str, value):
    Setting.objects.update_or_create(key=key, defaults={'value': value})


def _node_healthcheck_url(node: ZapNode) -> str:
    return f"{node.base_url.rstrip('/')}/JSON/core/view/version/"


def _test_node_connectivity(node: ZapNode):
    started = time.perf_counter()
    params = {'apikey': node.api_key} if node.api_key else None
    response = requests.get(_node_healthcheck_url(node), params=params, timeout=10)
    latency_ms = int((time.perf_counter() - started) * 1000)
    response.raise_for_status()
    payload = response.json()
    version = payload.get('version', '')

    node.last_health_check = timezone.now()
    node.last_latency_ms = latency_ms
    node.status = ZapNode.STATUS_HEALTHY
    node.version = version
    node.save(update_fields=['last_health_check', 'last_latency_ms', 'status', 'version'])
    return version, latency_ms


def _discover_internal_zap_containers() -> list[str]:
    if not OPS_ENABLED:
        return []
    response = _ops_get('/compose/services')
    response.raise_for_status()
    containers = []
    for row in response.json().get('services', []):
        if row.get('Service') != 'zap':
            continue
        state = str(row.get('State', '')).lower()
        if state != 'running':
            continue
        name = row.get('Name')
        if name:
            containers.append(name)
    return sorted(containers)


def _sync_internal_nodes() -> tuple[int, int]:
    containers = _discover_internal_zap_containers()
    seen_names: set[str] = set()
    created = 0
    for index, container_name in enumerate(containers, start=1):
        node_name = f'internal-zap-{index}'
        defaults = {
            'base_url': f'http://{container_name}:8090',
            'managed_type': ZapNode.MANAGED_INTERNAL,
            'docker_container_name': container_name,
            'enabled': True,
            'status': ZapNode.STATUS_UNKNOWN,
        }
        _, was_created = ZapNode.objects.update_or_create(name=node_name, defaults=defaults)
        if was_created:
            created += 1
        seen_names.add(node_name)

    disabled = 0
    to_disable = ZapNode.objects.filter(managed_type=ZapNode.MANAGED_INTERNAL).exclude(name__in=seen_names)
    for node in to_disable:
        node.enabled = False
        node.status = ZapNode.STATUS_DISABLED
        node.save(update_fields=['enabled', 'status'])
        disabled += 1
    return created, disabled


def _strong_password(password: str, user=None):
    validate_password(password, user=user)


def _external_host(url: str) -> str:
    parsed = urlparse(url)
    return parsed.hostname or ''


def _cert_paths() -> tuple[Path, Path]:
    return CERT_DIR / 'fullchain.pem', CERT_DIR / 'privkey.pem'


def _validate_existing_certs() -> tuple[bool, str]:
    cert_file, key_file = _cert_paths()
    if not cert_file.exists() or not key_file.exists():
        return False, 'Expected /certs/fullchain.pem and /certs/privkey.pem.'
    cmd = ['openssl', 'x509', '-in', str(cert_file), '-noout']
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return False, f'Certificate invalid: {result.stderr.strip()}'
    return True, 'Certificate files look valid.'


def _generate_self_signed_cert(external_base_url: str) -> tuple[bool, str]:
    cert_file, key_file = _cert_paths()
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    host = _external_host(external_base_url)
    sans = ['DNS:localhost', 'IP:127.0.0.1']
    if host:
        sans.append(f'DNS:{host}')
    san_value = ','.join(sans)
    cmd = [
        'openssl',
        'req',
        '-x509',
        '-nodes',
        '-newkey',
        'rsa:2048',
        '-days',
        '365',
        '-keyout',
        str(key_file),
        '-out',
        str(cert_file),
        '-subj',
        f'/CN={host or "localhost"}',
        '-addext',
        f'subjectAltName={san_value}',
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return False, f'OpenSSL failed: {result.stderr.strip()}'
    return True, f'Generated self-signed cert with SANs: {san_value}'


def _normalize_external_base_url(url: str) -> str:
    normalized = url.strip()
    if normalized and '://' not in normalized:
        normalized = f'http://{normalized}'
    return normalized


def _get_database_config_from_post(post_data) -> dict[str, str]:
    mode = post_data.get('database_mode', 'integrated').strip() or 'integrated'
    config = {
        'mode': mode,
        'name': post_data.get('external_db_name', '').strip(),
        'user': post_data.get('external_db_user', '').strip(),
        'password': post_data.get('external_db_password', ''),
        'host': post_data.get('external_db_host', '').strip(),
        'port': post_data.get('external_db_port', '5432').strip() or '5432',
    }
    return config


def _test_external_postgres_connection(config: dict[str, str]) -> tuple[bool, str]:
    required = ['name', 'user', 'password', 'host', 'port']
    missing = [k for k in required if not config.get(k)]
    if missing:
        return False, f"Missing external DB fields: {', '.join(missing)}"

    try:
        with psycopg.connect(
            dbname=config['name'],
            user=config['user'],
            password=config['password'],
            host=config['host'],
            port=int(config['port']),
            connect_timeout=5,
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
    except Exception as exc:
        return False, f'External PostgreSQL connection failed: {exc}'

    return True, 'External PostgreSQL connection successful.'


def _write_external_db_runtime_config(config: dict[str, str]) -> None:
    EXTERNAL_DB_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXTERNAL_DB_CONFIG_PATH.write_text(
        '\n'.join(
            [
                f"DJANGO_DB_ENGINE=postgres",
                f"POSTGRES_HOST={config['host']}",
                f"POSTGRES_PORT={config['port']}",
                f"POSTGRES_DB={config['name']}",
                f"POSTGRES_USER={config['user']}",
                f"POSTGRES_PASSWORD={config['password']}",
                '',
            ]
        )
    )


def _disable_internal_db() -> tuple[bool, str]:
    if OPS_ENABLED:
        try:
            response = _ops_post('/compose/scale', json={'service': 'db', 'replicas': 0})
            response.raise_for_status()
            return True, 'Internal DB disabled via Ops Agent scaling (db=0).'
        except Exception as exc:
            return False, f'Unable to disable internal DB automatically: {exc}'

    return False, 'Ops Agent disabled. Run: docker compose stop db (after applying external DB env and restarting services).'


def health(request):
    return JsonResponse({'status': 'ok'})


def setup(request):
    state = _setup_state()
    data = dict(state.wizard_data or {})

    if state.is_complete:
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            step = max(1, min(5, int(request.POST.get('step', state.current_step))))
        except ValueError:
            step = state.current_step
        action = request.POST.get('action', 'next')

        if step == 1:
            instance_name = request.POST.get('instance_name', '').strip()
            external_base_url = _normalize_external_base_url(request.POST.get('external_base_url', ''))
            display_http_port = request.POST.get('display_http_port', '').strip()
            db_config = _get_database_config_from_post(request.POST)

            if not instance_name or not external_base_url:
                messages.error(request, 'Instance name and external base URL are required.')
            else:
                db_ok = True
                db_note = 'Using integrated internal PostgreSQL service.'
                if db_config['mode'] == 'external':
                    db_ok, db_note = _test_external_postgres_connection(db_config)

                if db_ok:
                    data['instance'] = {
                        'instance_name': instance_name,
                        'external_base_url': external_base_url,
                        'display_http_port': display_http_port,
                    }
                    data['database'] = db_config
                    data['database_connectivity'] = db_note
                    _save_setting('instance', data['instance'])
                    _save_setting('database', db_config)
                    state.current_step = 2
                    messages.success(request, db_note)
                else:
                    messages.error(request, db_note)

        elif step == 2:
            email = request.POST.get('admin_email', '').strip().lower()
            password = request.POST.get('admin_password', '')
            if not email or not password:
                messages.error(request, 'Email and password are required.')
            else:
                User = get_user_model()
                user_for_validation = User(email=email)
                try:
                    _strong_password(password, user=user_for_validation)
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
                else:
                    admin_user = User.objects.filter(email=email).first()
                    if admin_user is None:
                        admin_user = User(email=email)
                    admin_user.is_staff = True
                    admin_user.is_superuser = True
                    admin_user.role = 'admin'
                    admin_user.set_password(password)
                    admin_user.save()

                    data['admin_email'] = email
                    state.current_step = 3
                    messages.success(request, 'Admin user configured.')

        elif step == 3:
            tls_mode = request.POST.get('tls_mode', 'generate')
            external_base_url = data.get('instance', {}).get('external_base_url', '')
            ok, msg = (False, 'Unknown mode')
            if tls_mode == 'provided':
                ok, msg = _validate_existing_certs()
            else:
                ok, msg = _generate_self_signed_cert(external_base_url)
            if ok:
                data['tls_mode'] = tls_mode
                data['tls_note'] = msg
                state.current_step = 4
                messages.success(request, msg)
            else:
                messages.error(request, msg)

        elif step == 4:
            pool_size_raw = request.POST.get('zap_pool_size', '1').strip() or '1'
            external_url = request.POST.get('external_zap_base_url', '').strip()
            external_key = request.POST.get('external_zap_api_key', '').strip()
            add_external = request.POST.get('add_external') == 'on'
            try:
                pool_size = max(1, int(pool_size_raw))
            except ValueError:
                pool_size = 1
            pool_applied = True
            pool_warning = ''

            if OPS_ENABLED:
                try:
                    response = _ops_post('/compose/scale', json={'service': 'zap', 'replicas': pool_size})
                    response.raise_for_status()
                    _sync_internal_nodes()
                except Exception as exc:
                    pool_applied = False
                    pool_warning = f'Ops scaling failed: {exc}'
            elif pool_size > 1:
                pool_applied = False
                pool_warning = f'Run: make scale-zap N={pool_size}'

            if add_external and external_url:
                try:
                    node, _ = ZapNode.objects.update_or_create(
                        base_url=external_url,
                        defaults={
                            'name': f'external-{external_url.replace("http://", "").replace("https://", "").replace(":", "-").replace("/", "-")[:80]}',
                            'api_key': external_key,
                            'enabled': True,
                            'managed_type': ZapNode.MANAGED_EXTERNAL,
                            'docker_container_name': None,
                        },
                    )
                    _test_node_connectivity(node)
                    messages.success(request, 'External ZAP node connectivity test succeeded.')
                except Exception as exc:
                    messages.error(request, f'External ZAP connectivity failed: {exc}')

            data['zap'] = {
                'pool_size': pool_size,
                'external_enabled': add_external,
                'external_url': external_url,
            }
            _save_setting('zap', data['zap'])
            state.pool_applied = pool_applied
            state.pool_warning = pool_warning
            state.current_step = 5

        elif step == 5 and action == 'finalize':
            checks = connectivity_checks(data.get('database', {}))
            cert_ok, cert_hint = _validate_existing_certs()
            checks.append({'name': 'TLS cert files', 'status': 'ok' if cert_ok else 'failed', 'hint': cert_hint})

            db_mode = data.get('database', {}).get('mode', 'integrated')
            if db_mode == 'external':
                _write_external_db_runtime_config(data['database'])
                db_disabled, db_disable_hint = _disable_internal_db()
                checks.append({'name': 'Disable internal DB', 'status': 'ok' if db_disabled else 'warning', 'hint': db_disable_hint})
                data['internal_db_disable_note'] = db_disable_hint

            failed = [c for c in checks if c['status'] == 'failed']
            data['health_checks'] = checks
            if failed:
                messages.warning(request, 'Some health checks failed. You can still finalize if intentional.')

            SETUP_FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
            SETUP_FLAG_PATH.write_text('complete\n')
            state.is_complete = True
            state.current_step = 5
            external_base_url = data.get('instance', {}).get('external_base_url', '')
            https_url = external_base_url.replace('http://', 'https://') if external_base_url else 'https://localhost:8443'
            data['final_https_url'] = https_url
            messages.success(request, f'Setup complete. Continue at {https_url}')

        if action == 'back':
            state.current_step = max(1, step - 1)

        state.wizard_data = data
        state.save()

    requested_step = request.GET.get('step')
    step = state.current_step
    if requested_step and requested_step.isdigit():
        step = max(1, min(state.current_step, int(requested_step)))

    context = {
        'state': state,
        'step': step,
        'wizard_data': state.wizard_data or {},
        'checks': connectivity_checks((state.wizard_data or {}).get('database', {})) if step == 5 else [],
        'ops_enabled': OPS_ENABLED,
    }
    return render(request, 'core/setup.html', context)


@login_required
def dashboard(request):
    latest_global = RiskSnapshot.objects.filter(project__isnull=True, target__isnull=True).first()
    trends = list(
        RiskSnapshot.objects.filter(project__isnull=True, target__isnull=True)
        .order_by('-created_at')[:10]
        .values('created_at', 'risk_score')
    )
    trends.reverse()
    projects = Project.objects.order_by('name')
    targets = Target.objects.select_related('project').order_by('project__name', 'name')
    return render(
        request,
        'core/dashboard.html',
        {'latest_global': latest_global, 'trends': trends, 'projects': projects, 'targets': targets},
    )


@login_required
def ops_overview(request):
    denied = _admin_only(request)
    if denied:
        return denied

    status_rows = []
    checks = connectivity_checks()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'test_all_nodes':
            tested, failed = _test_all_nodes()
            if failed:
                messages.warning(request, f'Tested {tested} nodes with {failed} failures.')
            else:
                messages.success(request, f'Tested {tested} nodes successfully.')
            return redirect('ops-overview')
        if action == 'scale_internal_pool':
            if not OPS_ENABLED:
                messages.error(request, 'Ops Agent must be enabled for internal scaling.')
                return redirect('ops-overview')
            try:
                replicas = max(0, int(request.POST.get('desired_pool_size', '1')))
                response = _ops_post('/compose/scale', json={'service': 'zap', 'replicas': replicas})
                response.raise_for_status()
                created, disabled = _sync_internal_nodes()
                _save_setting('zap_internal_pool', {'desired_size': replicas})
                messages.success(request, f'Internal pool scaled to {replicas}. Registered {created}, disabled {disabled}.')
            except Exception as exc:
                messages.error(request, f'Failed to scale internal pool: {exc}')
            return redirect('ops-overview')

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

    pool_setting = Setting.objects.filter(key='zap_internal_pool').first()
    desired_pool_size = (pool_setting.value or {}).get('desired_size', 1) if pool_setting else 1

    return render(
        request,
        'core/ops_overview.html',
        {
            'ops_enabled': OPS_ENABLED,
            'status_rows': status_rows,
            'checks': checks,
            'desired_pool_size': desired_pool_size,
            'nodes': ZapNode.objects.order_by('name'),
        },
    )


@login_required
def zapnodes(request):
    denied = _admin_only(request)
    if denied:
        return denied

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_external':
            name = request.POST.get('name', '').strip()
            base_url = request.POST.get('base_url', '').strip()
            api_key = request.POST.get('api_key', '').strip()
            if not name or not base_url:
                messages.error(request, 'Name and base URL are required.')
            else:
                node = ZapNode.objects.create(
                    name=name,
                    base_url=base_url,
                    api_key=api_key,
                    enabled=True,
                    managed_type=ZapNode.MANAGED_EXTERNAL,
                )
                messages.success(request, f'Added external node {node.name}.')
        elif action == 'remove_external':
            node = ZapNode.objects.filter(pk=request.POST.get('node_id'), managed_type=ZapNode.MANAGED_EXTERNAL).first()
            if node:
                node.delete()
                messages.success(request, 'External node removed.')
        elif action == 'test_node':
            node = ZapNode.objects.filter(pk=request.POST.get('node_id')).first()
            if node:
                try:
                    version, latency = _test_node_connectivity(node)
                    messages.success(request, f'{node.name} healthy (version {version}, {latency} ms).')
                except Exception as exc:
                    node.last_health_check = timezone.now()
                    node.status = ZapNode.STATUS_UNREACHABLE
                    node.save(update_fields=['last_health_check', 'status'])
                    messages.error(request, f'Node {node.name} test failed: {exc}')
        elif action == 'test_all_nodes':
            tested, failed = _test_all_nodes()
            if failed:
                messages.warning(request, f'Tested {tested} nodes with {failed} failures.')
            else:
                messages.success(request, f'Tested {tested} nodes successfully.')
        return redirect('zapnodes')

    return render(request, 'core/zapnodes.html', {'nodes': ZapNode.objects.order_by('name')})


def _test_all_nodes() -> tuple[int, int]:
    tested = 0
    failed = 0
    for node in ZapNode.objects.filter(enabled=True):
        tested += 1
        try:
            _test_node_connectivity(node)
        except Exception:
            failed += 1
            node.last_health_check = timezone.now()
            node.status = ZapNode.STATUS_UNREACHABLE
            node.save(update_fields=['last_health_check', 'status'])
    return tested, failed


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


def connectivity_checks(database_config: dict | None = None) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []

    database_mode = (database_config or {}).get('mode', 'integrated')
    if database_mode == 'external':
        ok, hint = _test_external_postgres_connection(database_config or {})
        checks.append({'name': 'External PostgreSQL ping', 'status': 'ok' if ok else 'failed', 'hint': hint})
    else:
        try:
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
            checks.append({'name': 'Internal DB ping', 'status': 'ok', 'hint': 'Database reachable'})
        except Exception as exc:
            checks.append({'name': 'Internal DB ping', 'status': 'failed', 'hint': str(exc)})

    try:
        redis_url = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
        redis.Redis.from_url(redis_url).ping()
        checks.append({'name': 'Redis ping', 'status': 'ok', 'hint': 'Redis reachable'})
    except Exception as exc:
        checks.append({'name': 'Redis ping', 'status': 'failed', 'hint': str(exc)})

    nodes = ZapNode.objects.filter(enabled=True)
    if not nodes.exists():
        checks.append({'name': 'ZAP nodes', 'status': 'warning', 'hint': 'No enabled ZAP nodes configured.'})
    else:
        tested, failed = _test_all_nodes()
        checks.append({'name': 'ZAP nodes', 'status': 'ok' if failed == 0 else 'failed', 'hint': f'Tested {tested}, failures {failed}'})

    return checks
