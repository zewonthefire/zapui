import os
import subprocess
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="zapui-ops-agent")

PROJECT_NAME = os.getenv("COMPOSE_PROJECT_NAME", "zapui")
PROJECT_DIR = Path(os.getenv("OPS_PROJECT_DIR", "/workspace"))
OPS_AGENT_TOKEN = os.getenv("OPS_AGENT_TOKEN", "")
ENABLE_OPS_AGENT = os.getenv("ENABLE_OPS_AGENT", "false").lower() in {"1", "true", "yes", "on"}
SAFE_ENV_KEYS = [
    "COMPOSE_PROJECT_NAME",
    "PUBLIC_HTTP_PORT",
    "PUBLIC_HTTPS_PORT",
    "DJANGO_DEBUG",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "CELERY_BROKER_URL",
    "ENABLE_OPS_AGENT",
    "ZAP_API_KEY",
]


class ServicePayload(BaseModel):
    services: list[str] = Field(default_factory=list)


class ScalePayload(BaseModel):
    service: str
    replicas: int = Field(ge=0, le=50)


class CsrfOriginPayload(BaseModel):
    origin: str


class ZapApiKeyPayload(BaseModel):
    api_key: str


def _compose_cmd(*parts: str) -> list[str]:
    return ["docker", "compose", "--project-name", PROJECT_NAME, *parts]


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=PROJECT_DIR, text=True, capture_output=True, check=False)


def _upsert_env_var(env_file: Path, key: str, value: str) -> None:
    lines: list[str] = []
    if env_file.exists():
        lines = env_file.read_text().splitlines()

    filtered = [line for line in lines if not line.startswith(f"{key}=")]
    filtered.append(f"{key}={value}")
    env_file.write_text("\n".join(filtered) + "\n")


def _upsert_compose_zap_api_key(compose_file: Path, _api_key: str) -> None:
    if not compose_file.exists():
        raise HTTPException(status_code=500, detail="docker-compose.yml not found")

    lines = compose_file.read_text().splitlines()
    prefix = "      ZAP_API_KEY:"
    desired = "      ZAP_API_KEY: ${ZAP_API_KEY:-change-me-zap-key}"
    for idx, line in enumerate(lines):
        if line.startswith(prefix):
            lines[idx] = desired
            compose_file.write_text("\n".join(lines) + "\n")
            return

    raise HTTPException(status_code=500, detail="ZAP_API_KEY line not found in docker-compose.yml")


def _allowed_services() -> set[str]:
    result = _run_command(_compose_cmd("ps", "--all", "--format", "json"))
    if result.returncode != 0:
        raise HTTPException(status_code=503, detail=f"compose discovery failed: {result.stderr.strip()}")

    allowed: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        import json

        entry = json.loads(line)
        service = entry.get("Service")
        if service:
            allowed.add(service)
    return allowed


def _require_valid_services(services: list[str]) -> list[str]:
    allowed = _allowed_services()
    invalid = [svc for svc in services if svc not in allowed]
    if invalid:
        raise HTTPException(status_code=403, detail=f"service(s) not allowed: {', '.join(invalid)}")
    return services


def _auth(x_ops_token: str = Header(default="")) -> None:
    if not ENABLE_OPS_AGENT:
        raise HTTPException(status_code=403, detail="ops agent is disabled")
    if not OPS_AGENT_TOKEN:
        raise HTTPException(status_code=503, detail="OPS_AGENT_TOKEN is not configured")
    if x_ops_token != OPS_AGENT_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ops-agent"}


@app.get("/compose/services", dependencies=[Depends(_auth)])
def compose_services() -> dict[str, Any]:
    allowed = sorted(_allowed_services())
    result = _run_command(_compose_cmd("ps", "--all", "--format", "json"))
    rows = []
    import json

    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        entry = json.loads(line)
        if entry.get("Service") in allowed:
            rows.append(entry)
    return {"project": PROJECT_NAME, "services": rows}


@app.get("/compose/logs/{service}", dependencies=[Depends(_auth)])
def compose_logs(service: str, tail: int = 200) -> dict[str, Any]:
    _require_valid_services([service])
    result = _run_command(_compose_cmd("logs", f"--tail={max(1, min(tail, 1000))}", service))
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr.strip())
    return {"service": service, "logs": result.stdout}


@app.post("/compose/restart/{service}", dependencies=[Depends(_auth)])
def compose_restart(service: str) -> dict[str, str]:
    _require_valid_services([service])
    result = _run_command(_compose_cmd("restart", service))
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr.strip())
    return {"status": "ok", "action": "restart", "service": service}


@app.post("/compose/rebuild", dependencies=[Depends(_auth)])
def compose_rebuild(payload: ServicePayload) -> dict[str, Any]:
    services = _require_valid_services(payload.services)
    result = _run_command(_compose_cmd("build", *services))
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr.strip())
    return {"status": "ok", "action": "rebuild", "services": services}


@app.post("/compose/redeploy", dependencies=[Depends(_auth)])
def compose_redeploy(payload: ServicePayload) -> dict[str, Any]:
    services = _require_valid_services(payload.services)
    result = _run_command(_compose_cmd("up", "-d", "--no-deps", *services))
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr.strip())
    return {"status": "ok", "action": "redeploy", "services": services}




@app.post("/compose/scale", dependencies=[Depends(_auth)])
def compose_scale(payload: ScalePayload) -> dict[str, Any]:
    _require_valid_services([payload.service])
    result = _run_command(_compose_cmd("up", "-d", "--scale", f"{payload.service}={payload.replicas}", payload.service))
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr.strip())
    return {"status": "ok", "action": "scale", "service": payload.service, "replicas": payload.replicas}


@app.get("/compose/env-summary", dependencies=[Depends(_auth)])
def compose_env_summary() -> dict[str, str]:
    return {key: os.getenv(key, "") for key in SAFE_ENV_KEYS}


@app.post("/compose/env/upsert-csrf-origin", dependencies=[Depends(_auth)])
def compose_upsert_csrf_origin(payload: CsrfOriginPayload) -> dict[str, Any]:
    origin = payload.origin.strip()
    if not origin.startswith("https://"):
        raise HTTPException(status_code=400, detail="origin must start with https://")
    if any(ch in origin for ch in ("\n", "\r")):
        raise HTTPException(status_code=400, detail="origin must be a single line")

    env_file = PROJECT_DIR / ".env"
    _upsert_env_var(env_file, "DJANGO_CSRF_TRUSTED_ORIGINS", origin)

    result = _run_command(_compose_cmd("up", "-d", "--force-recreate", "web", "nginx"))
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr.strip())

    return {
        "status": "ok",
        "action": "upsert-csrf-origin",
        "origin": origin,
        "services": ["web", "nginx"],
    }


@app.post("/compose/env/upsert-zap-api-key", dependencies=[Depends(_auth)])
def compose_upsert_zap_api_key(payload: ZapApiKeyPayload) -> dict[str, Any]:
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key is required")
    if any(ch in api_key for ch in ("\n", "\r")):
        raise HTTPException(status_code=400, detail="api_key must be a single line")

    env_file = PROJECT_DIR / ".env"
    compose_file = PROJECT_DIR / "docker-compose.yml"
    _upsert_env_var(env_file, "ZAP_API_KEY", api_key)
    _upsert_compose_zap_api_key(compose_file, api_key)

    result = _run_command(_compose_cmd("up", "-d", "--force-recreate", "zap"))
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr.strip())

    return {
        "status": "ok",
        "action": "upsert-zap-api-key",
        "services": ["zap"],
    }
