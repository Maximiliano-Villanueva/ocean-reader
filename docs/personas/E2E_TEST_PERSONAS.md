# E2E test personas

Two buyer personas drive how we test Ocean Read end-to-end. Each persona has a **project**, **schemas**, **PDF corpus**, and a **customer agent** prompt for blind UX review.

## Persona 1 — Maria Reyes (Lab QC Manager)

| | |
|--|--|
| **Role** | QC Lab Manager, Riverbank Beverages |
| **Goal** | Automate review of supplier Certificates of Analysis (CoA); sign off batches with evidence for audits and leadership |
| **Fears** | Wrong number released; auditor asks “how did you know?”; team re-types PDF data |
| **Success** | Schema = signed policy; every PDF → PASS/FAIL/AMBIGUOUS with PDF evidence; history = audit trail |

**Platform journey**

1. Create workspace project  
2. New schema → **Lab report** template → publish as `supplier_coa`  
3. Validate batch: clean CoA, out-of-spec, ambiguous  
4. History → filter FAIL → open run → PDF highlights  
5. (Roadmap) Export audit summary for C-level  

**Corpus** — `backend/tests/fixtures/wine/` (canonical CoA domain)

| PDF | Expected |
|-----|----------|
| `clean/row_000_clean.pdf` | PASS |
| `fail_schema/syn_fs_alcohol_high.pdf` | FAIL |
| `ambiguous/syn_amb_ph_dup.pdf` | AMBIGUOUS |

**Agent** — [MARIA_CUSTOMER_AGENT.md](./MARIA_CUSTOMER_AGENT.md)

---

## Persona 2 — James Okonkwo (Industrial QA / Audit prep)

| | |
|--|--|
| **Role** | QA Manager, mid-size manufacturing plant |
| **Goal** | Sample documents across processes before external audit; prove checks were run against frozen rule sets |
| **Fears** | Evidence scattered (email, folders, DB); inconsistent layouts; no proof of sampling |
| **Success** | Multiple document types, one platform; frozen schema versions; searchable history |

**Platform journey**

1. Three schemas: `delivery_note`, `invoice` (v1 + v2), `supplier_coa`  
2. 5+ PDFs per type, mixed outcomes  
3. Filter history by schema + outcome  
4. (Roadmap) Connectors for email / exports  

**Corpus** — `scripts/fixtures/personas/james_industrial/` (generated)

**Agent** — [JAMES_CUSTOMER_AGENT.md](./JAMES_CUSTOMER_AGENT.md)

---

## Artifacts

| Path | Purpose |
|------|---------|
| `docs/personas/captures/maria/` | Screenshots + video from Maria journey |
| `docs/personas/feedback/` | Session feedback markdown |
| `scripts/fixtures/personas/generate_persona_fixtures.py` | Build James PDF fixtures |
| `scripts/e2e/maria_lab_persona_journey.mjs` | Playwright journey + recording |
| `scripts/run_maria_persona_e2e.sh` | One-command run |

## Ground truth JSON

Each persona PDF has a sidecar in `scripts/fixtures/personas/`:

```json
{
  "persona": "maria",
  "schema_key": "supplier_coa",
  "schema_version": "1.0",
  "expected_outcome": "PASS",
  "audit_note": "Routine supplier CoA"
}
```
