#!/usr/bin/env bash
set -euo pipefail

DEFAULT_INSTALL_DIR="$HOME/zapui"
DEFAULT_REPO_URL="https://github.com/zewonthefire/zapui"
DEFAULT_HTTP_PORT="8090"
DEFAULT_HTTPS_PORT="443"

read -r -p "Install directory [${DEFAULT_INSTALL_DIR}]: " INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"

read -r -p "Git repository URL [${DEFAULT_REPO_URL}]: " REPO_URL
REPO_URL="${REPO_URL:-$DEFAULT_REPO_URL}"

read -r -p "Public HTTP port [${DEFAULT_HTTP_PORT}]: " PUBLIC_HTTP_PORT
PUBLIC_HTTP_PORT="${PUBLIC_HTTP_PORT:-$DEFAULT_HTTP_PORT}"

read -r -p "Public HTTPS port [${DEFAULT_HTTPS_PORT}]: " PUBLIC_HTTPS_PORT
PUBLIC_HTTPS_PORT="${PUBLIC_HTTPS_PORT:-$DEFAULT_HTTPS_PORT}"

echo "Enabling the Ops Agent may expose additional control-plane capabilities and should only be used in trusted environments."
read -r -p "Enable Ops Agent? (yes/NO): " ENABLE_OPS_AGENT_INPUT
ENABLE_OPS_AGENT_INPUT="${ENABLE_OPS_AGENT_INPUT:-no}"
ENABLE_OPS_AGENT="no"
COMPOSE_PROFILES=""
if [[ "${ENABLE_OPS_AGENT_INPUT,,}" == "yes" || "${ENABLE_OPS_AGENT_INPUT,,}" == "y" ]]; then
  ENABLE_OPS_AGENT="yes"
  COMPOSE_PROFILES="ops"
fi

mkdir -p "${INSTALL_DIR}"

if [[ ! -d "${INSTALL_DIR}/.git" ]]; then
  echo "Cloning ${REPO_URL} into ${INSTALL_DIR}"
  git clone "${REPO_URL}" "${INSTALL_DIR}"
else
  echo "Repository exists at ${INSTALL_DIR}; pulling latest changes"
  git -C "${INSTALL_DIR}" pull --ff-only
fi

cd "${INSTALL_DIR}"

mkdir -p certs nginx/state nginx/conf.d

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

upsert_env() {
  local key="$1"
  local value="$2"
  if grep -qE "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '%s=%s\n' "${key}" "${value}" >> .env
  fi
}

upsert_env PUBLIC_HTTP_PORT "${PUBLIC_HTTP_PORT}"
upsert_env PUBLIC_HTTPS_PORT "${PUBLIC_HTTPS_PORT}"
upsert_env ENABLE_OPS_AGENT "${ENABLE_OPS_AGENT}"
upsert_env COMPOSE_PROFILES "${COMPOSE_PROFILES}"

echo "Building images..."
docker compose build

echo "Starting services..."
docker compose up -d

echo
echo "Installation complete."
echo "HTTP setup URL:  http://localhost:${PUBLIC_HTTP_PORT}/setup"
echo "Health endpoint:  http://localhost:${PUBLIC_HTTP_PORT}/health"
echo "HTTPS endpoint:   https://localhost:${PUBLIC_HTTPS_PORT}/"
echo
echo "Next steps:"
echo "1) Open /setup to complete the wizard when implemented."
echo "2) Replace temporary certs in ./certs/fullchain.pem and ./certs/privkey.pem."
echo "3) Create nginx/state/setup_complete to enforce HTTP->HTTPS redirect after setup."
echo "4) Inspect logs with: docker compose logs -f nginx web"
