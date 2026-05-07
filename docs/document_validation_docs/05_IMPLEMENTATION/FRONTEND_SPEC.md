# Frontend Specification — Views, UX Flows, and Components

## Design Principles

1. **Clarity first**: Every screen has one primary action. Users should never wonder what to do next.
2. **Evidence is the product**: The validation result is not just PASS/FAIL — it's a visual map of what was found where in the document. The PDF viewer is always present alongside results.
3. **Ambiguity is explicit**: AMBIGUOUS is a first-class state with a dedicated UI. It is not an error — it is a request for human judgment.
4. **Progressive disclosure**: Simple cases look simple (one field, one error). Complex cases (many fields, ambiguity, repeating groups) reveal their complexity only when needed.
5. **Modern, professional, usable**: The UI should feel like a compliance tool that a QA officer would actually want to use — not a developer debug panel.

---

## Tech Stack

- **Framework**: React 18 + TypeScript
- **Routing**: React Router v6
- **Styling**: CSS modules or Tailwind (TBD — current uses plain CSS)
- **PDF viewer**: Browser native `<iframe>` for M1; `react-pdf` (PDF.js) for M2+ (needed for bbox highlighting)
- **State**: Local component state (`useState`, `useReducer`); no global state manager needed for M1

---

## Routes

| Path | Component | Description |
|------|-----------|-------------|
| `/` | redirect → `/projects` | |
| `/projects` | `ProjectsPage` | List all projects |
| `/projects/:projectId` | `ProjectOverviewPage` | Project dashboard |
| `/projects/:projectId/validation` | `ProjectValidationPage` | Upload + validate + view results |
| `/projects/:projectId/schemas` | `ProjectSchemasPage` | Schema management (create, view versions) |
| `/projects/:projectId/runs` | `ProjectRunsPage` | Validation run history (M2) |
| `/projects/:projectId/runs/:runId` | `RunDetailPage` | Full run snapshot detail (M2) |

---

## View: `/projects`

**Purpose**: Entry point. Lists all projects. First action is "New project" or selecting an existing project.

**Layout**:
- Header: "Projects" + "New Project" button (top right)
- Grid of project cards, each showing:
  - Project name
  - Number of schemas
  - Last validation run date + status badge (PASS/FAIL/AMBIGUOUS)
  - "Open" button
- Empty state: "No projects yet. Create your first project to start validating documents."

---

## View: `/projects/:projectId`

**Purpose**: Project overview / dashboard.

**Layout**:
- Project name as page title
- 3 cards: "Schemas" (count), "Validation Runs" (count, M2), "Last Run" (status + timestamp)
- Quick actions: "Validate a document" button → navigates to `/projects/:projectId/validation`
- Recent runs table (M2): last 5 runs with status badge, schema key, timestamp

---

## View: `/projects/:projectId/validation` — PRIMARY VIEW

This is the core product experience. It must be designed with extreme care.

### Layout

Split into 3 panels:

```
┌──────────────────────────────────────────────────────────────────────┐
│  HEADER: "Document Validation"  │  Schema: [dropdown]  Ver: [dropdown]│
│                                                                      │
├────────────────┬─────────────────────────────────────────────────────┤
│                │                                                      │
│  LEFT PANEL    │            PDF VIEWER PANEL                         │
│  (Results)     │                                                      │
│                │  • Shows uploaded PDF                                │
│  • Upload zone │  • Highlights evidence bboxes (M2+)                  │
│  • Run button  │  • Click on highlight → focus result in left panel  │
│  • Status      │                                                      │
│  • Error list  │                                                      │
│  • Ambiguity   │                                                      │
│    panel       │                                                      │
│                │                                                      │
└────────────────┴─────────────────────────────────────────────────────┘
```

### Left Panel — Upload State (no file)

- Large drag-and-drop zone: "Drop a PDF here or click to browse"
- Schema selector (required before upload):
  - Dropdown: schema key
  - Dropdown: version (filtered to selected key, shows `(active)` / `(archived)` labels)
- "Run Validation" button (disabled until file + schema + version selected)

### Left Panel — Pending State (validating)

- PDF thumbnail shown
- Spinner + "Validating…" label
- Schema + version locked (not editable mid-run)

### Left Panel — PASS State

```
┌─────────────────────────────┐
│  ✓  PASS                    │
│  Schema: wine_lab_report    │
│  Version: v1.1              │
│                             │
│  All 3 fields passed.       │
│  No rule violations.        │
│                             │
│  [Validate another]         │
└─────────────────────────────┘
```

### Left Panel — FAIL State

```
┌─────────────────────────────┐
│  ✕  FAIL                    │
│  Schema: wine_lab_report    │
│  Version: v1.1              │
│                             │
│  2 rule violation(s)        │
│                             │
│  ┌─ alcohol ───────────────┐│
│  │ Value: 18.0             ││
│  │ Expected: 8.0 – 15.0    ││
│  │ Rule: range_validation  ││
│  │ Evidence: block b3, p.1 ││
│  │ [Show in PDF →]         ││
│  └─────────────────────────┘│
│                             │
│  ┌─ volatile_acidity ──────┐│
│  │ Value: missing          ││
│  │ Expected: present       ││
│  │ Rule: required          ││
│  │ (no location)           ││
│  └─────────────────────────┘│
└─────────────────────────────┘
```

**Error card interactions**:
- Click "Show in PDF →": jumps the PDF viewer to the relevant page and highlights the bounding box.
- Hovering an error card highlights the corresponding location in the PDF.
- Clicking a highlighted bbox in the PDF focuses the corresponding error card.

### Left Panel — AMBIGUOUS State

```
┌─────────────────────────────┐
│  ⚠  AMBIGUOUS               │
│  Schema: wine_lab_report    │
│  Version: v1.1              │
│                             │
│  1 field needs review       │
│                             │
│  ┌─ temperature ───────────┐│
│  │ We found 2 values:      ││
│  │                         ││
│  │ ● 18.5°C — block b7    ││
│  │   "Fermentation temp:   ││
│  │    18.5°C"  [Show →]   ││
│  │   Section: Fermentation ││
│  │                         ││
│  │ ● 22.0°C — block b19   ││
│  │   "Bottling temperature ││
│  │    22.0°C"  [Show →]   ││
│  │   Section: Bottling     ││
│  │                         ││
│  │ Please review the PDF   ││
│  │ and determine which     ││
│  │ value is correct for    ││
│  │ this field.             ││
│  └─────────────────────────┘│
└─────────────────────────────┘
```

---

## View: `/projects/:projectId/schemas` — Schema Management

**Purpose**: Browse schemas, view version history, create new versions.

### Layout

- List of schema keys (accordion or tabs)
- Each schema key expands to show version history table:
  - Version label | Status badge | Created at | Archived at | Actions
  - Actions: Archive (if active), View body
- "New Schema" button → opens schema creation flow

### Schema Creation Flow

**Step 1 — Describe** (LLM-assisted):
```
┌─────────────────────────────────────────────────────┐
│  Create a new schema                                │
│                                                     │
│  Schema key: [___________________]                  │
│  Version:    [___________________] (e.g. "v1.0")   │
│                                                     │
│  Describe what this document should contain:        │
│  ┌─────────────────────────────────────────────┐   │
│  │ The report must have a pH between 3.0 and   │   │
│  │ 4.5, alcohol content between 8% and 15%,   │   │
│  │ and a quality score from 0 to 10. All       │   │
│  │ three fields are required.                  │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  [Generate Schema →]                                │
└─────────────────────────────────────────────────────┘
```

**Step 2 — Review** (generated schema in editable form):
```
┌─────────────────────────────────────────────────────┐
│  Review generated schema                            │
│                                                     │
│  Summary: 3 required numeric fields                 │
│                                                     │
│  Fields:                                            │
│  ┌─ ph ──────────────────────────────────────────┐ │
│  │ Type: Number  Required: ✓                     │ │
│  │ Range: 3.0 – 4.5                              │ │
│  │ Aliases: (none)  [+ Add alias]                │ │
│  └───────────────────────────────────────────────┘ │
│  ┌─ alcohol ─────────────────────────────────────┐ │
│  │ Type: Number  Required: ✓                     │ │
│  │ Range: 8.0 – 15.0                             │ │
│  │ Aliases: Alcohol %, Alc.  [+ Add alias]       │ │
│  └───────────────────────────────────────────────┘ │
│  ┌─ quality ─────────────────────────────────────┐ │
│  │ Type: Number  Required: ✓                     │ │
│  │ Range: 0 – 10                                 │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  [+ Add field]   [Edit as JSON]                     │
│                                                     │
│  [← Back]     [Save and Activate →]                 │
└─────────────────────────────────────────────────────┘
```

Users can switch between form-based and raw JSON view. Both are kept in sync.

---

## View: `/projects/:projectId/runs` (Milestone 2)

**Purpose**: Browse validation run history.

**Layout**:
- Filter bar: schema key, status (PASS/FAIL/AMBIGUOUS), date range
- Table: Run ID (truncated) | Schema key | Version | Status badge | Timestamp | PDF hash (truncated) | "View" link
- Pagination

---

## View: `/projects/:projectId/runs/:runId` (Milestone 2)

**Purpose**: Inspect a complete validation run snapshot.

**Layout**: Same as the validation view, but read-only (showing the stored report + PDF hash).
- Shows all intermediate state counts (X blocks extracted, Y candidates found, Z fields resolved)
- Collapsible "Technical details" section with full intermediate state (for developers)

---

## PDF Viewer — Milestones

### Milestone 1 (current)
- `<iframe src="{pdf_url}#page={N}">` — native browser PDF viewer
- Jump to page where first error occurred
- No bbox highlighting

### Milestone 2+ (target)
- Replace iframe with PDF.js-based viewer (`react-pdf`)
- Render bbox highlight overlays as colored rectangles on the canvas
- Color coding: red for FAIL errors, orange for AMBIGUOUS candidates
- Clicking a highlight focuses the corresponding result card
- Multiple highlights per page (one per error/candidate on that page)

---

## Component Architecture

```
src/
├── pages/
│   ├── ProjectsPage.tsx
│   ├── ProjectOverviewPage.tsx
│   ├── ProjectValidationPage.tsx     ← primary view
│   ├── ProjectSchemasPage.tsx
│   ├── ProjectRunsPage.tsx           (M2)
│   └── RunDetailPage.tsx             (M2)
│
├── components/
│   ├── validation/
│   │   ├── UploadZone.tsx            drag-drop PDF upload
│   │   ├── SchemaSelector.tsx        key + version dropdowns
│   │   ├── ValidationStatusBadge.tsx PASS/FAIL/AMBIGUOUS badge
│   │   ├── ValidationErrorCard.tsx   single error with evidence
│   │   ├── AmbiguousFieldCard.tsx    field with multiple candidates
│   │   └── ValidationResultPanel.tsx aggregates error cards + status
│   │
│   ├── pdf/
│   │   ├── PdfViewer.tsx             iframe (M1) or PDF.js (M2+)
│   │   └── BboxHighlight.tsx         overlay for evidence bbox (M2+)
│   │
│   ├── schemas/
│   │   ├── SchemaKeyList.tsx
│   │   ├── SchemaVersionTable.tsx
│   │   ├── SchemaFieldForm.tsx       field editor (form-based)
│   │   └── SchemaJsonEditor.tsx      raw JSON editor
│   │
│   └── shared/
│       ├── StatusBadge.tsx
│       ├── EmptyState.tsx
│       └── LoadingSpinner.tsx
│
├── api.ts                            typed API client
└── layouts/
    └── AppLayout.tsx                 sidebar nav + content area
```

---

## API Client (`api.ts`)

All API calls go through a typed client module. No raw `fetch` calls in components.

```typescript
export const api = {
  projects: {
    list: () => get<Project[]>('/projects'),
    get: (id: string) => get<Project>(`/projects/${id}`),
    create: (name: string) => post<Project>('/projects', { name }),
  },
  validation: {
    listSchemas: (projectId: string) => get<ValidationSchemaGroupOut[]>(
      `/projects/${projectId}/validation-schemas`
    ),
    createSchema: (projectId: string, body: CreateSchemaRequest) => post(
      `/projects/${projectId}/validation-schemas`, body
    ),
    validateDocument: (
      projectId: string, schemaId: string, version: string, file: File
    ) => postForm<ValidateDocumentResponse>('/validate-document', {
      project_id: projectId, schema_id: schemaId, schema_version: version, document: file,
    }),
    generateSchema: (projectId: string, description: string) => post<GenerateSchemaResponse>(
      `/projects/${projectId}/schemas/generate`, { description }
    ),
  },
  runs: {  // M2
    list: (projectId: string, params?: RunListParams) => get<RunListResponse>(
      `/projects/${projectId}/validation-runs`, params
    ),
    get: (projectId: string, runId: string) => get<RunDetail>(
      `/projects/${projectId}/validation-runs/${runId}`
    ),
  },
};
```

---

## Cross-References

| Topic | Document |
|-------|----------|
| API contracts | `05_IMPLEMENTATION/API_SPEC.md` |
| AMBIGUOUS status | `01_ARCHITECTURE/PIPELINE_DESIGN.md` |
| Schema DSL | `03_DOMAIN/VALIDATION_SCHEMA.md` |
| Run history (M2) | `02_MILESTONES/MILESTONE_2_AUDITABILITY.md` |
