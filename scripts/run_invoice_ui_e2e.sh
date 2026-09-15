#!/usr/bin/env bash
# Browser E2E wrapper for invoice validation UI test.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}/scripts/e2e"
if [[ ! -d node_modules/playwright ]]; then
  npm install --silent
  npx playwright install chromium
fi
node invoice_validation.mjs
