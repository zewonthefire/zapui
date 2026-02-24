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
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "CELERY_BROKER_URL",
    "ENABLE_OPS_AGENT",
]


class ServicePayload(BaseModel):
    services: list[str] = Field(default_factory=list)


def _compose_cmd(*parts: str) -> list[str]:
    return ["docker", "compose", "--project-name", PROJECT_NAME, *parts]


def _run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=PROJECT_DIR, text=True, capture_output=True, check=False)


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


@app.get("/compose/env-summary", dependencies=[Depends(_auth)])
def compose_env_summary() -> dict[str, str]:
    return {key: os.getenv(key, "") for key in SAFE_ENV_KEYS}
