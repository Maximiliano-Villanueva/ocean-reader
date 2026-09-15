# Ocean Read — UX & design review (Aug 2026)

Hands-on review at **http://localhost:8080** (1440×900, Docker stack). Screenshots: [`captures/ux-review/`](captures/ux-review/).

## Executive summary (updated after polish pass)

| Dimension | Score | Verdict |
|-----------|-------|---------|
| Visual design | 8.5/10 | Cohesive ocean/teal dark theme; card-based workspaces; clean tables |
| Clarity | 8/10 | Checklist labels, friendly dates, collapsed outcome guide |
| Ease of use | 8/10 | History table above the fold; View + More row actions; PASS runs less noisy |
| Consistency | 8.5/10 | Shared `formatSchemaKey` / `formatRunTimestamp` across pages |
| Delight | 7/10 | Modern SaaS feel; schema studio still slightly dev-facing |

**Overall: 8/10 — polished enough for persona demos and pilot users.**

### Round 2 changes (implemented)

- **Workspaces:** Card grid, deduped names, subtle “Remove” link, empty create input with placeholder
- **History:** Human “Checklist” column (`Supplier COA`), short dates, hidden empty Status column, `View` + `More` menu
- **Run detail:** No PASS explainer duplicate; FAIL/AMBIGUOUS get colored guidance blocks; field labels (`pH`)
- **Checklists:** Title shows friendly name; technical key in meta; “Edit checklist” button
- **Outcome guide:** Collapsed `<details>` by default under “Reports & exports”

---

## What works well

### Brand & shell
- **Ocean Read** header with OR mark, Workspaces / Logs, breadcrumb back to workspace name.
- **Project tabs** (Overview · History · Validate · Checklists) with short hints — clear mental model.
- Teal accent on primary actions; PASS/FAIL/AMBIGUOUS pills are instantly scannable.

### Validate flow (`03-validate.png`)
- Hero explains the job in one sentence.
- Drag/drop + file list + schema picker + batch run — obvious path.
- “Checklists” link for power users without blocking novices.

### Run detail — the product’s hero screen
- **PASS** (`06-run-pass.png`): Outcome banner, field table with extracted values, PDF pane with highlights — side-by-side works at 1440px; no horizontal overflow.
- **AMBIGUOUS** (`07-run-ambiguous.png`): Amber explainer + “multiple readings” copy; clicking a field row jumps PDF highlight — strong audit story.
- **FAIL** (`08-run-fail.png`): Red banner + missing/rule violations visible in table; export actions (CSV / JSON / copy) in header — good for QC leads.

### History (`05-history-full.png`)
- Filters (document, schema, version, outcome) are logical.
- Row actions (View, Re-run, Archive, Remove) are discoverable.
- Audit summary pills (9 passed / 8 failed / 8 need review) give leadership a one-glance snapshot.

### David workspace (`09-david-history.png`)
- Same patterns hold for AP invoice project — validates that redesign isn’t Maria-only.

---

## Issues found (by severity)

### High — fixed in this pass
1. **History: table buried below exports** — Outcome guide + dataset export + audit report appeared *before* filters and the run table. Users opening “History” had to scroll past ~3 panels to see data. **Fix:** table first; “Reports & exports” section below.

### Medium — recommend next
2. **Duplicate messaging on PASS runs** — Outcome banner and explainer block repeat the same “all required fields satisfied” idea. Collapse explainer for PASS; keep for FAIL/AMBIGUOUS.
3. **Technical labels** — `supplier_coa`, “Edit schema”, filter label “Schema” — personas think “checklist” / “template”. Align copy on Checklists page and history filters.
4. **Started column timestamps** — Full ISO with microseconds (`2026-07-27 14:46:52.042086+00:00`) clutter the table. Format as `Jul 27, 2026 · 14:46` locally.
5. **Row action density** — Four text buttons per row × 20 rows = visual noise. Consider a single “⋯” menu with View / Re-run / Archive / Remove.
6. **Workspaces list** (`01-workspaces.png`) — Duplicate demo projects; **Delete** is as prominent as **Open**. Softer destructive styling + dedupe or “demo” badge.

### Low — polish backlog
7. **Schema studio** — Token-aligned but not fully redesigned; still feels like a separate sub-app.
8. **Expected column** in field table — Long strings (`number · required · 8 – 15 · 2 aliases`). Tooltip or truncated display with expand.
9. **Status column** in history — Always `—`; hide until lifecycle states are surfaced.
10. **Onboarding** — No first-run tour; acceptable for pilot, not for self-serve.

---

## Page-by-page notes

| # | Screenshot | Notes |
|---|------------|-------|
| 01 | `01-workspaces.png` | Clear grid; create row is minimal but fine |
| 02 | `02-overview.png` | Good dashboard: stats + recent runs + CTA to validate |
| 03 | `03-validate.png` | Best upload UX in the app |
| 04 | `04-checklists.png` | Version list works; “Edit schema” / field keys too dev-facing |
| 05 | `05-history-full.png` | Strong audit table; was top-heavy before reorder |
| 06 | `06-run-pass.png` | Layout stable; export chips visible |
| 07 | `07-run-ambiguous.png` | Best demo screen for “human in the loop” |
| 08 | `08-run-fail.png` | Clear failure reasons |
| 09 | `09-david-history.png` | Parity with Maria workspace |

---

## Accessibility & layout checks

- **Horizontal overflow:** None at 1440×900 on workspaces, overview, validate, history, run detail (automated audit).
- **Contrast:** Dark theme passes casual inspection; formal WCAG audit not run.
- **Keyboard:** Filters and table links reachable; PDF row click targets improved (no `rowSpan` intercept).

---

### Round 4 — wizard dedupe + onboarding (latest)

- **Wizard:** Command-bar Checklist ID hidden while in wizard mode; single field in step 1 with “Shows as Supplier COA” preview
- **Overview:** Dismissible “How Ocean Read works” quick-start tour (3 steps with ✓ when done); persists via localStorage per project
- **Publish gate:** Create checklist disabled until Checklist ID is set

### Remaining backlog

1. Re-record Maria + David demo videos with new UI
2. Optional backend export API
3. Spotlight-style guided tour (if needed beyond quick-start banner)

---

## How to re-run capture

```bash
# App at http://localhost:8080
node scripts/e2e/ux_design_review.mjs
```

Outputs refresh under `docs/personas/captures/ux-review/`.
