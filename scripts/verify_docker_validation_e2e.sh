#!/usr/bin/env bash
# End-to-end check: Traefik → API → validate PDF → M2 pdf_hash + snapshot sub-resources + list filter.
# Prereq: ``docker compose up -d`` (or ``./start.sh``) with a healthy stack on GATEWAY_HTTP_PORT (default 8080).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Prefer backend venv so PyMuPDF is available without a global install.
PYTHON="${OCEAN_VERIFY_PYTHON:-python3}"
if [[ -x "${ROOT}/backend/.venv/bin/python3" ]]; then
  PYTHON="${ROOT}/backend/.venv/bin/python3"
fi

set -a
# shellcheck disable=1091
[[ -f .env ]] && source .env
set +a

PORT="${GATEWAY_HTTP_PORT:-8080}"
BASE="http://127.0.0.1:${PORT}"

curl_health() {
  local enabled
  enabled="$(printf '%s' "${EDGE_AUTH_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')"
  if [[ "${enabled}" == "1" || "${enabled}" == "true" || "${enabled}" == "yes" ]]; then
    [[ -n "${EDGE_API_TOKEN:-}" ]] || { echo "EDGE_AUTH_ENABLED but EDGE_API_TOKEN empty" >&2; return 2; }
    curl -sfS -H "Authorization: Bearer ${EDGE_API_TOKEN}" "$BASE/api/health" -o /dev/null
  else
    curl -sfS "$BASE/api/health" -o /dev/null
  fi
}

echo "Waiting for ${BASE}/api/health ..."
for _ in $(seq 1 60); do
  if curl_health; then break; fi
  sleep 2
done
echo "API healthy."

python3 "${ROOT}/scripts/ensure_default_validation.py"

PID="$(curl -sfS "$BASE/api/projects" | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['id'])")"
echo "Using project_id=${PID}"

PDF="${TMPDIR:-/tmp}/ocean_read_docker_verify.pdf"
"${PYTHON}" <<PY
import fitz
doc = fitz.open()
page = doc.new_page()
y = 72
for line in ("Wine QA Report", "pH: 3.5", "Alcohol: 12%", "Quality: 7"):
    page.insert_text((72, y), line)
    y += 18
open("${PDF}", "wb").write(doc.tobytes())
doc.close()
PY

AUTH=()
if [[ "$(printf '%s' "${EDGE_AUTH_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')" =~ ^(1|true|yes)$ ]]; then
  AUTH=(-H "Authorization: Bearer ${EDGE_API_TOKEN}")
fi

curl_api() {
  if [[ ${#AUTH[@]} -gt 0 ]]; then
    curl -sfS "${AUTH[@]}" "$@"
  else
    curl -sfS "$@"
  fi
}

RESP="$(curl_api -X POST "$BASE/api/validate-document" \
  -F "project_id=${PID}" \
  -F "schema_id=wine_quality" \
  -F "schema_version=1.0" \
  -F "document=@${PDF};type=application/pdf")"

RUN_ID="$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['run_id'])")"
STATUS="$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])")"
echo "validate-document: status=${STATUS} run_id=${RUN_ID}"

if command -v shasum >/dev/null 2>&1; then
  EXP="sha256:$(shasum -a 256 "$PDF" | awk '{print $1}')"
elif command -v sha256sum >/dev/null 2>&1; then
  EXP="sha256:$(sha256sum "$PDF" | awk '{print $1}')"
else
  echo "Need shasum or sha256sum for fingerprint check" >&2
  exit 1
fi

DET="$(curl_api "$BASE/api/projects/${PID}/validation-runs/${RUN_ID}")"
HASH="$(echo "$DET" | python3 -c "import json,sys; print(json.load(sys.stdin).get('pdf_hash',''))")"
[[ "$HASH" == "$EXP" ]] || { echo "pdf_hash mismatch: got=$HASH expected=$EXP" >&2; exit 1; }
echo "pdf_hash OK"

BLOCKS="$(curl_api "$BASE/api/projects/${PID}/validation-runs/${RUN_ID}/blocks")"
echo "$BLOCKS" | python3 -c "import json,sys; b=json.load(sys.stdin); assert len(b)>=1, b"
echo "blocks OK"

CANDS="$(curl_api "$BASE/api/projects/${PID}/validation-runs/${RUN_ID}/candidates")"
echo "$CANDS" | python3 -c "import json,sys; c=json.load(sys.stdin); assert len(c)>=1, c"
echo "candidates OK"

RES="$(curl_api "$BASE/api/projects/${PID}/validation-runs/${RUN_ID}/resolved")"
echo "$RES" | python3 -c "import json,sys; r=json.load(sys.stdin); assert 'ph' in r and 'alcohol' in r, r"
echo "resolved OK"

LIST="$(curl_api "$BASE/api/projects/${PID}/validation-runs?status=PASS&page_size=25")"
echo "$LIST" | python3 -c "import json,sys; p=json.load(sys.stdin); assert p['total']>=1; assert all(x['outcome']=='PASS' for x in p['items'])"
echo "list filter OK"

echo "verify_docker_validation_e2e: ALL PASSED"
