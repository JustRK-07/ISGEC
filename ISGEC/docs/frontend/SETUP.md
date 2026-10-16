# Frontend Setup

> **Audience:** Engineers setting up the ISGEC Next.js frontend for the first time.
> **Time to first run:** ~3 minutes.

---

## 0. Prerequisites

| Tool | Version | Required |
|---|---|---|
| Node.js | ≥ 18.0 | yes |
| npm | ≥ 9 | yes |
| Docker | latest | optional (for container dev) |

The frontend uses **Next.js 14** (App Router). Tailwind CSS is configured but disabled in `app/globals.css` to match the prototype stylesheet.

---

## 1. Local development setup

### 1.1. Install dependencies

```bash
cd ISGEC/frontend
npm ci        # exact install from package-lock.json
# or
npm install   # if you've changed deps
```

### 1.2. Configure environment

```bash
# Create .env.local (gitignored)
cat > .env.local <<EOF
NEXT_PUBLIC_API_BASE=http://localhost:8001
EOF
```

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8001` | FastAPI backend URL |

### 1.3. Run the dev server

```bash
npm run dev -- --hostname 0.0.0.0 --port 3001
```

Expected output:

```
  ▲ Next.js 14.x.x
  - Local:        http://localhost:3001
  - Network:      http://192.168.x.x:3001

 ✓ Starting...
 ✓ Ready in 1.2s
```

Open **<http://localhost:3001>**.

### 1.4. Hot reload

Next.js App Router supports fast refresh — edit any component or page and see changes immediately.

---

## 2. Build for production

```bash
npm run build
npm run start
```

`next build` produces an optimized `.next/` bundle; `next start` serves it on the configured port.

### Build output

```
Route (app)                                Size     First Load JS
┌ ○ /                                      8.5 kB         120 kB
├ ○ /_not-found                            871 B          871 B
├ ƒ /api/...                               0 B                0 B
├ ƒ /dashboard                             2.1 kB          95 kB
├ ƒ /dashboard/[id]                        4.5 kB          110 kB
└ ƒ /upload                                1.8 kB          90 kB
```

---

## 3. Tests

### Unit tests (Vitest)

```bash
npm run test        # run once
npm run test:watch  # watch mode
```

Coverage:
- `lib/api.test.ts` — typed FastAPI client
- `lib/store.test.ts` — Zustand stores
- `lib/viewport.test.ts` — viewport utilities

See **[TESTING.md](./TESTING.md)** for details.

### Type check

```bash
npm run type-check
```

Runs `tsc --noEmit` against the strict TypeScript config. Surfaces type errors without producing JS.

### Lint

```bash
npm run lint
```

Runs Next.js ESLint config.

---

## 4. Docker

### Build image

```bash
cd ISGEC/
docker build -f frontend/Dockerfile -t isgec-frontend .
```

### Run with docker-compose

```bash
cd ISGEC/
docker compose up
```

This starts both the backend (port 8001) and frontend (port 3001) together.

### The Dockerfile (multi-stage)

```dockerfile
# Stage 1: deps
FROM node:18-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# Stage 2: builder
FROM node:18-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# Stage 3: runner
FROM node:18-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
EXPOSE 3001
CMD ["npm", "start"]
```

---

## 5. Project layout (relevant subset)

```
ISGEC/frontend/
├── package.json
├── tsconfig.json
├── next.config.mjs
├── tailwind.config.ts
├── vitest.config.ts
├── vitest.setup.ts
├── Dockerfile
├── .dockerignore
├── .next/                    (gitignored; build output)
├── node_modules/             (gitignored)
├── app/
├── components/
├── lib/
└── public/
```

See **[STRUCTURE.md](./STRUCTURE.md)** for the full directory tree.

---

## 6. Common issues

### "Port 3001 already in use"

Another process is bound to 3001. Either stop it, or use a different port:

```bash
npm run dev -- --port 3002
```

### "Failed to fetch from /api/projects"

The FastAPI backend isn't running or `NEXT_PUBLIC_API_BASE` is wrong.

```bash
# Check the backend
curl http://localhost:8001/api/health

# Check the env var
echo $NEXT_PUBLIC_API_BASE
```

### Tailwind utilities not applying

Tailwind is configured but `globals.css` uses the prototype stylesheet. To use Tailwind utilities, ensure your component imports from a CSS file that includes the Tailwind directives:

```css
/* In a component CSS file: */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

Or just use the prototype classes (e.g. `class="container"`, `class="section-heading"`).

### Hydration mismatch warnings

Usually means `useEffect`-only state leaks into the initial render. Check that any `window`/`document` access is gated by SSR checks.

### Tests fail with "Cannot find module"

```bash
rm -rf node_modules .next
npm ci
```

---

## 7. Reference

- [`STRUCTURE.md`](./STRUCTURE.md) — overall structure
- [`MARKETING.md`](./MARKETING.md) — 16 marketing sections
- [`WORKSPACE.md`](./WORKSPACE.md) — workspace components
- [`TESTING.md`](./TESTING.md) — Vitest unit tests
- [`../backend/API.md`](../backend/API.md) — the FastAPI endpoints this frontend calls