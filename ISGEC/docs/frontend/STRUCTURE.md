# Frontend Structure

> **Source:** `ISGEC/frontend/`

The Next.js app structure: routes, components, libraries, configuration.

---

## Directory layout

```
ISGEC/frontend/
├── package.json                deps + scripts (Vitest, Next 14)
├── tsconfig.json               TypeScript config
├── next.config.mjs            Next.js config
├── tailwind.config.ts         Tailwind theme
├── postcss.config.mjs         PostCSS for Tailwind
├── vitest.config.ts           Vitest test runner
├── vitest.setup.ts            jsdom + testing-library setup
├── next-env.d.ts              Next.js TypeScript declarations
├── Dockerfile                 production build (multi-stage)
│
├── app/                       App Router pages
│   ├── layout.tsx             root layout (nav + footer)
│   ├── globals.css            shared CSS (138 KB; the prototype stylesheet)
│   ├── page.tsx               marketing landing (composes 16 sections)
│   ├── dashboard/
│   │   ├── page.tsx           projects grid
│   │   └── [id]/page.tsx      workspace for a specific project
│   └── upload/
│       └── page.tsx           opens the upload modal
│
├── components/                React components
│   ├── marketing/             16 landing-page sections
│   ├── workspace/             AppShell, DrawingCanvas, IssueInspector
│   ├── upload/                UploadModal
│   └── auth/                  SignInModal
│
├── lib/                       shared client-side libraries
│   ├── api.ts                 typed FastAPI client
│   ├── api.test.ts            tests for api.ts
│   ├── store.ts               Zustand store(s)
│   ├── store.test.ts          tests for store.ts
│   ├── viewport.ts            viewport / pan-zoom utilities
│   └── viewport.test.ts       tests for viewport.ts
│
├── styles/                    additional CSS files
├── public/                    static assets
│
└── tests/                     (E2E if any — currently empty)
```

---

## App routes

### `/` — Marketing landing

Composes 16 section components matching the brief in [`../reference/WEBSITE_CONTENT_BRIEF.md`](../reference/WEBSITE_CONTENT_BRIEF.md).

| Section | File | Brief § |
|---|---|---|
| Hero | `components/marketing/Hero.tsx` | §1 |
| Why Agentic | `components/marketing/WhyAgentic.tsx` | §6 |
| Pipeline | `components/marketing/Pipeline.tsx` | §3 |
| Capabilities | `components/marketing/Capabilities.tsx` | §4 |
| How It Works | `components/marketing/HowItWorks.tsx` | §5 |
| Defensibility | `components/marketing/Defensibility.tsx` | §7 |
| Supported Formats | `components/marketing/SupportedFormats.tsx` | §8 |
| Integrations | `components/marketing/Integrations.tsx` | §9 |
| Security | `components/marketing/Security.tsx` | §10 |
| Use Cases | `components/marketing/UseCases.tsx` | §11 |
| Standards | `components/marketing/Standards.tsx` | §12 |
| Testimonials | `components/marketing/Testimonials.tsx` | §14 |
| FAQ | `components/marketing/FAQ.tsx` | §15 |
| Final CTA | `components/marketing/FinalCTA.tsx` | §16 |
| Problem Cards | `components/marketing/ProblemCards.tsx` | §2 |
| LocalModel | `components/marketing/LocalModel.tsx` | (variant) |

Plus shared chrome: `Nav.tsx`, `Footer.tsx`, `RevealInit.tsx`.

See **[MARKETING.md](./MARKETING.md)** for details on each section.

### `/dashboard` — Projects grid

Lists all projects via `GET /api/projects`, with summary (pass/warn/fail counts) and a click-to-open action.

### `/dashboard/{id}` — Workspace

The drawing workspace. Renders:
- The drawing canvas (entities with click-to-zoom)
- The issue inspector panel (severity-filtered findings)
- Tabs: STR / MECH / OVERLAY (per the prototype spec)

See **[WORKSPACE.md](./WORKSPACE.md)** for details.

### `/upload` — Upload flow

Opens `UploadModal` (drag-drop 2 drawings, pick strategy, click Start).

---

## Components

### `components/marketing/`

16 section components — see **[MARKETING.md](./MARKETING.md)** for the full list and what each implements.

### `components/workspace/`

| File | Purpose |
|---|---|
| `AppShell.tsx` | Outer layout — nav rail, status bar, chat tab |
| `DrawingCanvas.tsx` | Renders entities (line/polyline/circle/etc.) with click-to-locate |
| `IssueInspector.tsx` | 4-tab findings panel (per the prototype): STR / MECH / OVERLAY / ACTIVITY |

### `components/upload/`

| File | Purpose |
|---|---|
| `UploadModal.tsx` | Drag-drop STR + MECH, label + rev form, submit → `POST /api/projects` |

### `components/auth/`

| File | Purpose |
|---|---|
| `SignInModal.tsx` | Demo-mode sign-in (any email + 4+ char password accepted) |

---

## Libraries

### `lib/api.ts` — Typed FastAPI client

```typescript
// Wraps fetch() with typed responses
export async function listProjects(): Promise<ProjectSummary[]> { ... }
export async function getProject(id: string): Promise<ProjectDetail> { ... }
export async function createProject(formData: FormData): Promise<ProjectOut> { ... }
export async function patchIssue(issueId: string, body: IssuePatch): Promise<...> { ... }
// etc.
```

Each project has:
- `lib/api.test.ts` (5.6 KB) — Vitest tests for the client

### `lib/store.ts` — Zustand stores

```typescript
// Per-store hooks
export const useSessionStore    = create<SessionState>(...)
export const useProjectsStore   = create<ProjectsState>(...)
export const useModalsStore     = create<ModalsState>(...)
```

Each store has:
- `lib/store.test.ts` (4.8 KB) — Vitest tests

### `lib/viewport.ts` — Pan/zoom utilities

```typescript
// Pure functions for converting between world coords (mm) and screen pixels
export function worldToScreen(point: Vec2, viewport: Viewport): Vec2 { ... }
export function screenToWorld(point: Vec2, viewport: Viewport): Vec2 { ... }
export function zoomAt(viewport: Viewport, screenPoint: Vec2, factor: number): Viewport { ... }
export function pan(viewport: Viewport, dx: number, dy: number): Viewport { ... }
```

Each has:
- `lib/viewport.test.ts` (2.6 KB) — Vitest tests

---

## Configuration

### `package.json` scripts

```json
{
  "dev":       "next dev",
  "build":     "next build",
  "start":     "next start",
  "lint":      "next lint",
  "test":      "vitest run",
  "test:watch":"vitest",
  "type-check":"tsc --noEmit"
}
```

### `tsconfig.json`

Strict TypeScript, paths alias `@/*` → `app/*` + `components/*` + `lib/*`.

### `vitest.config.ts`

```typescript
export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
  },
});
```

### `next.config.mjs`

Standard Next.js config with:
- React strict mode enabled
- Image domains whitelisted

### `tailwind.config.ts`

The Tailwind theme tokens match the design system in [`../reference/WEBSITE_CONTENT_BRIEF.md`](../reference/WEBSITE_CONTENT_BRIEF.md) §"Design System Tokens":

| Token | Value |
|---|---|
| `--bg-primary` | `#FAFAF7` (off-white) |
| `--bg-dark` | `#0F172A` (dark navy) |
| `--accent` | `#0EA5A4` (teal) |
| `--clash-hard` | `#DC2626` (red) |
| `--clash-soft` | `#F59E0B` (amber) |
| `--pass` | `#10B981` (green) |

> Note: Tailwind is installed but `globals.css` is set up so the **prototype stylesheet can be used verbatim** (per the conversion plan). Tailwind utilities are still available for new components.

---

## Reference

- **[MARKETING.md](./MARKETING.md)** — 16 marketing sections
- **[WORKSPACE.md](./WORKSPACE.md)** — workspace components
- **[TESTING.md](./TESTING.md)** — Vitest setup
- **[SETUP.md](./SETUP.md)** — local dev + Docker
- [`../reference/WEBSITE_CONTENT_BRIEF.md`](../reference/WEBSITE_CONTENT_BRIEF.md) — marketing brief the components implement