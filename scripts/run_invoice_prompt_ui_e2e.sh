#!/usr/bin/env bash
# Browser E2E: AI assistant creates invoice schema from user prompt + PDF validation.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}/scripts/e2e"
if [[ ! -d node_modules/playwright ]]; then
  npm install --silent
  npx playwright install chromium
fi
node invoice_prompt_schema.mjs
