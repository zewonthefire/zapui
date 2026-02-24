#!/usr/bin/env bash
set -euo pipefail

DEFAULT_INSTALL_DIR="${HOME}/projects/zapui"
DEFAULT_REPO_URL="https://github.com/zewonthefire/zapui"
DEFAULT_HTTP_PORT="8090"
DEFAULT_HTTPS_PORT="8093"
DEFAULT_PUBLIC_HOST="$(hostname -f 2>/dev/null || hostname 2>/dev/null || echo localhost)"

color() { printf "\033[%sm%s\033[0m\n" "$1" "$2"; }
status() { color "1;34" "[INFO] $*"; }
ok() { color "1;32" "[OK]   $*"; }
warn() { color "1;33" "[WARN] $*"; }

prompt_default() {
  local prompt="$1"; local default="$2"; local value
  read -r -p "${prompt} [${default}]: " value
  printf "%s" "${value:-$default}"
}

prompt_yes_no() {
  local prompt="$1"; local default="$2"; local value
  read -r -p "${prompt} (${default}): " value
  value="${value:-$default}"
  case "${value,,}" in
    y|yes) printf "yes" ;;
    *) printf "no" ;;
  esac
}

command -v git >/dev/null || { echo "git is required" >&2; exit 1; }
command -v docker >/dev/null || { echo "docker is required" >&2; exit 1; }

auto_env_value() {
  local env_file="$1"; local key="$2"; local fallback="$3"
  if [[ -f "$env_file" ]]; then
    local existing
    existing="$(awk -F= -v k="$key" '$1==k {print substr($0, index($0, "=")+1)}' "$env_file" | tail -n1)"
    if [[ -n "$existing" ]]; then
      printf "%s" "$existing"
      return
    fi
  fi
  printf "%s" "$fallback"
}

upsert_env() {
  local env_file="$1"; local key="$2"; local value="$3"
  if grep -qE "^${key}=" "$env_file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$env_file"
  fi
}

ensure_compose_zap_key_uses_env() {
  local compose_file="$1"
  if [[ ! -f "$compose_file" ]]; then
    warn "docker-compose.yml not found, skipping compose ZAP_API_KEY sync"
    return
  fi

  python3 - "$compose_file" <<'PY'
from pathlib import Path
import sys

compose_path = Path(sys.argv[1])
target = "      ZAP_API_KEY:"
desired = "      ZAP_API_KEY: ${ZAP_API_KEY:-change-me-zap-key}"

lines = compose_path.read_text().splitlines()
updated = False
for idx, line in enumerate(lines):
    if line.startswith(target):
        lines[idx] = desired
        updated = True
        break

if not updated:
    raise SystemExit("unable to find zap environment ZAP_API_KEY line in docker-compose.yml")

compose_path.write_text("\n".join(lines) + "\n")
PY

  ok "Normalized docker-compose.yml ZAP_API_KEY to read from .env"
}

random_api_key() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 24
    return
  fi
  python3 - <<'PYKEY'
import secrets
print(secrets.token_hex(24))
PYKEY
}

status "ZapUI installer (idempotent). Safe to run multiple times."

INSTALL_DIR="$(prompt_default "Install directory" "$DEFAULT_INSTALL_DIR")"
REPO_URL="$(prompt_default "Git repository URL" "$DEFAULT_REPO_URL")"
mkdir -p "$INSTALL_DIR"

if [[ ! -d "${INSTALL_DIR}/.git" ]]; then
  status "Cloning repository into ${INSTALL_DIR}"
  git clone "$REPO_URL" "$INSTALL_DIR"
  ok "Repository cloned"
else
  status "Repository already exists at ${INSTALL_DIR}"
  CURRENT_REMOTE="$(git -C "$INSTALL_DIR" remote get-url origin 2>/dev/null || true)"
  if [[ -n "$CURRENT_REMOTE" && "$CURRENT_REMOTE" != "$REPO_URL" ]]; then
    warn "Requested repo differs from current origin: ${CURRENT_REMOTE}"
  fi
  PULL_LATEST="$(prompt_yes_no "Pull latest code now?" "yes")"
  if [[ "$PULL_LATEST" == "yes" ]]; then
    git -C "$INSTALL_DIR" pull --ff-only
    ok "Repository updated"
  else
    warn "Skipping git pull; using existing checkout"
  fi
fi

cd "$INSTALL_DIR"
mkdir -p certs nginx/state nginx/conf.d

if [[ ! -f .env ]]; then
  cp .env.example .env
  ok "Created .env from .env.example"
else
  ok "Using existing .env"
fi

CURRENT_ZAP_API_KEY="$(auto_env_value .env ZAP_API_KEY "")"
if [[ -z "$CURRENT_ZAP_API_KEY" || "$CURRENT_ZAP_API_KEY" == "change-me-zap-key" ]]; then
  GENERATED_ZAP_API_KEY="$(random_api_key)"
  upsert_env .env ZAP_API_KEY "$GENERATED_ZAP_API_KEY"
  ACTIVE_ZAP_API_KEY="$GENERATED_ZAP_API_KEY"
  ok "Generated internal ZAP API key and saved to .env"
else
  ACTIVE_ZAP_API_KEY="$CURRENT_ZAP_API_KEY"
  ok "Keeping existing internal ZAP API key from .env"
fi

ensure_compose_zap_key_uses_env "docker-compose.yml"

HTTP_DEFAULT="$(auto_env_value .env PUBLIC_HTTP_PORT "$DEFAULT_HTTP_PORT")"
HTTPS_DEFAULT="$(auto_env_value .env PUBLIC_HTTPS_PORT "$DEFAULT_HTTPS_PORT")"
OPS_DEFAULT="$(auto_env_value .env ENABLE_OPS_AGENT "false")"
CSRF_ORIGINS_DEFAULT="$(auto_env_value .env DJANGO_CSRF_TRUSTED_ORIGINS "")"

if [[ -n "$CSRF_ORIGINS_DEFAULT" ]]; then
  CSRF_HOST_DEFAULT="$(printf '%s' "$CSRF_ORIGINS_DEFAULT" | cut -d',' -f1 | sed -E 's#^https?://##' | cut -d':' -f1)"
else
  CSRF_HOST_DEFAULT="$DEFAULT_PUBLIC_HOST"
fi

PUBLIC_HTTP_PORT="$(prompt_default "Public HTTP port" "$HTTP_DEFAULT")"
PUBLIC_HTTPS_PORT="$(prompt_default "Public HTTPS port" "$HTTPS_DEFAULT")"
PUBLIC_HOSTNAME="$(prompt_default "Public hostname for HTTPS/CSRF" "$CSRF_HOST_DEFAULT")"

if [[ "${OPS_DEFAULT,,}" == "true" || "${OPS_DEFAULT,,}" == "1" || "${OPS_DEFAULT,,}" == "yes" ]]; then
  OPS_QUESTION_DEFAULT="yes"
else
  OPS_QUESTION_DEFAULT="no"
fi

warn "Ops Agent uses Docker socket and should only be enabled in trusted environments."
ENABLE_OPS_INPUT="$(prompt_yes_no "Enable Ops Agent" "$OPS_QUESTION_DEFAULT")"
ENABLE_OPS_AGENT="false"
COMPOSE_PROFILES=""
if [[ "$ENABLE_OPS_INPUT" == "yes" ]]; then
  ENABLE_OPS_AGENT="true"
  COMPOSE_PROFILES="ops"
fi

upsert_env .env PUBLIC_HTTP_PORT "$PUBLIC_HTTP_PORT"
upsert_env .env PUBLIC_HTTPS_PORT "$PUBLIC_HTTPS_PORT"
upsert_env .env ENABLE_OPS_AGENT "$ENABLE_OPS_AGENT"
upsert_env .env COMPOSE_PROFILES "$COMPOSE_PROFILES"
upsert_env .env DJANGO_CSRF_TRUSTED_ORIGINS "https://${PUBLIC_HOSTNAME}:${PUBLIC_HTTPS_PORT}"
ok "Updated .env values"

BUILD_ACTION="$(prompt_yes_no "Build/rebuild images" "yes")"
if [[ "$BUILD_ACTION" == "yes" ]]; then
  status "Building images"
  docker compose build --pull
  ok "Image build completed"
else
  warn "Skipping image build"
fi

status "Applying compose changes (ports/profiles/env)"
docker compose up -d --remove-orphans
ok "Services are running"

docker compose -f ${INSTALL_DIR}/docker-compose.yml down
docker compose -f ${INSTALL_DIR}/docker-compose.yml up -d

status "Current service status"
docker compose ps

echo
ok "Installation/update complete"
echo "Setup URL:       http://${PUBLIC_HOSTNAME}:${PUBLIC_HTTP_PORT}/setup"
echo "Health endpoint: http://${PUBLIC_HOSTNAME}:${PUBLIC_HTTP_PORT}/health"
echo "HTTPS endpoint:  https://${PUBLIC_HOSTNAME}:${PUBLIC_HTTPS_PORT}/"
