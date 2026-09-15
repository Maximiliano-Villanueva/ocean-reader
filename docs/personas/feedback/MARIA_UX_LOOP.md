# Maria Reyes — UX test loop (completed)

## Persona

**Maria Reyes**, QC Lab Manager at Riverbank Beverages. She evaluates Ocean Read as if buying it for supplier CoA validation. She is not technical.

**Workspace created:** `Riverbank QC Lab — Maria Reyes`  
**Customer agent:** `.cursor/agents/maria-qc-customer.md`

## What we ran

```bash
./scripts/run_maria_persona_e2e.sh
```

Full browser journey: workspace → checklist wizard (lab report) → batch validate 3 PDFs → history → fail detail with PDF evidence.

## Artifacts for sales

| Type | Location |
|------|----------|
| **Video (81s)** | `docs/personas/captures/maria/maria-journey.webm` |
| **Screenshots** | `docs/personas/captures/maria/01-*.png` … `14-*.png` |
| **Raw feedback** | `docs/personas/feedback/MARIA_SESSION_FEEDBACK.md` |

## Issues found → fixes shipped

| Maria's complaint | Severity | Fix |
|-------------------|----------|-----|
| "Projects / schema" is developer language | P0 | Tabs: **Checklists**, **Validate**, **History**; overview = **Quality dashboard** |
| Overview empty / not actionable | P1 | Stats (pass/fail/review), 3-step guide, recent validations list |
| No batch summary after validating many PDFs | P1 | **Batch complete: N passed · M failed · …** banner |
| Why PASS when something missing? | P1 | Green explainer on PASS runs: required vs optional fields |
| Misaligned hero / dropzone text | P2 | `text-align: left` on shell + project pages |
| Remove (×) button wrong corner on queue | P2 | Positioned top-right on status cards |
| "Schema key" in wizard | P2 | Renamed **Checklist ID** with helper text |
| Workspaces landing lacks value prop | P2 | Added audit/evidence tagline |

## Remaining roadmap (honest for sales)

- Exportable audit pack (PDF/CSV) for C-level
- Email / database connectors (James persona)
- ETA when ambiguous/LLM path is slow (~1 min/doc)
- Publish success toast ("Checklist is live")

## Scores after fixes

| Screen | Score |
|--------|-------|
| Workspaces | 4/5 |
| Quality dashboard | 4/5 |
| Checklist wizard | 4/5 |
| Validate batch | **5/5** |
| Run detail (FAIL) | 4/5 |

**Verdict:** Sellable for PDF CoA workflow demo; position integrations and export as roadmap.
