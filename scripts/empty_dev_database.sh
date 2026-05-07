#!/usr/bin/env bash
# Wipe all projects (CASCADE: documents, BYTEA, chunks + pgvector embeddings, sessions, …).
# For uploads volume + DB together, use scripts/empty_dev_testing.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! docker compose ps --status running db >/dev/null 2>&1; then
  echo "Error: db service is not running. From repo root: docker compose up -d db" >&2
  exit 1
fi

docker compose exec -T db psql -U "${POSTGRES_USER:-ocean}" -d "${POSTGRES_DB:-ocean_read}" -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;
DELETE FROM projects;
INSERT INTO organizations (id, name)
SELECT '00000000-0000-4000-8000-000000000001'::uuid, 'Default organization'
WHERE NOT EXISTS (SELECT 1 FROM organizations WHERE id = '00000000-0000-4000-8000-000000000001'::uuid);
COMMIT;
SQL

echo "All projects removed; default organization ensured."
