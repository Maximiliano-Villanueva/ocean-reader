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
MAX_WAIT_SECONDS="${START_MAX_WAIT_SECONDS:-240}"
WAIT_INTERVAL_SECONDS="${START_WAIT_INTERVAL_SECONDS:-3}"

echo "Ocean Read — starting from ${ROOT}"

if ! docker info >/dev/null 2>&1; then
  echo "Error: Docker is not running or this user cannot reach the Docker daemon." >&2
  echo "Start Docker Desktop (or your engine), then retry." >&2
  exit 1
fi

echo "Building and starting containers (first run or after code changes can take several minutes)..."

curl_health() {
  local enabled
  enabled="$(printf '%s' "${EDGE_AUTH_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')"
  if [[ "${enabled}" == "1" || "${enabled}" == "true" || "${enabled}" == "yes" ]]; then
    if [[ -z "${EDGE_API_TOKEN:-}" ]]; then
      echo "Error: EDGE_AUTH_ENABLED is true but EDGE_API_TOKEN is empty. Set EDGE_API_TOKEN in .env." >&2
      return 2
    fi
    curl -sfS -H "Authorization: Bearer ${EDGE_API_TOKEN}" "${HEALTH_URL}" -o /dev/null
  else
    curl -sfS "${HEALTH_URL}" -o /dev/null
  fi
}

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
echo "Ensuring default workspace + wine_quality @ 1.0 validation schema (idempotent; safe after empty DB)..."
set +e
python3 "${ROOT}/scripts/ensure_default_validation.py"
SEED_RC=$?
set -e
if [[ "${SEED_RC}" -ne 0 ]]; then
  echo "Warning: default validation seed script exited ${SEED_RC}. Create a project from the UI or run the script manually." >&2
fi

echo ""
echo "Ready — UI and API:"
echo "  http://127.0.0.1:${GATEWAY_PORT}/"
echo "  GET ${HEALTH_URL}"
echo "  OpenAPI: http://127.0.0.1:${GATEWAY_PORT}/docs"
echo ""
echo "Optional validation LLM fallback uses Ollama at OLLAMA_BASE_URL (Compose: host.docker.internal:11434)."
echo "Optional CoreDNS: dig @127.0.0.1 -p ${COREDNS_P} +short gateway.ocean-read.internal"
echo ""
echo "Postgres and uploads use Docker named volumes; this script does not remove them."
echo "To wipe app data: ./scripts/empty_dev_testing.sh  (see docs/DOCKER.md)."
echo ""
echo "Optional Airflow is NOT started (needs profile): docker compose --profile airflow up -d"
echo "  UI: http://127.0.0.1:\${AIRFLOW_UI_PORT:-8794}/ — unrelated to the validation product."
