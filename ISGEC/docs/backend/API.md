# REST API — ISGEC Backend

> **Base URL:** `http://localhost:8001` (configurable via `BACKEND_PORT`)
> **API prefix:** `/api`
> **Auto-generated docs:** `http://localhost:8001/docs` (FastAPI built-in)
> **OpenAPI schema:** `http://localhost:8001/openapi.json`

Every endpoint, with request/response shapes and status codes. All endpoints return JSON unless noted.

---

## 0. Authentication

**There is no auth in v1.** This is a single-tenant internal tool — assume deployment behind a reverse proxy that handles authentication at the network layer. The data model does not track users; `uploaded_by` is optional and free-form.

---

## 1. Health & introspection

### `GET /api/health`

Health check; confirms LLM provider is loaded.

**Response 200**:
```json
{
  "ok": true,
  "version": "0.1.0",
  "llm": {
    "provider": "gemini" | "ollama",
    "ready":    true | false
  },
  "uptimeSec":     3600,
  "dbFile":        "data/isgec.db",
  "projectCount":  13
}
```

---

## 2. Projects

### `GET /api/projects`

List all projects, newest-first by `lastOpened`.

**Response 200**: array of [ProjectSummary](#projectsummary)
```json
[
  {
    "id":         "uuid",
    "label":      "TP-104 Conveyor",
    "shortName":  "TP-104",
    "rev":        "C",
    "kind":       "Str + Mech",
    "status":     "ready",
    "createdAt":  1721073600000,
    "lastOpened": 1721073610000,
    "summary":    { "pass": 5, "warn": 2, "fail": 3 }
  }
]
```

---

### `POST /api/projects`

Create a new project from STR + MECH (+ optional extra) drawing uploads.

**Request**: `multipart/form-data`
| Field | Type | Required | Notes |
|---|---|---|---|
| `str` | file | yes | Structural GA (.dwg/.dxf/.ifc/.pdf) |
| `mech` | file | yes | Mechanical GA |
| `extra` | file | no | Optional 3rd drawing |
| `label` | string | no | Default: `"Untitled · {ISO timestamp}"` |
| `rev` | string | no | Revision letter (e.g. `"A"`, `"B"`, `"C"`) |

**Validation**:
- File extension must be in `{dwg, dxf, ifc, pdf}`
- File size ≤ `MAX_UPLOAD_MB` (default 100 MB)
- Returns `415 Unsupported Media Type` if extension rejected
- Returns `413 Payload Too Large` if file too big

**Response 201**:
```json
{
  "id":         "uuid",
  "label":      "TP-104 Conveyor",
  "shortName":  "TP-104 Conveyor",
  "rev":        "C",
  "status":     "processing",
  "createdAt":  1721073600000,
  "lastOpened": 1721073600000,
  "files": {
    "str":   { "id": "...", "filename": "...", "format": "dwg", "sizeBytes": 3131396, "sha256": "..." },
    "mech":  { "id": "...", "filename": "...", "format": "dwg", "sizeBytes": 2876543, "sha256": "..." },
    "extra": null
  }
}
```

**Side effects**:
- Project row inserted (status=`"processing"`)
- 3 events emitted: `upload.started`, `upload.str`, `upload.mech` (and `upload.extra` if applicable), `upload.complete`
- Background task spawned: `_background_run_analysis(project_id)` — runs phase 1 (sync) + schedules phase 2 (async)

---

### `GET /api/projects/{project_id}`

Full project detail with everything the workspace needs.

**Response 200**: [ProjectDetail](#projectdetail)
```json
{
  "id":         "uuid",
  "label":      "TP-104 Conveyor",
  "shortName":  "TP-104",
  "rev":        "C",
  "kind":       "Str + Mech",
  "status":     "ready",
  "createdAt":  1721073600000,
  "lastOpened": 1721073610000,
  "files":   [FileOut, ...],
  "issues":  [IssueOut, ...],
  "entities": {
    "str":  [Entity, ...],
    "mech": [Entity, ...]
  },
  "sheets":  ["0001", "M-01"],
  "analysis": {
    "status":     "done",
    "phase":      "rules" | "rules+llm" | null,
    "llmStatus":  "pending" | "running" | "done" | "failed" | "skipped" | null,
    "llmError":   null | "LLM timed out after 20s",
    "summary":    { "pass": 5, "warn": 2, "fail": 3 } | null,
    "issueCount": 10 | null,
    "error":      null,
    "startedAt":   1721073600000 | null,
    "finishedAt": 1721073610000 | null
  },
  "checks": [
    { "id": "fuzzy", "name": "Fuzzy ID match",       "meta": "Levenshtein + ...", "state": "ok",   "count": 0 },
    { "id": "pos",   "name": "Position tolerance",    "meta": "Euclidean · ±25 mm", "state": "fail", "count": 3 },
    ...
  ],
  "events": [ProjectEvent, ...],
  "summary": { "pass": 5, "warn": 2, "fail": 3 }
}
```

**Response 404**: `{"detail": "Project not found"}`

---

### `DELETE /api/projects/{project_id}`

Delete a project + cascade.

**Response 200**:
```json
{ "ok": true }
```

**Side effects**:
- All `files`, `issues`, `entities`, `revisions` cascade-deleted (via FK ON DELETE CASCADE)
- `project_events` rows **not** removed (audit trail)
- `shutil.rmtree(uploads/<project_id>/)` removes on-disk files

---

## 3. Analysis

### `POST /api/projects/{project_id}/analyze`

Re-trigger analysis on an existing project. Useful for retrying after fixing parse errors or after an LLM upgrade.

**Response 200 (success)**:
```json
{ "ok": true, "status": "running" }
```

**Response 200 (skipped — no LLM)**:
```json
{ "ok": false, "status": "skipped", "reason": "LLM_PROVIDER=gemini not configured" }
```

**Response 404**: `{"detail": "Project not found"}`

**Side effects**:
- Background task spawned: `_background_analyze(project_id)`
- Phase 1 re-parses and re-runs rules
- Phase 2 (if LLM configured) re-runs the LLM enrichment
- Issues are reconciled by fingerprint (user state preserved)

---

### `GET /api/projects/{project_id}/analysis`

Poll the current state of the (re-)analysis. The frontend polls this every ~500ms during a run.

**Response 200**: [AnalysisState](#analysisstate)
```json
{
  "status":     "idle" | "running" | "done" | "error",
  "phase":      "rules" | "llm" | null,
  "llmStatus":  "pending" | "running" | "done" | "failed" | "skipped" | null,
  "llmError":   null | "LLM timed out after 20s",
  "summary":    { "pass": 5, "warn": 2, "fail": 3 } | null,
  "issueCount": 10 | null,
  "error":      null | "File parse failed",
  "startedAt":  1721073600000 | null,
  "finishedAt": 1721073610000 | null
}
```

**Response 404**: `{"detail": "Project not found"}`

---

## 4. Issues

### `PATCH /api/issues/{issue_id}`

Update an issue's state (resolve/dismiss/re-open) or assignment.

**Request body**:
```json
{
  "state":    "open" | "resolved" | "dismissed" | null,
  "assigned": "engineer@firm.com" | null
}
```

Both fields are optional. Pass only what you want to change.

**Response 200**:
```json
{
  "ok":       true,
  "id":       "uuid",
  "state":    "resolved",
  "assigned": "engineer@firm.com"
}
```

**Response 400**:
```json
{ "detail": "state must be one of open, resolved, dismissed" }
```

**Response 404**: `{"detail": "Issue not found"}`

**Side effects**:
- If `state` changed: emits `issue.{new_state}` event with `previousState` in payload
- Tone: `"ok"` if resolved, `"info"` if reopened/dismissed

---

## 5. Revisions (Layer 0)

### `POST /api/projects/{project_id}/revisions`

Upload a new revision of a project file. Same bytes → 409 Conflict with the existing `revision_id`.

**Request**: `multipart/form-data`
| Field | Type | Required | Notes |
|---|---|---|---|
| `file` | file | yes | The new revision DWG/DXF |
| `uploaded_by` | string | no | Optional user identifier |

**Response 201**:
```json
{
  "id":              "uuid",
  "family_id":       "tp-104 str ga",
  "revision_letter": "B",
  "supersedes":      "<prev-revision-uuid>" | null,
  "sha256":          "9f86d0...",
  "filename":        "TP-104 STR GA rev B.dwg",
  "size_bytes":      3145728,
  "uploaded_by":     "engineer@firm.com" | null,
  "uploaded_at":     1721073610000
}
```

**Response 409** (duplicate SHA-256):
```json
{
  "detail": {
    "error":       "File already ingested",
    "code":        "DUPLICATE_REVISION",
    "revision_id": "<existing-revision-uuid>"
  }
}
```

**Response 404**: `{"detail": "Project not found"}`

**Side effects**:
- File persisted to `uploads/<project_id>/rev.<ext>`
- File row inserted (discipline="extra", parse_status="pending")
- Revision row inserted; `revision_letter` incremented per family
- Event emitted: `revision.registered` (or `revision.duplicate` on dedupe)

---

### `GET /api/projects/{project_id}/revisions`

List all revisions for a project.

**Response 200**: array of revisions
```json
[
  {
    "id":              "uuid",
    "family_id":       "tp-104 str ga",
    "revision_letter": "A",
    "supersedes":      null,
    "sha256":          "9f86d0...",
    "filename":        "TP-104 STR GA.dwg",
    "size_bytes":      3131396,
    "uploaded_at":     1721073600000
  },
  ...
]
```

**Response 404**: `{"detail": "Project not found"}`

---

## 6. Events

### `GET /api/projects/{project_id}/events`

Bounded event log for a project (newest-first).

**Query parameters**:
| Name | Type | Default | Notes |
|---|---|---|---|
| `limit` | int | 200 | Hard-capped at 500 |

**Response 200**: array of [ProjectEvent](#projectevent)
```json
[
  {
    "id":        "uuid",
    "projectId": "uuid",
    "category":  "analyze",
    "code":      "rules.completed",
    "tone":      "ok",
    "message":   "Rule engine completed across 2242 elements.",
    "payload":   { "entityCount": 2242 },
    "createdAt": 1721073600000
  },
  ...
]
```

**Response 404**: `{"detail": "Project not found"}`

---

## 7. Files

### `GET /uploads/{project_id}/{filename}`

Raw file bytes for download/view.

**Response 200**: `application/octet-stream` (or detected MIME)

**Response 404**: `{"detail": "Not found"}`

Use cases:
- Workspace viewer wants to display the original DXF/DWG
- Click-to-locate highlighting requires the raw geometry
- Audit export bundles the source files

---

## Schema references

### `ProjectSummary`

```typescript
{
  id:         string
  label:      string
  shortName:  string
  rev:        string | null
  kind:       "Str + Mech" | string
  status:     "processing" | "ready" | "error"
  createdAt:  number  // epoch ms
  lastOpened: number  // epoch ms
  summary:    { pass: number, warn: number, fail: number }
}
```

### `ProjectDetail`

`ProjectSummary` + arrays:

```typescript
{
  ...ProjectSummary,
  files:    FileOut[]
  issues:   IssueOut[]
  entities: { str: Entity[]; mech: Entity[] }
  sheets:   string[]
  analysis: AnalysisState
  checks:   CheckResult[]     // see aggregate_checks()
  events:   ProjectEvent[]
}
```

### `FileSummary`

```typescript
{
  id:        string
  filename:  string
  format:    "dwg" | "dxf" | "ifc" | "pdf"
  sizeBytes: number
  sha256:    string
}
```

### `FileOut`

```typescript
{
  id:           string
  discipline:   "str" | "mech" | "extra"
  filename:     string
  format:       string
  sizeBytes:    number
  sha256:       string
  parseStatus:  "pending" | "ok" | "partial" | "failed" | "skipped"
  parseMeta:    object | null
}
```

### `IssueOut`

```typescript
{
  id:         string
  severity:   "high" | "medium" | "low" | "pass"
  category:   string
  code:       string              // e.g. "HARD-CLASH", "POS-DELTA"
  title:      string
  evidence:   string | null
  sheet:      string | null
  grid:       string | null
  mech_ref:   string | null
  str_ref:    string | null
  formula:    string | null
  result:     object | null       // JSON
  state:      "open" | "resolved" | "dismissed" | "obsolete"
  assigned:   string | null
  created_at: number              // epoch ms
}
```

### `Entity`

```typescript
{
  id:         string
  discipline: "str" | "mech"
  sheet:      string
  kind:       "opening" | "duct" | "pipe" | "beam" | "column" | "equipment" | string
  label:      string | null
  x_mm:       number | null
  y_mm:       number | null
  w_mm:       number | null
  h_mm:       number | null
  rotation:   number | null
  meta:       object | null       // JSON
}
```

### `AnalysisState`

```typescript
{
  status:      "idle" | "running" | "done" | "error"
  phase:       "rules" | "llm" | string | null
  llmStatus:   string | null       // 'pending' | 'running' | 'done' | 'failed' | 'skipped'
  llmError:    string | null
  summary:     { pass: number; warn: number; fail: number } | null
  issueCount:  number | null
  error:       string | null
  startedAt:   number | null       // epoch ms
  finishedAt:  number | null       // epoch ms
}
```

### `ProjectEvent`

```typescript
{
  id:        string
  projectId: string
  category:  "upload" | "parse" | "analyze" | "llm" | "issue" | "revision" | "system"
  code:      string                  // e.g. "upload.complete", "rules.completed", "llm.timed_out"
  tone:      "info" | "ok" | "warn" | "fail"
  message:   string
  payload:   object | null           // JSON
  createdAt: number                  // epoch ms
}
```

### `CheckResult` (from `aggregate_checks`)

```typescript
{
  id:    "fuzzy" | "pos" | "size" | "poly" | "clear" | "elev" | "req" | "orph"
  name:  string
  meta:   string
  state:  "ok" | "warn" | "fail"
  count:  number
}
```

---

## Status code summary

| Code | When |
|---|---|
| 200 | Successful read or non-create write |
| 201 | Resource created (POST upload/revision) |
| 400 | Bad request body (e.g. invalid `state`) |
| 404 | Resource not found (project/issue/file/revision) |
| 409 | Duplicate revision (SHA-256 already in ledger) |
| 413 | File too large |
| 415 | Unsupported file extension |
| 422 | Pydantic validation error (handled by FastAPI) |
| 500 | Internal server error (logged) |

---

*For data-model specifics: [`DATA_MODEL.md`](./DATA_MODEL.md). For architecture: [`ARCHITECTURE.md`](./ARCHITECTURE.md).*