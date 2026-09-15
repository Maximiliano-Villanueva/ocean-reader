#!/usr/bin/env bash
# Reset validation schemas to a small demo set: 3 schema keys (one with 2 versions).
# Usage: ./scripts/seed_demo_schemas.sh [project_name]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

set -a
# shellcheck disable=1091
[[ -f .env ]] && source .env
set +a

PORT="${GATEWAY_HTTP_PORT:-8080}"
BASE="http://127.0.0.1:${PORT}"
PROJECT_NAME="${1:-Default workspace}"

AUTH=()
if [[ "$(printf '%s' "${EDGE_AUTH_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')" =~ ^(1|true|yes)$ ]]; then
  [[ -n "${EDGE_API_TOKEN:-}" ]] || { echo "EDGE_AUTH_ENABLED but EDGE_API_TOKEN empty" >&2; exit 2; }
  AUTH=(-H "Authorization: Bearer ${EDGE_API_TOKEN}")
fi

curl_api() {
  if [[ ${#AUTH[@]} -gt 0 ]]; then
    curl -sfS "${AUTH[@]}" "$@"
  else
    curl -sfS "$@"
  fi
}

echo "Waiting for ${BASE}/api/health ..."
for _ in $(seq 1 60); do
  if curl_api "$BASE/api/health" -o /dev/null 2>/dev/null; then break; fi
  sleep 2
done
curl_api "$BASE/api/health" -o /dev/null

PID="$(curl_api "$BASE/api/projects" | python3 -c "
import json,sys
name=sys.argv[1]
ps=json.load(sys.stdin)
p=next((x for x in ps if x['name']==name), None)
if not p:
    raise SystemExit(f'Project not found: {name!r}')
print(p['id'])
" "$PROJECT_NAME")"
echo "project_id=${PID}"

echo "Deleting existing schema versions ..."
IDS="$(curl_api "$BASE/api/projects/${PID}/validation-schemas" | python3 -c "
import json,sys
for g in json.load(sys.stdin):
    for v in g.get('versions',[]):
        print(v['id'])
")"
while IFS= read -r vid; do
  [[ -z "$vid" ]] && continue
  curl_api -X DELETE "$BASE/api/projects/${PID}/validation-schemas/${vid}" >/dev/null || true
  echo "deleted ${vid}"
done <<< "$IDS"

post_schema() {
  local key="$1" version="$2" body_file="$3"
  local payload
  payload="$(python3 - "$key" "$version" "$body_file" <<'PY'
import json, sys
key, version, body_file = sys.argv[1:4]
print(json.dumps({
    "schema_key": key,
    "version_label": version,
    "archive_previous_active": True,
    "body": json.load(open(body_file)),
}))
PY
)"
  curl_api -X POST "$BASE/api/projects/${PID}/validation-schemas" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null
  echo "created ${key}@${version}"
}

INVOICE_V1="${ROOT}/scripts/fixtures/demo_invoice_v1.json"
INVOICE_V2="${ROOT}/scripts/fixtures/demo_invoice_v2.json"
WINE="${ROOT}/backend/src/ocean_read/domain/validation/default_wine_schema.py"

mkdir -p "${ROOT}/scripts/fixtures"
python3 -c "
import json
from pathlib import Path

v1 = {
    'version': '3',
    'fields': {
        'invoice_number': {
            'type': 'string',
            'required': True,
            'aliases': ['Invoice Nº', 'invoice number'],
            'semantic_role': 'document_identifier',
            'llm_fallback': True,
        },
        'issue_date': {
            'type': 'date',
            'required': False,
            'aliases': ['Fecha', 'issue date'],
            'semantic_role': 'issue_date',
            'llm_fallback': True,
        },
        'total_due': {
            'type': 'number',
            'required': True,
            'aliases': ['TOTAL INVOICE', 'total due'],
            'semantic_role': 'document_total',
            'min': 0,
            'llm_fallback': True,
        },
    },
    'rules': ['required', 'range_validation', 'type_check'],
    'extraction': {'understand_document': True, 'context_pass': 'when_needed'},
    'open_ended': {
        'recipient_name': {
            'extract_prompt': 'Extract the bill-to recipient name',
            'informative_only': True,
            'link_evidence': True,
        },
    },
}
v2 = json.loads(json.dumps(v1))
v2['fields']['issue_date']['required'] = True
v2['fields']['currency'] = {
    'type': 'string',
    'required': False,
    'aliases': ['€', 'EUR', 'USD'],
    'llm_fallback': True,
}
Path('$INVOICE_V1').write_text(json.dumps(v1, indent=2))
Path('$INVOICE_V2').write_text(json.dumps(v2, indent=2))
"

# Wine body from Python module constant
WINE_JSON="$(python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('dws', '${ROOT}/backend/src/ocean_read/domain/validation/default_wine_schema.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
import json
print(json.dumps(mod.DEFAULT_WINE_QUALITY_SCHEMA_BODY))
")"

DELIVERY_JSON="$(python3 -c "
import json
print(json.dumps({
  'version': '3',
  'fields': {
    'order_id': {'type': 'string', 'required': True, 'aliases': ['Order', 'PO number']},
    'ship_date': {'type': 'date', 'required': False, 'aliases': ['Ship date', 'Fecha envío'], 'llm_fallback': True},
    'item_count': {'type': 'number', 'required': True, 'min': 1, 'aliases': ['Items', 'Qty']},
  },
  'rules': ['required', 'range_validation', 'type_check'],
}))
")"

post_schema invoice 1.0 "$INVOICE_V1"
post_schema invoice 2.0 "$INVOICE_V2"

echo "$WINE_JSON" > /tmp/demo_wine.json
post_schema wine_quality 1.0 /tmp/demo_wine.json

echo "$DELIVERY_JSON" > /tmp/demo_delivery.json
post_schema delivery_note 1.0 /tmp/demo_delivery.json

echo ""
echo "Done. Schema keys: invoice (1.0 + 2.0), wine_quality (1.0), delivery_note (1.0)"
