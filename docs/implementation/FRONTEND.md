# Frontend

## Routes (`frontend/src/App.tsx`)

| Path | Page |
|------|------|
| `/projects` | Project list / create |
| `/projects/:projectId` | Overview |
| `/projects/:projectId/validation` | Schema selection, PDF upload, PASS/FAIL + evidence + PDF preview |
| `/logs` | Log viewer |
| `/projects/:projectId/validate/:docId` | Redirect → `/validation` (legacy bookmark) |

## API client (`frontend/src/api.ts`)

Relative **`/api`** (Traefik same-origin; Vite dev proxy). Optional gateway bearer **`VITE_EDGE_API_TOKEN`** and log viewer token.

## Styling

**`App.css`** — validation layout uses classes prefixed with **`validation-`**.
