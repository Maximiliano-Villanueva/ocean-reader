#!/usr/bin/env bash
# Stop Ocean Read Docker Compose stack (containers and default network; named volumes are kept).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "Ocean Read — stopping Compose stack in ${ROOT}"
docker compose down
echo "Done. Volumes kept (Postgres, uploads). Remove data with: docker compose down -v"
