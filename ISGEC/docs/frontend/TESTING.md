# Frontend Testing

> **Source:** `ISGEC/frontend/lib/*.test.ts`, `vitest.config.ts`, `vitest.setup.ts`
> **Stack:** Vitest + jsdom + @testing-library/react

The frontend test suite is small but focused — it covers the libraries (`api`, `store`, `viewport`) that the workspace components depend on. Component-level testing is out of scope for v1.

---

## Setup

### `vitest.config.ts`

```typescript
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
  },
});
```

### `vitest.setup.ts`

```typescript
import '@testing-library/jest-dom';
// Additional setup (mocks, polyfills, etc.)
```

### `package.json` scripts

```json
{
  "test":        "vitest run",
  "test:watch":  "vitest",
  "type-check":  "tsc --noEmit"
}
---

## Test files

### `lib/api.test.ts` (5.6 KB)

Tests the typed FastAPI client.

**Coverage**:
- Request shape (URL, headers, body) for each endpoint
- Response parsing (camelCase JSON → snake_case types)
- Error handling (4xx/5xx → typed error)
- Mocked `fetch` (no real network calls)

Example test sketch:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { listProjects, getProject } from './api';

describe('api.listProjects', () => {
  it('returns ProjectSummary[]', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      json: async () => [{ id: '1', label: 'P1', ... }],
    } as Response);
    
    const projects = await listProjects();
    expect(projects).toHaveLength(1);
    expect(projects[0].id).toBe('1');
  });
});
```

### `lib/store.test.ts` (4.8 KB)

Tests the Zustand stores.

**Coverage**:
- Initial state
- State transitions (`signIn`, `signOut`, `loadProject`, etc.)
- Polling lifecycle (start/stop)

```typescript
import { describe, it, expect } from 'vitest';
import { useSessionStore } from './store';

describe('useSessionStore', () => {
  it('starts with user=null', () => {
    expect(useSessionStore.getState().user).toBeNull();
  });
  
  it('signIn sets user', () => {
    useSessionStore.getState().signIn('test@example.com');
    expect(useSessionStore.getState().user).toEqual({
      email: 'test@example.com',
    });
  });
});
```

### `lib/viewport.test.ts` (2.6 KB)

Tests the pure-function viewport utilities.

**Coverage**:
- `worldToScreen` / `screenToWorld` — round-trip identity
- `zoomAt` — zoom-in keeps the screen point fixed
- `pan` — translation accumulates correctly
- Edge cases (zoom = 0, negative scale, etc.)

```typescript
import { describe, it, expect } from 'vitest';
import { worldToScreen, screenToWorld, zoomAt, pan } from './viewport';

describe('viewport', () => {
  it('worldToScreen → screenToWorld is identity', () => {
    const vp = { center: { x: 0, y: 0 }, scale: 1, ... };
    const pt = { x: 100, y: 200 };
    const screen = worldToScreen(pt, vp);
    const back = screenToWorld(screen, vp);
    expect(back).toEqual(pt);
  });
  
  it('zoomAt keeps the screen point fixed', () => {
    const vp = { center: { x: 0, y: 0 }, scale: 1, ... };
    const screenPt = { x: 100, y: 200 };
    const newVp = zoomAt(vp, screenPt, 2);
    // The world point under screenPt should be unchanged
    expect(screenToWorld(screenPt, newVp)).toEqual(screenToWorld(screenPt, vp));
  });
});
```

---

## Running tests

```bash
cd ISGEC/frontend

# Run once
npm run test

# Watch mode
npm run test:watch

# Type check (separate from tests)
npm run type-check

# CI (no watch, no colors)
npm run test -- --reporter=verbose
```

Expected output:

```
 ✓ lib/api.test.ts (12 tests) 31ms
 ✓ lib/store.test.ts (8 tests) 18ms
 ✓ lib/viewport.test.ts (15 tests) 12ms

 Test Files  3 passed (3)
      Tests  35 passed (35)
   Duration  420ms
```

---

## What's NOT covered (yet)

- Component-level testing (renders, interactions)
- End-to-end testing (full user flows)
- Visual regression testing
- Accessibility testing (axe-core)

For v1, the focus is on **library correctness** — the components consume tested APIs.

Future work: Playwright E2E for the upload → workspace flow.

---

## Reference

- [`STRUCTURE.md`](./STRUCTURE.md) — overall frontend structure
- [`MARKETING.md`](./MARKETING.md) — 16 marketing sections
- [`WORKSPACE.md`](./WORKSPACE.md) — workspace components
- [`SETUP.md`](./SETUP.md) — local dev setup