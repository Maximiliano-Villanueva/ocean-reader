#!/usr/bin/env bash
# Wipe application data for local testing: all projects (CASCADE removes documents, chunks,
# embeddings in Postgres), default org row ensured, and files under the backend upload volume.
# Does NOT remove Docker volumes themselves (use docker compose down -v for that).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

"$ROOT/scripts/empty_dev_database.sh"

clear_uploads() {
  docker compose exec -T backend sh -c 'find /data/uploads -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true'
}

if docker compose ps --status running backend >/dev/null 2>&1; then
  clear_uploads
  echo "Cleared files under backend /data/uploads (volume ocean_uploads)."
elif docker compose ps -a --format '{{.Service}}' 2>/dev/null | grep -qx backend; then
  echo "Starting a one-off backend container to clear uploads volume..."
  docker compose run --rm --no-deps backend sh -c 'find /data/uploads -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true'
  echo "Cleared files under /data/uploads on volume ocean_uploads."
else
  echo "Note: no backend service in this compose project — skipped upload volume cleanup."
  echo "  After docker compose up, run: $0"
fi
