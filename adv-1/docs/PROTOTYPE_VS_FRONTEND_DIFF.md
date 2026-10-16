# Prototype vs Frontend — UI Parity Diff

Captured at `1440×900` viewport on `2026-07-22`. Screenshots in `/tmp/adv-compare/`.

## TL;DR

The marketing landing page (`/`) is a **near pixel-perfect** port of the
prototype. All 17 sections render identically. The remaining issues are
concentrated in the **workspace** view (Tailwind-disabled components) and a
few small correctness/UX items.

## ✅ Sections that match

| # | Section | Prototype lines | Frontend file | Match |
|---|---|---|---|---|
| 01 | Hero (with viewer SVG + findings rail) | 6029–6158 | `components/marketing/Hero.tsx` | ✅ identical (SVG transcribed to JSX) |
| 02 | Local Model (4 cards + diagram + 4 pillars + 4 stats) | 6163–6287 | `LocalModel.tsx` | ✅ identical |
| 03 | Problem Cards (4) | 6287–6351 | `ProblemCards.tsx` | ✅ identical |
| 04 | Pipeline (L0 + L1–L5) | 6351–6401 | `Pipeline.tsx` | ✅ identical |
| 05 | Capabilities (5 capabilities) | 6406–6646 | `Capabilities.tsx` | ✅ identical (incl. inline SVG geometry) |
| 06 | How It Works (4 steps) | 6646–6681 | `HowItWorks.tsx` | ✅ identical |
| 07 | Why Agentic (11-row table) | 6681–6762 | `WhyAgentic.tsx` | ✅ identical |
| 08 | Defensibility (3 cells) | 6762–6792 | `Defensibility.tsx` | ✅ identical |
| 09 | Supported Formats | 6792–6857 | `SupportedFormats.tsx` | ✅ identical |
| 10 | Integrations (10) | 6857–6882 | `Integrations.tsx` | ✅ identical |
| 11 | Security (4 cards + audit block) | 6882–6927 | `Security.tsx` | ✅ identical |
| 12 | Use Cases (3) | 6927–6975 | `UseCases.tsx` | ✅ identical |
| 13 | Standards (4 code cols) | 6975–7035 | `Standards.tsx` | ✅ identical |
| 15 | Testimonials (3) | 7035–7074 | `Testimonials.tsx` | ✅ identical |
| 16 | FAQ (10 items) | 7074–7129 | `FAQ.tsx` | ✅ identical |
| 17 | Final CTA | 7129–7142 | `FinalCTA.tsx` | ✅ identical |
| — | Footer | 7142–7181 | `Footer.tsx` | ✅ identical |
| — | Sticky Nav | 6004–6024 | `Nav.tsx` | ✅ identical (conditional Projects link) |
| — | Reveal-on-scroll | (JS hook) | `RevealInit.tsx` | ✅ identical |

CSS is **byte-identical** to prototype (4,901 lines in `app/globals.css`,
served at `/_next/static/css/app/layout.css`). The big middle whitespace
visible in the full-page screenshots is the prototype's own design — the
sections themselves render with full content.

## ⚠️ Issues that remain

### A. Workspace uses disabled Tailwind classes (BREAKING visual)

Tailwind directives are commented out in `app/globals.css` lines 1–6, but
two workspace files still use Tailwind utilities. These will render as
unstyled DOM in the live app:

**`components/workspace/DrawingCanvas.tsx`** lines 102–126
- Uses `w-full`, `h-full`, `absolute`, `top-4 right-4 z-10 flex gap-2`,
  `bg-bg-dark`, `text-white`, `border border-border`, `rounded px-2 py-1 text-sm`.
- Effect: the sheet `<select>` and `+`/`−` zoom buttons floating over the
  canvas will be unstyled — no background, no border, no positioning.

**`components/workspace/IssueInspector.tsx`** lines 35–129
- Uses `p-4`, `text-h3`, `font-semibold`, `mb-3`, `gap-2`, `mb-4`, `text-sm`,
  `font-mono`, `space-y-2`, `border-l-4`, `border-l-clash-hard`,
  `bg-clash-hard/5`, `border-l-clash-soft`, `bg-clash-soft/5`,
  `border-l-text-muted`, `bg-text-muted/5`, `border-l-pass`, `bg-pass/5`,
  `ring-2 ring-accent`, `rounded-r cursor-pointer`, `text-xs uppercase`,
  `text-text-muted`, `text-pass`, `text-text-primary`, `bg-bg-primary`,
  `rounded`, `hover:underline`, `border-accent bg-accent/10`, `border-border`.
- Effect: the right-rail findings panel is essentially unstyled — no
  borders, no severity color stripes, no card layout.

**Fix options:**
1. Re-enable Tailwind directives in `globals.css` (uncomment `@tailwind`
   on lines 1–6) and ensure `tailwind.config.ts` token names map to the
   `globals.css` design tokens (`bg-dark` → `--ink`, `text-muted` →
   `--ink-mute`, `clash-hard` → `--rust`, `clash-soft` → `--amber`,
   `pass` → `--pass`, `accent` → `--cyan-deep`).
2. Replace Tailwind classes in those two files with CSS classes already
   defined in `globals.css` (e.g. `.rail-mode`, `.rail-btn`, `.issue-row`,
   `.issue-card`).

### B. Dead code

- `lib/store.ts` — `useView` slice (`view`, `setView`) is exported but
  never imported anywhere.
- `components/workspace/WorkspaceLayout.tsx` — unused; the dynamic page
  imports `AppShell` directly.
- `lib/api.ts` — `fetcher()` returns `api.listProjects()` typed as `T`,
  which is wrong; the comment says "Keep legacy fetcher export so existing
  imports don't break" but nothing imports it.

### C. AppShell auth-gate UX is jarring

`components/workspace/AppShell.tsx` lines 32–48:
```ts
useEffect(() => {
  if (!user) {
    openSignIn();        // pops the modal
    router.push("/");    // bounces to landing
  }
}, [user]);

if (!user) return null;   // page renders nothing while bouncing
```

Visiting `/dashboard` while signed out: flash of empty page → land on `/`
with sign-in modal. After signing in, the user lands on `/`, not back on
`/dashboard` (no destination-remember). The modal is also mounted
globally in `app/layout.tsx`, so it appears on every page including the
landing.

### D. Sign-in CTA navigation is incomplete

`components/auth/SignInModal.tsx` only redirects to `/dashboard` when the
pathname is `/` or `/upload`. Visiting `/dashboard/foo` while signed out
bounces to `/` → signs in → lands on `/` instead of returning to
`/dashboard/foo`.

### E. FinalCTA placeholder links

`components/marketing/FinalCTA.tsx` line 13–15: the
"Book a 20-min Demo" and "View a Sample Report" links go to `href="#"`
(prototype does the same — placeholder for now).

### F. Workspace toolbar buttons are decorative

`app/dashboard/[id]/page.tsx` renders Prev/Next sheet, Fit, 100%, Layers,
Undo, Redo, REV-A⇄REV-C, SUPERIMPOSE, plus the entire left/right rail
of tool buttons — none are wired to real behavior beyond sheet switching.
This matches the prototype (also decorative in the static HTML) so not a
conversion regression, but a known TODO.

## What this report does NOT cover

- Real auth (the demo-mode Zustand session)
- LLM analysis (backend LLM not configured — `llm.ready=false` in `/api/health`)
- The actual DWG → DXF ingestion path (backend responsibility)

## Recommended fix order

1. **(A)** Replace Tailwind classes in `DrawingCanvas.tsx` +
   `IssueInspector.tsx` with `globals.css` equivalents — restores
   workspace visual parity.
2. **(B)** Delete dead code (`useView`, `WorkspaceLayout`, `fetcher`).
3. **(C/D)** Fix auth-gate: stash intended destination, redirect after
   sign-in, and stop popping the modal on `/`.
4. **(F)** Wire up at least the active-sheet switching in the workspace
   viewer toolbar (other buttons can stay decorative).
