# Marketing Components

> **Source:** `ISGEC/frontend/components/marketing/`
> **Spec:** [`../reference/WEBSITE_CONTENT_BRIEF.md`](../reference/WEBSITE_CONTENT_BRIEF.md)

16 section components that compose the marketing landing page (`/`). Each implements one section of the marketing brief. The order matches the page flow at the bottom of the brief.

---

## 1. Component index

| File | Brief § | Purpose |
|---|---|---|
| `Nav.tsx` | (chrome) | Sticky top navigation |
| `Hero.tsx` | §1 | H1 + sub + dual CTA + animation |
| `ProblemCards.tsx` | §2 | 4 pain-point cards (Missed Supports, Wrong Openings, Clashes, Tolerance Drift) |
| `Pipeline.tsx` | §3 | 5-layer architecture diagram |
| `Capabilities.tsx` | §4 | 5 core capabilities (Semantic Normalization, Openings, Smart ID, Clash, Click-to-locate) |
| `HowItWorks.tsx` | §5 | 4-step rail (Upload → Detect → Match & Check → Sign Off) |
| `WhyAgentic.tsx` | §6 | Comparison table (Agentic AI vs Trained ML) |
| `Defensibility.tsx` | §7 | "Every finding traces to sheet + grid + formula" callout |
| `SupportedFormats.tsx` | §8 | Format icon grid (DWG, DXF, IFC, RVT, PDF) |
| `Integrations.tsx` | §9 | Logo grid (Procore, ACC, Bluebeam, SharePoint, Revit, Outlook, Power BI) |
| `Security.tsx` | §10 | 3 security cards + audit ledger + zero-API callout |
| `UseCases.tsx` | §11 | 3 use cases (Mech↔Str, Revision Compare, Multi-discipline) |
| `Standards.tsx` | §12 | Code library (ACI 318, AISC 360, IS 800, Eurocode 3, ASCE 7, etc.) |
| `Testimonials.tsx` | §14 | QA-stamp testimonial cards |
| `FAQ.tsx` | §15 | 8-question FAQ |
| `FinalCTA.tsx` | §16 | Full-width dark CTA section |
| `LocalModel.tsx` | (variant) | Self-hosted LLM deep-dive (Qwen, Llama, DeepSeek, etc.) |
| `RevealInit.tsx` | (chrome) | Reveal-on-scroll initializer |
| `Footer.tsx` | (chrome) | Footer with product/resources/company/legal columns |

> **Note**: `Pricing.tsx` was **deleted** — the product is positioned as a custom-quote enterprise sale, not tiered pricing. (See git history.)

---

## 2. Page flow (top-to-bottom)

The page composes these in order:

```
[ Announcement bar — placeholder for press mention ]
[ Nav (sticky) ]
[ 1. Hero ]
[ 2. Problem Cards (4-col) ]
[ 3. Pipeline (5-stage diagram) ]
[ 4. Capabilities (5 alternating L/R blocks) ]
[ 5. How It Works (4-step rail) ]
[ 6. Why Agentic (comparison table) ]
[ 7. Defensibility (centered callout) ]
[ 8. Supported Formats (icon grid) ]
[ 9. Integrations (logo grid) ]
[ 10. Security (3 cards + audit ledger) ]
[ 11. Use Cases (3 detailed) ]
[ 12. Standards (code library) ]
[ 13. Testimonials (QA-stamp cards) ]
[ 14. FAQ (accordion) ]
[ 15. Final CTA (full-width dark) ]
[ Footer ]
```

The page entry point is `app/page.tsx`, which imports each component and composes them in this order.

---

## 3. Shared chrome

### `Nav.tsx`

- Sticky top navigation
- Links: `#pipeline`, `#capabilities`, `#security`, `#faq`, `Book a Demo`, `Upload a DWG`
- Mobile: hamburger menu
- CTA buttons match the brand teal `#0EA5A4`

### `Footer.tsx`

- 4-column layout: Product / Resources / Company / Legal
- Links + social icons
- Copyright + version

---

## 4. Section patterns

Most sections follow a consistent pattern:

```typescript
// Pattern: heading + sub + 4 cards or 3 cards or single CTA
export function SectionName() {
  return (
    <section id="section-id" className="...">
      <div className="container">
        <Eyebrow>CAPABILITY 03 · MATCHING</Eyebrow>
        <h2>Heading goes here</h2>
        <p>Sub-heading one-liner.</p>
        <div className="grid grid-cols-3 gap-6">
          <Card title="..." body="..." />
          <Card title="..." body="..." />
          <Card title="..." body="..." />
        </div>
      </div>
    </section>
  );
}
```

Each component accepts its copy as inline text (or could be lifted to a `content.ts` data file — see the marketing brief's "Marketing copy" section for that suggestion).

---

## 5. Animation patterns

- `RevealInit.tsx` — Intersection Observer based reveal animations
- Hero animation — subtle blueprint grid that fades in on load
- Hover states — teal accents on cards and CTAs

---

## 6. Theming

All components use the design tokens from the brief:

| Token | Value | Use |
|---|---|---|
| `--bg-primary` | `#FAFAF7` | Page background |
| `--bg-dark` | `#0F172A` | Hero dark sections, footer |
| `--text-primary` | `#0F172A` | Body text |
| `--text-muted` | `#64748B` | Captions |
| `--accent` | `#0EA5A4` | Primary teal |
| `--clash-hard` | `#DC2626` | Hard clash highlights |
| `--clash-soft` | `#F59E0B` | Soft intrusion |
| `--pass` | `#10B981` | Pass / compliant |

Tailwind is configured to use these tokens — see `tailwind.config.ts`.

---

## 7. Reference

- [`../reference/WEBSITE_CONTENT_BRIEF.md`](../reference/WEBSITE_CONTENT_BRIEF.md) — the marketing brief
- [`STRUCTURE.md`](./STRUCTURE.md) — overall frontend structure
- [`WORKSPACE.md`](./WORKSPACE.md) — the workspace components (not marketing)