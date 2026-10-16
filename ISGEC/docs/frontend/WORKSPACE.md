# Workspace Components

> **Source:** `ISGEC/frontend/components/workspace/`, `components/upload/`, `components/auth/`

The drawing workspace — what users see after uploading a project. Three components form the outer shell, with the upload modal and sign-in modal as overlays.

---

## 1. Workspace layout

```
┌────────────────────────────────────────────────────────────────┐
│ AppShell                                                        │
│ ├─ [Nav rail (top)]                                             │
│ ├─ [Drawing tabs: STR | MECH | OVERLAY | ACTIVITY]              │
│ ├─ [Status bar (bottom)]                                        │
│ └─ [Chat panel (toggle, right)]                              │
│                                                                 │
│ ┌─────────────────────────┬───────────────────────────────────┐│
│ │                         │                                   ││
│ │   DrawingCanvas         │   IssueInspector                  ││
│ │   (left, large)         │   (right, scrollable)             ││
│ │                         │                                   ││
│ │   - Entities rendered   │   - Severity filter               ││
│ │   - Pan / zoom          │   - Finding cards                 ││
│ │   - Click-to-locate     │   - Click → zoom on canvas        ││
│ │                         │                                   ││
│ └─────────────────────────┴───────────────────────────────────┘│
└────────────────────────────────────────────────────────────────┘
```

---

## 2. Components

### `workspace/AppShell.tsx`

The outer layout shell. Manages:
- Top nav rail (project title + actions)
- Drawing tabs (STR / MECH / OVERLAY / ACTIVITY)
- Status bar (bottom; shows upload progress, analysis phase, etc.)
- Chat panel toggle (right side; future feature)

Renders inside `app/dashboard/[id]/page.tsx`.

### `workspace/DrawingCanvas.tsx`

Renders drawing entities with pan/zoom. Uses the viewport utilities in `lib/viewport.ts`.

**Features**:
- Renders LINE, LWPOLYLINE, CIRCLE, ARC, ELLIPSE, TEXT, INSERT, DIMENSION entities
- Pan: drag with mouse
- Zoom: scroll wheel
- Click-to-locate: clicking on an entity highlights it + emits an event the inspector uses to scroll to the finding
- Sheet selector (top-right corner; switches between sheets when multi-sheet projects are supported)
- Toggle overlays: STR on/off, MECH on/off, grid on/off

**Performance**: Uses `<canvas>` (not SVG) for performance — even TP-104 with 56k entities renders smoothly.

### `workspace/IssueInspector.tsx`

The findings panel on the right.

**4 tabs** (matching the prototype):
- **STR** — STR findings only (filterable by severity)
- **MECH** — MECH findings only
- **OVERLAY** — cross-discipline findings (clash, missing, orphan)
- **ACTIVITY** — recent events from `/api/projects/{id}/events`

**Finding card** shows:
- Severity badge (high/medium/low/pass)
- Title + category + code
- Evidence + formula
- Sheet + grid
- mech_ref / str_ref tags
- "Click to locate" button → zooms the canvas

---

## 3. Upload flow

### `upload/UploadModal.tsx`

Drag-drop STR + MECH drawings, fill in label + rev, submit.

**Behavior**:
1. Drag two `.dwg` / `.dxf` / `.ifc` / `.pdf` files onto the dropzone
2. Form fields: label (optional, defaults to timestamp), rev (optional)
3. Submit → `POST /api/projects` with multipart form data
4. On 201: redirect to `/dashboard/{id}` to view the new project
5. On error: show inline error (size limit, unsupported extension, etc.)

---

## 4. Auth (demo mode)

### `auth/SignInModal.tsx`

Demo-mode sign-in. **Any email + 4+ char password is accepted** (no backend validation). State stored in `useSessionStore` (Zustand).

> In production, swap for OAuth/SSO/SAML via the Auth provider.

---

## 5. State management

The workspace uses Zustand stores in `lib/store.ts`:

```typescript
// lib/store.ts (sketch)
export const useSessionStore = create<SessionState>((set) => ({
  user: null,
  signIn: (email) => set({ user: { email } }),
  signOut: () => set({ user: null }),
}));

export const useProjectStore = create<ProjectState>((set, get) => ({
  project: null,
  issues: [],
  entities: { str: [], mech: [] },
  analysis: { status: 'idle', ... },
  loadProject: async (id) => {
    const project = await getProject(id);
    set({ project, issues: project.issues, entities: project.entities });
  },
  // polling
  startPolling: (id) => { /* poll /analysis every 500ms */ },
  stopPolling: () => { ... },
}));
```

Stores are tested in `lib/store.test.ts`.

---

## 6. Click-to-locate flow

This is the hero interaction — clicking a finding in the inspector zooms the canvas to its location.

```typescript
// In IssueInspector:
<button onClick={() => {
  // 1. Send an event to the canvas store
  zoomToEntity(finding.entity_id, finding.zoom_box);
  
  // 2. Highlight the entity
  highlightEntity(finding.entity_id, { duration: 5000 });
  
  // 3. Switch to the OVERLAY tab if not there
  setActiveTab('overlay');
}}>
  Click to locate
</button>
```

The canvas listens for these events and animates the zoom.

---

## 7. Polling for analysis status

While analysis runs, the workspace polls `/api/projects/{id}/analysis` every 500ms:

```typescript
// In dashboard/[id]/page.tsx
useEffect(() => {
  const interval = setInterval(async () => {
    const state = await getAnalysis(projectId);
    setAnalysisState(state);
    if (state.status === 'done') clearInterval(interval);
  }, 500);
  return () => clearInterval(interval);
}, [projectId]);
```

Updates flow:
- `status: running` → show spinner
- `status: done` → stop polling, render findings
- `status: error` → show error message

---

## 8. Reference

- [`STRUCTURE.md`](./STRUCTURE.md) — overall frontend structure
- [`MARKETING.md`](./MARKETING.md) — the 16 marketing sections
- [`TESTING.md`](./TESTING.md) — Vitest unit tests
- [`../backend/API.md`](../backend/API.md) — the FastAPI endpoints the frontend calls
- [`../backend/DATA_MODEL.md`](../backend/DATA_MODEL.md) — JSON contracts the frontend consumes