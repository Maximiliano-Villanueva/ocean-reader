#!/usr/bin/env bash
# Invoice E2E: create agent schema → validate inv_cursor_formatted.pdf → assert ground truth.
# Prereq: ``./start.sh`` or ``docker compose up -d`` on GATEWAY_HTTP_PORT (default 8080).
# Requires Ollama on host for contextual extraction + open-ended fields.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

set -a
# shellcheck disable=1091
[[ -f .env ]] && source .env
set +a

PORT="${GATEWAY_HTTP_PORT:-8080}"
BASE="http://127.0.0.1:${PORT}"
PDF="${ROOT}/backend/tests/fixtures/invoice/inv_cursor_formatted.pdf"
SCHEMA_JSON="${ROOT}/backend/tests/fixtures/invoice/schema_inv_cursor_agent_prompt.json"
SCHEMA_KEY="inv_cursor_agent"
SCHEMA_VERSION="1.0"

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
for _ in $(seq 1 90); do
  if curl_api "$BASE/api/health" -o /dev/null 2>/dev/null; then break; fi
  sleep 2
done
curl_api "$BASE/api/health" -o /dev/null
echo "API healthy."

PID="$(curl_api "$BASE/api/projects" | python3 -c "
import json,sys
ps=json.load(sys.stdin)
print(next(p['id'] for p in ps if p['name']=='Default workspace'))
")"
echo "project_id=${PID}"

# Upsert invoice schema (ignore 409 if already exists).
BODY="$(python3 -c "import json; print(json.dumps({'schema_key':'${SCHEMA_KEY}','version_label':'${SCHEMA_VERSION}','body':json.load(open('${SCHEMA_JSON}'))}))")"
if ! curl_api -X POST "$BASE/api/projects/${PID}/validation-schemas" \
  -H "Content-Type: application/json" \
  -d "$BODY" >/dev/null 2>&1; then
  echo "Schema ${SCHEMA_KEY}@${SCHEMA_VERSION} already exists (ok)."
fi

echo "Validating ${PDF} ..."
RESP="$(curl_api -X POST "$BASE/api/validate-document" \
  -F "project_id=${PID}" \
  -F "schema_id=${SCHEMA_KEY}" \
  -F "schema_version=${SCHEMA_VERSION}" \
  -F "document=@${PDF};type=application/pdf")"

echo "$RESP" | python3 -c "
import json, sys

resp = json.load(sys.stdin)
status = resp.get('status')
run_id = resp.get('run_id')
meta = resp.get('extraction_meta') or {}
resolved = resp.get('resolved_values') or {}

strict_truth = {
    'invoice_number': 'DOEA864B-0011',
    'recipient_email': 'mvillanueva.tolcachier@gmail.com',
    'issue_date': '9 de agosto de 2025',
    'due_date': '9 de agosto de 2025',
    'total_due': 20.0,
}

print(f'status={status} run_id={run_id}')
print(f\"parser={meta.get('parser')} read_images={meta.get('read_images')} markdown_chars={meta.get('markdown_chars')}\")

assert status == 'PASS', f'expected PASS, got {status!r} errors={resp.get(\"errors\")} ambiguous={resp.get(\"ambiguous_fields\")}'
assert meta.get('parser') == 'docling', f'expected docling parser, got {meta.get(\"parser\")!r}'

for field, expected in strict_truth.items():
    assert field in resolved, f'missing resolved field {field!r}'
    got = resolved[field]
    if isinstance(expected, float):
        assert abs(float(got) - expected) < 0.001, f'{field}: got {got!r} expected {expected!r}'
    elif field.endswith('_date'):
        assert str(expected).lower() in str(got).lower(), f'{field}: got {got!r} expected {expected!r}'
    else:
        assert str(got) == str(expected), f'{field}: got {got!r} expected {expected!r}'

oe = {r['field']: r.get('extracted_value') for r in (resp.get('open_ended_results') or [])}
if oe:
    print('open_ended:', oe)
    if 'recipient_name' in oe and oe['recipient_name']:
        assert 'villanueva' in str(oe['recipient_name']).lower(), oe['recipient_name']

print('INVOICE_GROUND_TRUTH_OK')
"

RUN_ID="$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['run_id'])")"
BLOCKS="$(curl_api "$BASE/api/projects/${PID}/validation-runs/${RUN_ID}/blocks")"
echo "$BLOCKS" | python3 -c "import json,sys; b=json.load(sys.stdin); assert len(b)>=5, f'expected blocks for highlights, got {len(b)}'"
echo "blocks OK (count=$(echo "$BLOCKS" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"))"

echo ""
echo "verify_invoice_validation_e2e: ALL PASSED"
echo "Run detail UI: ${BASE}/projects/${PID}/validation/runs/${RUN_ID}"
