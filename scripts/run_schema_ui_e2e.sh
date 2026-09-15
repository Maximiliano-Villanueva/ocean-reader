#!/usr/bin/env bash
# Browser E2E for schema UI redesign (wizard, workspace, simple, publish).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}/scripts/e2e"
if [[ ! -d node_modules/playwright ]]; then
  npm install --silent
  npx playwright install chromium
fi
node schema_ui_redesign.mjs
