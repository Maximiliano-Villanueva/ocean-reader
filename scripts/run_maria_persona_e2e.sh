#!/usr/bin/env bash
# Maria Reyes persona journey — browser E2E with screenshots + video.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

set -a
# shellcheck disable=1091
[[ -f .env ]] && source .env
set +a

echo "Generating persona fixtures..."
python3 scripts/fixtures/personas/generate_persona_fixtures.py

echo "Installing Playwright (if needed)..."
(cd scripts/e2e && npm install --silent 2>/dev/null || true)
(cd scripts/e2e && npx playwright install chromium 2>/dev/null || true)

echo "Waiting for gateway..."
PORT="${GATEWAY_HTTP_PORT:-8080}"
for _ in $(seq 1 60); do
  curl -sf "http://127.0.0.1:${PORT}/api/health" -o /dev/null 2>/dev/null && break
  sleep 2
done

echo "Running Maria persona journey..."
GATEWAY_HTTP_PORT="$PORT" node scripts/e2e/maria_lab_persona_journey.mjs

echo ""
echo "Artifacts:"
echo "  Screenshots: docs/personas/captures/maria/"
echo "  Video:       docs/personas/captures/maria/video/"
echo "  Feedback:    docs/personas/feedback/MARIA_SESSION_FEEDBACK.md"
