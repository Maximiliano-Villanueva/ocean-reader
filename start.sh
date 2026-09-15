#!/usr/bin/env bash
# Start Ocean Read (Docker Compose): build images, run stack, wait until Traefik proxies a healthy API.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

set -a
if [[ -f .env ]]; then
  # shellcheck disable=1091
  source .env
fi
set +a

GATEWAY_PORT="${GATEWAY_HTTP_PORT:-8080}"
COREDNS_P="${COREDNS_UDP_PORT:-55353}"
HEALTH_URL="http://127.0.0.1:${GATEWAY_PORT}/api/health"
PROJECTS_URL="http://127.0.0.1:${GATEWAY_PORT}/api/projects"
MAX_WAIT_SECONDS="${START_MAX_WAIT_SECONDS:-240}"
WAIT_INTERVAL_SECONDS="${START_WAIT_INTERVAL_SECONDS:-3}"
OLLAMA_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
LLM_MODEL_NAME="${LLM_MODEL:-gemma4:e4b}"
DEFAULT_PROJECT_NAME="Default workspace"

# Seed script reads these (same values as curl helpers below).
export GATEWAY_HTTP_PORT="${GATEWAY_PORT}"
export EDGE_AUTH_ENABLED="${EDGE_AUTH_ENABLED:-false}"
export EDGE_API_TOKEN="${EDGE_API_TOKEN:-}"
export SEED_MAX_WAIT_SECONDS="${SEED_MAX_WAIT_SECONDS:-${MAX_WAIT_SECONDS}}"

echo "Ocean Read — starting from ${ROOT}"

if ! docker info >/dev/null 2>&1; then
  echo "Error: Docker is not running or this user cannot reach the Docker daemon." >&2
  echo "Start Docker Desktop (or your engine), then retry." >&2
  exit 1
fi

edge_auth_enabled() {
  local enabled
  enabled="$(printf '%s' "${EDGE_AUTH_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')"
  [[ "${enabled}" == "1" || "${enabled}" == "true" || "${enabled}" == "yes" ]]
}

curl_api() {
  local url="$1"
  if edge_auth_enabled; then
    if [[ -z "${EDGE_API_TOKEN:-}" ]]; then
      echo "Error: EDGE_AUTH_ENABLED is true but EDGE_API_TOKEN is empty. Set EDGE_API_TOKEN in .env." >&2
      return 2
    fi
    curl -sfS -H "Authorization: Bearer ${EDGE_API_TOKEN}" "${url}"
  else
    curl -sfS "${url}"
  fi
}

curl_health() {
  curl_api "${HEALTH_URL}" -o /dev/null
}

curl_projects() {
  curl_api "${PROJECTS_URL}" -o /dev/null
}

has_default_workspace() {
  python3 -c "
import sys
sys.path.insert(0, '${ROOT}/scripts')
from ensure_default_validation import has_default_workspace_project
sys.exit(0 if has_default_workspace_project() else 1)
"
}

run_workspace_seed() {
  python3 "${ROOT}/scripts/ensure_default_validation.py"
}

seed_with_retries() {
  local label="$1"
  local attempts="${2:-${START_SEED_ATTEMPTS:-5}}"
  local sleep_s="${3:-${START_SEED_RETRY_SECONDS:-5}}"
  local attempt rc=1
  echo ""
  echo "${label}"
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if run_workspace_seed; then
      return 0
    fi
    rc=$?
    if ((attempt < attempts)); then
      echo "  Seed attempt ${attempt}/${attempts} failed (exit ${rc}); retrying in ${sleep_s}s..." >&2
      sleep "${sleep_s}"
    fi
  done
  return "${rc}"
}

echo "Building and starting containers (first run or after code changes can take several minutes)..."

if ! docker compose up --build -d; then
  echo ""
  echo "Compose failed (ports in use?). Postgres host port defaults to POSTGRES_PUBLISH=15432 — override in .env." >&2
  echo "If 8080 is busy, set GATEWAY_HTTP_PORT in .env." >&2
  exit 1
fi

echo ""
echo "Waiting for Traefik to proxy a healthy backend (Alembic runs on backend startup; timeout ${MAX_WAIT_SECONDS}s)..."

started="${SECONDS}"
until curl_health; do
  err=$?
  if [[ "${err}" -eq 2 ]]; then
    exit 1
  fi
  elapsed=$((SECONDS - started))
  if ((elapsed >= MAX_WAIT_SECONDS)); then
    echo ""
    echo "Timed out waiting for ${HEALTH_URL}" >&2
    echo "Compose status:" >&2
    docker compose ps -a >&2 || true
    echo "" >&2
    echo "Recent backend logs:" >&2
    docker compose logs --tail 100 backend >&2 || true
    exit 1
  fi
  sleep "${WAIT_INTERVAL_SECONDS}"
done

echo ""
echo "Waiting for project API (timeout ${MAX_WAIT_SECONDS}s)..."
started="${SECONDS}"
until curl_projects; do
  err=$?
  if [[ "${err}" -eq 2 ]]; then
    exit 1
  fi
  elapsed=$((SECONDS - started))
  if ((elapsed >= MAX_WAIT_SECONDS)); then
    echo ""
    echo "Timed out waiting for ${PROJECTS_URL}" >&2
    docker compose logs --tail 80 backend >&2 || true
    exit 1
  fi
  sleep "${WAIT_INTERVAL_SECONDS}"
done

if ! seed_with_retries "Ensuring ${DEFAULT_PROJECT_NAME} + wine_quality @ 1.0 (idempotent)..."; then
  echo "" >&2
  echo "Error: could not seed ${DEFAULT_PROJECT_NAME}." >&2
  if edge_auth_enabled && [[ -z "${EDGE_API_TOKEN:-}" ]]; then
    echo "  Set EDGE_API_TOKEN in .env, then run ./start.sh again." >&2
  else
    echo "  Check: docker compose logs backend" >&2
    echo "  Then run ./start.sh again." >&2
  fi
  exit 1
fi

if ! has_default_workspace; then
  echo "Warning: ${DEFAULT_PROJECT_NAME} not visible after seed; retrying once..." >&2
  if ! seed_with_retries "Re-seeding workspace..." 3 "${START_SEED_RETRY_SECONDS:-5}"; then
    echo "Error: ${DEFAULT_PROJECT_NAME} still missing after seed." >&2
    exit 1
  fi
fi

echo ""
echo "Checking Ollama on host (${OLLAMA_URL}, model ${LLM_MODEL_NAME})..."
if curl -sfS "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
  if curl -sfS "${OLLAMA_URL}/api/tags" | grep -q "${LLM_MODEL_NAME%%:*}"; then
    echo "  Ollama reachable; model family present."
  else
    echo "  Warning: pull the model on the host: ollama pull ${LLM_MODEL_NAME}" >&2
  fi
else
  echo "  Warning: Ollama not reachable at ${OLLAMA_URL}. Start Ollama, then: ollama pull ${LLM_MODEL_NAME}" >&2
fi

echo ""
echo "Waiting for schema-agent (requires Ollama from the host)..."
schema_started="${SECONDS}"
SCHEMA_AGENT_MAX_WAIT="${START_SCHEMA_AGENT_MAX_WAIT_SECONDS:-120}"
until docker compose exec -T schema-agent python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/health', timeout=5)" >/dev/null 2>&1; do
  elapsed=$((SECONDS - schema_started))
  if ((elapsed >= SCHEMA_AGENT_MAX_WAIT)); then
    echo "Warning: schema-agent not healthy after ${SCHEMA_AGENT_MAX_WAIT}s." >&2
    echo "  Ensure Ollama is running and: ollama pull ${LLM_MODEL_NAME}" >&2
    echo "  Check: docker compose logs -f schema-agent" >&2
    break
  fi
  sleep "${WAIT_INTERVAL_SECONDS}"
done

if ! has_default_workspace; then
  echo ""
  echo "Final check: ${DEFAULT_PROJECT_NAME} missing — seeding again..." >&2
  if ! seed_with_retries "Final workspace seed..." 3 "${START_SEED_RETRY_SECONDS:-5}"; then
    echo "Error: ${DEFAULT_PROJECT_NAME} could not be created." >&2
    exit 1
  fi
  if ! has_default_workspace; then
    echo "Error: ${DEFAULT_PROJECT_NAME} still missing. Run ./start.sh again after checking backend logs." >&2
    exit 1
  fi
fi

echo ""
echo "Ready — UI and API:"
echo "  http://127.0.0.1:${GATEWAY_PORT}/projects"
echo "  http://127.0.0.1:${GATEWAY_PORT}/"
echo "  GET ${HEALTH_URL}"
echo "  OpenAPI: http://127.0.0.1:${GATEWAY_PORT}/docs"
echo ""
echo "Default project: ${DEFAULT_PROJECT_NAME}"
echo ""
echo "Schema assistant uses Ollama (${LLM_MODEL_NAME}) at ${OLLAMA_URL} from containers via host.docker.internal."
echo "Optional: VALIDATION_LLM_FALLBACK_ENABLED, VALIDATION_OPEN_ENDED_ENABLED, VALIDATION_LLM_VISION_ENABLED in .env"
echo "Optional CoreDNS: dig @127.0.0.1 -p ${COREDNS_P} +short gateway.ocean-read.internal"
echo ""
echo "Postgres and uploads use Docker named volumes; this script does not remove them."
echo "To wipe app data: ./scripts/empty_dev_testing.sh  (see docs/DOCKER.md)."
echo ""
echo "Optional Airflow is NOT started (needs profile): docker compose --profile airflow up -d"
echo "  UI: http://127.0.0.1:\${AIRFLOW_UI_PORT:-8794}/ — unrelated to the validation product."
