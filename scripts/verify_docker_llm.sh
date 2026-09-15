#!/usr/bin/env bash
# Quick check: Ollama on host + schema-agent health through Compose network.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
MODEL="${LLM_MODEL:-gemma4:e4b}"

echo "==> Ollama /api/tags at $OLLAMA_URL"
curl -sf "$OLLAMA_URL/api/tags" | head -c 400 || {
  echo "Ollama not reachable. Start Ollama on the host and: ollama pull $MODEL"
  exit 1
}
echo ""

echo "==> schema-agent /health (in container)"
docker compose exec -T schema-agent python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8081/health', timeout=10).read().decode())" \
  || { echo "schema-agent unhealthy — check logs"; exit 1; }

echo "OK"
