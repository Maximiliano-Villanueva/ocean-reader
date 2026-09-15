#!/usr/bin/env bash
# Generate fixtures + record Maria (lab) and David (AP invoice) sales demo videos.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

set -a
# shellcheck disable=1091
[[ -f .env ]] && source .env
set +a

PORT="${GATEWAY_HTTP_PORT:-8080}"

echo "==> Fixtures"
python3 scripts/fixtures/personas/generate_persona_fixtures.py
(cd backend && uv run python ../scripts/fixtures/personas/generate_david_invoices.py)

echo "==> Waiting for API on :${PORT}"
for _ in $(seq 1 60); do
  curl -sf "http://127.0.0.1:${PORT}/api/health" -o /dev/null 2>/dev/null && break
  sleep 2
done

(cd scripts/e2e && npm install --silent 2>/dev/null; npx playwright install chromium 2>/dev/null)

echo "==> Rebuild backend (tight bbox) + frontend"
docker compose build backend frontend 2>&1 | tail -5
docker compose up -d 2>&1 | tail -5
sleep 5

echo "==> Maria lab demo"
GATEWAY_HTTP_PORT="$PORT" node scripts/e2e/maria_lab_persona_journey.mjs

echo "==> David AP demo (schema agent — may take several minutes)"
GATEWAY_HTTP_PORT="$PORT" node scripts/e2e/david_ap_persona_demo.mjs

echo ""
echo "Videos:"
echo "  docs/personas/captures/maria/maria-journey.webm"
echo "  docs/personas/captures/david/david-journey.webm"
