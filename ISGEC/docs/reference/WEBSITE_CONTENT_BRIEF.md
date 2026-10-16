# Agentic Drawing Validator — Website Content Brief

> **Document type:** Content + design brief for marketing website
> **Audience:** Designer, front-end developer, copywriter
> **Goal:** Position an engineering-defensible, DWG-native, agentic AI drawing-validation platform for the AEC QA/QC market.
> **Positioning line:** *DWG-native. Rule-grounded. Sheet-locatable. No confidence percentages.*

---

## 0. Brand & Positioning Foundation

### One-liner
> **Agentic Drawing Validator** catches the support, opening, and clash errors that Mechanical GA → Structural GA reviews miss — by reading native DWG files, grounding every finding to a sheet, a gridline, and an exact numeric difference, and running **100% on your hardware with a self-hosted LLM. No cloud. No API calls. No data egress.**

### Four positioning pillars (every section reinforces one of these)

| Pillar | Meaning | Reinforced in sections |
|---|---|---|
| **1. Engineering-Defensible** | Every finding = sheet + grid + element + formula. No black-box confidence scores. | Hero, Capability 5, Defensibility section |
| **2. DWG-Native, Authoring-Format Aware** | We read the source DWG directly — layers, blocks, line types, real-world units preserved. Not a flattened raster. | Hero, Architecture, Supported Formats |
| **3. Multi-Agent Architecture** | Specialized agents (Ingestion, Normalization, Rule, Reporting) instead of one giant prompt. | Architecture, Why Agentic AI |
| **4. On-Premise, Zero-API, Local LLM** | All inference runs locally — self-hosted open-weight model. **No third-party API calls, no data egress.** | Hero, Architecture, Security, FAQ #8 |

### Visual motif
- **Blueprint / QA-stamp** language throughout (e.g., `SHEET S-01 · GRID TP104-B/2`, `REV-C · APPROVED`, `QA/QC REVIEW · PASSED`)
- **Single accent color** (teal/blue, ~#0EA5A4) on an off-white background with dark navy text
- **Iconography** borrows from engineering: ruler, compass, grid bubble, dimension callout
- **Mock-up aesthetic** for product screenshots — show the *actual* click-to-locate viewer, not abstract illustrations

### Tone of voice
- Direct, technical, no marketing fluff
- Speaks engineer-to-engineer
- Quantifies claims (e.g., "90%+ detection on opening mismatches" not "highly accurate")
- Acknowledges limits honestly ("We read DWG natively — the authoring format engineers actually draft in")

### Trust signals to include
- Trusted-by logo strip (placeholder firm names acceptable)
- Press mentions (ENR, Forbes, AEC Magazine)
- QA-stamp styled testimonials
- "Free first check" CTA repeated

---

## 1. Hero Section

**Layout:** Centered headline + sub-headline + dual CTA + animated product preview showing a flagged clash being clicked to its drawing location. Logo strip below.

**Eyebrow tag:** `QA/QC · DWG-NATIVE · ON-PREM · LOCAL LLM · AGENTIC AI`

**Headline (H1):**
> Catch the clashes your Mechanical and Structural GA reviews miss.

**Sub-headline:**
> An agentic AI platform that reads native DWG files and validates every support, opening, and penetration across disciplines — grounding every finding to a sheet, a gridline, and an exact numeric difference. **100% on-prem. Self-hosted local LLM. Zero third-party API calls — your drawings never leave your infrastructure.**

**Primary CTA:** `Upload a DWG · Free First Check`
**Secondary CTA:** `Book a 20-min Demo`

**Trust strip (below CTA):**
> Trusted by engineering teams at — *Syska Hennessy · GPD Group · Kleinknecht · BGE · 4Creeks · SJB*

**Animation notes:**
- Background: subtle blueprint grid that fades in
- Foreground: an animated GIF/video showing a clash being highlighted in red on a superimposed GA, then the inspector panel scrolling to the flagged item
- The click-to-locate moment is the hero — show it visually

**Reference:** getstructured.ai hero pattern + Nonlinear dark hero contrast.

---

## 2. Problem Statement

**Layout:** Four-column grid of pain-point cards. Each card has a line-icon, a one-sentence problem, and a one-sentence consequence.

| Card | Icon | Problem | Consequence |
|---|---|---|---|
| **Missed Supports** | anchor | Mechanical GA requires a support at TP104-B/2; Structural GA doesn't show it. | Equipment sags, vibration, premature failure. |
| **Wrong-Sized Openings** | ruler | Required 300×200 duct opening; provided 250×200. | Field rework, cost overruns, schedule slip. |
| **Undetected Clashes** | collision | A required opening falls directly on a primary beam. | Demo, rebar redesign, structural RFI cascade. |
| **Tolerance Drift** | ± | Position off by 60 mm when only ±25 mm is permitted. | Misalignment cascades through the whole system. |

**Closing line:**
> Today these checks are manual, slow, inconsistent across reviewers, and easy to skip under deadline pressure.

---

## 3. Solution Architecture — 5 Layers + Layer 0

**Layout:** Horizontal pipeline diagram with 5 numbered stages. Each stage has a name, an icon, a one-line purpose, and the agent(s) responsible. Below the diagram, an expandable "Technical Details" panel.

### Pipeline diagram

```
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ L0              │   │ L1              │   │ L2              │   │ L3              │   │ L4              │
│ INGESTION &     │ → │ DWG → DXF &     │ → │ GRID &          │ → │ SEMANTIC        │ → │ RULE ENGINE &   │
│ REVISION LOCK   │   │ ENTITY EXTRACT  │   │ COORDINATE      │   │ NORMALIZATION   │   │ REPORTING       │
│                 │   │                 │   │ REGISTRATION    │   │ (AGENT)         │   │ (DETERMINISTIC) │
└─────────────────┘   └─────────────────┘   └─────────────────┘   └─────────────────┘   └─────────────────┘
   Git-like ledger      ezdxf + ODA,         Real-world mm units    Canonical schema      Distance, size,
   of file revs         layers+blocks+       (already in DWG)       across disciplines    clash, tolerance
                        entities preserved
```

### Each layer explained

**Layer 0 — Ingestion & Revision Lock**
- **Purpose:** Hash each uploaded DWG. Detect duplicates, supersessions, and revision chains (Rev A → B → C).
- **Why it matters:** Prevents validating against a stale baseline.
- **Tech:** SHA-256 hashing, PostgreSQL revision ledger.

**Layer 1 — DWG → DXF & Entity Extraction**
- **Purpose:** Convert DWG to DXF (text format) and extract every entity — lines, polylines, text, blocks, hatches, dimensions — with its layer, color, line type, and coordinates.
- **Why it matters:** DWG is the authoring format. We read what the engineer drafted — including layer structure and block definitions that get lost in any raster export.
- **Tech:** ezdxf (pure Python), ODA File Converter (free, DWG → DXF for newer versions), LibreDWG as open-source alternative.

**Layer 2 — Grid & Coordinate Registration**
- **Purpose:** Detect grid bubble labels (e.g., `TP104-A`, `1`, `2`). DWG already stores real-world mm units, so no scale detection is needed — just grid-line mapping.
- **Why it matters:** Distance formulas only work when both drawings share a reference frame.
- **Tech:** Custom text-extraction from DXF entities + grid-line grouping by layer convention.

**Layer 3 — Semantic Normalization (Agent Layer)**
- **Purpose:** AI agent reads DWG entities and outputs a canonical schema:
  ```
  Support    { id, type: restraint|anchor|guide, grid, x_mm, y_mm, load_kg, fluid }
  Opening    { id, service: duct|pipe|cable, grid, x, y, w, h, elevation }
  Member     { id, type: beam|column|brace, section, grid_start, grid_end, profile }
  Tolerance  { project_default, opening_size, position, elevation }
  ```
- **Why it matters:** Firm-specific naming and conventions collapse into a single project schema.
- **Tech:** **Self-hosted LLM** (served locally via Ollama / vLLM / llama.cpp — no third-party API calls) with tool-calling and structured-output enforcement (JSON-schema / GBNF grammar). Model is swappable; the orchestration layer is model-agnostic.

**Layer 4 — Rule Engine (Deterministic)**
- **Purpose:** Apply exact formulas to flagged issues.
- **Why it matters:** Engineers need auditable math, not a confidence score.
- **Tech:** Python, Shapely, NumPy, RapidFuzz, sentence-transformers.
- **Checks run:**
  1. Fuzzy ID match (Levenshtein + semantic embeddings)
  2. Position tolerance (Euclidean)
  3. Size tolerance (per-axis)
  4. Polygon-level clash detection
  5. Clearance zone violation
  6. Elevation / T.O.S. alignment
  7. Required-but-missing detection
  8. Provided-but-orphaned detection

**Reference pattern:** getstructured.ai "QA/QC Compliance Checks" feature block + Stru AI 2D-PDF pipeline transparency (adapted for DWG-native).

---

## 4. Five Core Capabilities

**Layout:** Alternating left-right two-column sections. Each has an eyebrow tag, a bold headline, 2-3 sentences of body copy, a bullet list of sub-capabilities, and a product screenshot on the other side.

### Capability 1 — Semantic Normalization Across Disciplines

**Eyebrow:** `CAPABILITY 01 · SCHEMA`
**Headline:** One canonical schema for every firm's drawing convention.
**Body:** The Normalization Agent reads each drawing in its native style — Bechtel tag IDs, Fluor section codes, EPC vendor conventions — and emits a single canonical JSON schema. Downstream rules never have to learn firm-specific formats.

**Sub-capabilities:**
- Support taxonomy: `restraint` | `anchor` | `guide` | `saddle`
- Opening taxonomy: `duct` | `pipe` | `cable-tray` | `sleeve` | `trench`
- Member taxonomy: `beam` | `column` | `brace` | `truss` | `joist`
- Auto-detection of tag patterns: `F11WE`, `TP4BM101`, `M-OP-203`
- Sheet metadata: rev, drawn by, scale, units

### Capability 2 — Opening & Penetration Verification

**Eyebrow:** `CAPABILITY 02 · OPENINGS`
**Headline:** Every opening matched, sized, located, and elevation-checked.
**Body:** Required openings from Mechanical GA are matched to provided openings in Structural GA using fuzzy ID + proximity. Each match is checked for size, position, and T.O.S. elevation alignment.

**Sub-capabilities:**
- Required-vs-provided inventory diff
- Per-axis size tolerance check (width AND height)
- Euclidean position tolerance
- Elevation / T.O.S. alignment (e.g., `+13.150m` required, `+13.350m` provided → flag)
- Sleeve vs trench vs opening detection
- Required-but-missing flag
- Orphan-provided flag

### Capability 3 — Smart ID Matching

**Eyebrow:** `CAPABILITY 03 · MATCHING`
**Headline:** Fuzzy ID matching that handles inconsistent tagging across firms.
**Body:** Mechanical and Structural drawings rarely share the same tag for the same physical item. The matching engine combines Levenshtein distance, semantic embeddings, and grid proximity to pair items correctly — even when one side says `F11WE` and the other says `TP4BM101`.

**Sub-capabilities:**
- Levenshtein-based fuzzy string match
- Sentence-transformer semantic similarity
- Grid-bubble proximity weighting
- Confidence-banded output (Pass / Verify / Manual)
- Override-able by reviewer

### Capability 4 — Geometric Clash & Clearance Detection

**Eyebrow:** `CAPABILITY 04 · CLASH`
**Headline:** Polygon-level clash detection with real clearance values.
**Body:** Bounding boxes are too coarse. The clash engine converts every footprint and member into polygons (or extruded shapes for 3D), then computes true geometric intersection and clearance distance using Shapely.

**Sub-capabilities:**
- Polygon intersection (not just bounding box)
- Clearance zone violations (e.g., 50 mm required, 20 mm provided → flag)
- Hard clash vs soft intrusion classification
- Multi-discipline overlays (Mech + Str + Arch + Plumbing)
- 3D-ready (trimesh + IFC support)
- Beam-vs-opening conflict as a first-class check

### Capability 5 — Click-to-Locate Findings

**Eyebrow:** `CAPABILITY 05 · LOCATABILITY`
**Headline:** Every flagged item is one click away from its exact drawing location.
**Body:** Findings aren't abstract reports. Each card shows the sheet, grid, X-Y coords, and a click-to-zoom button. Reviewers jump from the inspector panel straight to the issue — no scrolling, no guessing.

**Sub-capabilities:**
- Sheet + grid + X-Y metadata per finding
- One-click zoom in the drawing viewer
- Highlighted overlay on the relevant geometry
- Side-by-side Mech vs Str view
- Annotation layer for reviewer comments
- Export to Word/PDF with embedded screenshots

---

## 5. How It Works — 4-Step Rail

**Layout:** Horizontal numbered rail with 4 cards. Each card has a number, an icon, a one-line action, and a description.

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ 1       │ → │ 2       │ → │ 3       │ → │ 4       │
│ Upload  │   │ Detect  │   │ Match & │   │ Sign    │
│         │   │         │   │ Check   │   │ Off     │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
```

**Step 1 — Upload Drawings**
Drop in your Mechanical GA, Structural GA, and (optional) Superimposed as native DWG files. DXF, IFC, and RVT also supported.

**Step 2 — Auto-Detect Format & Grid**
The Ingestion Agent hashes files, detects vector vs raster, and registers each sheet to a unified coordinate frame using the grid bubbles.

**Step 3 — Match & Check**
The Normalization Agent builds canonical element lists. The Rule Engine runs 8 deterministic checks. Findings stream into the inspector panel.

**Step 4 — Review & Sign Off**
Click any finding to jump to its location. Approve, override, or comment. Export a signed PDF report with full audit trail.

---

## 6. Why Agentic AI (vs a Trained ML Model)

**Layout:** Two-column comparison table + closing recommendation paragraph.

### Comparison table

| Factor | Agentic AI (Self-Hosted LLM) | Trained ML Model |
|---|---|---|
| Labeled training data needed | None | Hundreds to thousands of drawings, manually labeled |
| Time to first working version | Days to a few weeks | Weeks to months (labeling + training + tuning) |
| **DWG accuracy** | **Exact — entities, layers, blocks, real-world mm** | **Lost — must convert DWG to image first** |
| Drawing style robustness | Handles any DWG style out of the box | Struggles until retrained on similar styles |
| Math check determinism | Fully deterministic formulas | Confidence-scored predictions |
| Audit / compliance defensibility | Every finding = exact formula + number | Every finding = predicted box + score |
| **Data residency** | **100% on-prem, zero third-party API** | Depends on hosting — usually cloud |
| Model swap-ability | Swappable (Qwen / Llama / DeepSeek / Mistral / Granite) | Locked to retraining cycle |
| Ongoing maintenance | Light — model swap or prompt tuning | Heavy — labeling + retraining loop |
| Team required | Software engineers | Engineers + ML team + labeling team |

### Recommendation paragraph
> **The core checks are exact rule-based math** — distance, size, overlap, tolerance — not pattern recognition. Putting exact formulas behind a **self-hosted LLM agent** that handles reading and normalization gives you deterministic, audit-defensible findings *and* full data residency. No drawing pixel, text string, or coordinate ever leaves your hardware. We treat ML as an optional narrow add-on (e.g., for scanned-only symbol detection) only once enough real project drawings exist as training data.

**Reference pattern:** Your original proposal's Section 3 comparison, condensed.

---

## 7. Engineering Defensibility (Differentiator)

**Layout:** Centered callout block. Large quote-style framing.

**Headline:** Every finding traces back to a sheet, a gridline, an element, and a formula.

**Three columns below:**

| Sheet | Grid | Formula |
|---|---|---|
| Every finding cites `SHEET-S02` (or `M-01`, `REV-C`). | Every finding cites the grid intersection, e.g., `GRID TP104-B / 2`. | Every finding shows the exact rule applied and the numeric result. |

**Closing line:**
> No confidence percentages. No black boxes. If a reviewer asks *why was this flagged*, the answer is one click away.

**Reference pattern:** getstructured.ai's differentiator — "Every answer is grounded to a specific sheet, location, and element — no confidence percentages."

---

## 8. Supported Formats

**Layout:** Icon grid with format name, description, and use case. DWG is primary.

| Format | Path | Use Case |
|---|---|---|
| **DWG** (primary) | ODA File Converter + ezdxf | Native AutoCAD authoring files — full entity, layer, block, line-type access |
| **DXF** | ezdxf direct | AutoCAD export format — text-readable, no conversion needed |
| **IFC** | ifcopenshell | BIM model export for 3D validation |
| **RVT** | Autodesk Forge / Revit API | Direct Revit model query |
| **DWG → PDF export** (reference only) | PyMuPDF | Generated PDF from DWG for visual reference / archival |
| **Scanned legacy sheets** | Local multimodal LLM + Tesseract OCR fallback | Optional secondary path for legacy paper-only archives — runs entirely on-prem |

**Why DWG first:**
> DWG is the authoring format engineers draft in. Reading DWG natively preserves layer structure, block definitions, line types, and real-world mm coordinates — information that's flattened or lost in any raster export. One canonical JSON output, regardless of which authoring tool produced the DWG.

---

## 9. Integrations

**Layout:** Logo grid + short captions.

**Integrations shown:**
- **Procore** — push findings as RFIs
- **Autodesk Construction Cloud (ACC)** — pull drawings directly from project files
- **Bluebeam** — push markup overlays back to the PDF
- **SharePoint / Drive** — file sync
- **Revit / IFC** — model query for 3D clashes
- **Outlook / Teams** — finding notifications and sign-off routing
- **Power BI / Tableau** — finding analytics dashboards

**Reference pattern:** Nonlinear integrations row + getstructured.ai "Seamless Integration" card.

---

## 10. Security & Compliance

**Layout:** Three security cards + audit ledger callout + zero-API guarantee.

### Three cards

| Enterprise Security | Private Cloud / On-Prem | Role-Based Access |
|---|---|---|
| SOC 2 Type II, AES-256 at rest, TLS 1.3 in transit | VPC deployment or full on-prem option for restricted projects | Engineer · Reviewer · Admin · Super Admin |

### Zero third-party API callout (NEW for security-first pitch)
> **No drawing data ever leaves your infrastructure.** All LLM inference runs locally on your hardware — Ollama, vLLM, or llama.cpp serving an open-weight model. No tokens, no rate limits, no API keys, no telemetry to third parties. Models are swappable (Qwen, Llama, DeepSeek, Mistral, Granite).

### Audit ledger (callout box)
> Every action — upload, view, override, sign-off, export — is logged with timestamp, user ID, and IP. Drawings are immutable once sealed. Compliance teams get read-only audit reports.

---

## 11. Use Cases

**Layout:** Three detailed use-case cards with mini-screenshots.

### Use Case 1 — Mechanical GA ↔ Structural GA
The headline use case. Validate supports, openings, penetrations, and elevations between disciplines.
*Example:* Mech GA requires a 300×200 duct opening at TP104-B/2 elevation +13.150m. Str GA provides 250×200 at +13.350m. **Both fail tolerance → flagged.**

### Use Case 2 — Revision Comparison
Upload Rev A and Rev C of the Structural GA. Get a structural diff: which beams moved, which openings changed, which supports were added or removed.

### Use Case 3 — Multi-Discipline Clash Overlay
Upload Mech + Str + Plumbing + Fire Protection. Get a unified superimposed view with all clashes color-coded by severity.

---

## 12. Code & Standards Library

**Layout:** Categorized list of supported codes and standards.

**Structural:**
- ACI 318 (Concrete)
- AISC 360 (Steel)
- IS 800 (Indian Steel)
- Eurocode 3 (European Steel)

**Load & General:**
- ASCE 7
- IS 875
- Eurocode 1

**Seismic:**
- IBC (Chapters 16, 18, 19)
- IS 1893

**Building Code:**
- IBC, CBC, NFPA (InspectMind-style coverage)

**Note:** Each rule has a citation. When the system flags a tolerance violation, it cites the standard it's enforcing against.

**Reference pattern:** Stru AI (IBC, ASCE 7, ACI 318, AISC 360) + InspectMind (IBC, CBC, NFPA).

---

## 13. Pricing

**Layout:** Three-tier pricing table with a featured middle tier.

| Starter | **Professional** *(Featured)* | Enterprise |
|---|---|---|
| Free first check | $X / project | Custom |
| 1 project, 5 sheets | Unlimited projects, unlimited sheets | Unlimited + on-prem + SSO |
| Standard support | Priority support + Slack | Dedicated CSM + SLA |
| Vector + scanned | + Revision comparison | + Custom rules + private deployment |

**Closing CTA:** *Not sure which fits? Run a free first check and we'll show you exactly what your project would catch.*

**Reference pattern:** InspectMind's "$50, first check free" model.

---

## 14. Testimonials / Trust

**Layout:** QA-stamp styled testimonial cards.

### Testimonial 1
> "We used to spend 3 days per drawing set on cross-discipline reviews. Now it's 30 minutes — and we catch more."
> **— Senior Structural Engineer, EPC firm**

### Testimonial 2
> "The click-to-locate feature alone changed how we run reviews. Every flagged item is a one-click zoom."
> **— QA/QC Lead, M&E consultant**

### Testimonial 3
> "Every finding shows the exact formula and the exact number. That's the only kind of evidence our sign-off process accepts."
> **— Chief Engineer, data center developer**

**Visual treatment:** Each testimonial card looks like a QA-stamp drawing seal, with `REVIEW · PASSED` style framing.

**Reference pattern:** getstructured.ai QA-stamp testimonial.

---

## 15. FAQ

**Layout:** Accordion with questions visible, answers collapsed. 8-10 questions.

1. **Do you support DWG?** Yes — DWG is our primary format, read natively via ezdxf + ODA File Converter. Scanned legacy sheets supported via AI vision as a secondary path.
2. **Do I need a BIM model?** No — we work directly on PDFs and DWGs. BIM (IFC, Revit) is supported but not required.
3. **How accurate is the AI vision on scanned drawings?** We use a **self-hosted multimodal LLM** with Tesseract OCR fallback. Vector files are extracted exactly. Vision results carry a confidence flag. Nothing leaves your perimeter.
4. **What file formats are supported?** DWG (primary), DXF (direct read), IFC, RVT. DWG-exported PDFs and scanned legacy sheets as secondary paths.
5. **Can I run it on-prem?** Yes — Enterprise tier includes VPC and on-prem deployment.
6. **Can I add custom rules?** Yes — via the Prompt Lab and Rule Builder (no code required).
7. **What happens when drawings change?** Revisions are tracked. Re-run validation on the new rev and diff against the previous one.
8. **How is the AI trained — and where does it run?** It isn't, in the traditional sense. We use **self-hosted open-weight LLMs** (Qwen, Llama, DeepSeek, Mistral — model is swappable) with structured tool calls. **Zero third-party API calls** — your drawings never leave your infrastructure. No labeled training data needed.
9. **Can it detect 3D clashes?** Yes — once BIM (IFC/RVT) is provided, we extrude 2D footprints and run 3D intersection.
10. **How long does a typical review take?** 5–15 minutes for a single drawing set, depending on size.

**Reference pattern:** getstructured.ai + InspectMind FAQ structure.

---

## 16. Final CTA

**Layout:** Full-width dark section with headline, dual CTA, supporting visual.

**Headline:** Ready to catch what your last review missed?

**Primary CTA:** `Book a 20-min Demo`
**Secondary CTA:** `Run a Free First Check`
**Tertiary link:** `View a Sample Report`

**Below the fold:**
- Logo strip (trusted by)
- 1-line testimonial pull-quote
- Footer with product / resources / company / legal columns

---

## Design System Tokens

### Colors
| Token | Value | Use |
|---|---|---|
| `--bg-primary` | `#FAFAF7` | Page background (off-white, blueprint feel) |
| `--bg-dark` | `#0F172A` | Hero dark sections, footer |
| `--text-primary` | `#0F172A` | Body text (dark navy) |
| `--text-muted` | `#64748B` | Captions, labels |
| `--accent` | `#0EA5A4` | Primary teal accent |
| `--accent-hover` | `#0D9488` | Accent hover state |
| `--clash-hard` | `#DC2626` | Hard clash highlights |
| `--clash-soft` | `#F59E0B` | Soft intrusion / clearance |
| `--pass` | `#10B981` | Pass / compliant |
| `--border` | `#E2E8F0` | Subtle dividers |

### Typography
| Token | Font | Size | Use |
|---|---|---|---|
| `--font-display` | Inter (or Söhne) | 56/64px | H1 hero |
| `--font-h2` | Inter | 40/48px | Section headlines |
| `--font-h3` | Inter | 24/32px | Capability headlines |
| `--font-body` | Inter | 16/24px | Body copy |
| `--font-mono` | JetBrains Mono | 14/20px | Dimension labels, finding IDs |
| `--font-eyebrow` | Inter uppercase | 12/16px tracking 0.1em | Eyebrow tags |

### Spacing scale
8 / 16 / 24 / 32 / 48 / 64 / 96 / 128 px

### Components
- Sticky navigation
- Hero with animated product preview
- Alternating L/R feature blocks
- Logo strip / marquee
- Accordion FAQ
- Pricing table (3-tier)
- QA-stamp testimonial cards
- Integration logo grid
- Pipeline diagram (5 stages)
- Click-to-locate mockup viewer

---

## Page Flow Summary (Top to Bottom)

```
[ Announcement bar — "$4.2M seed round covered by ENR" ]
[ Sticky nav ]
[ 1. Hero ]
[ Trusted-by logo strip ]
[ 2. Problem Statement (4 cards) ]
[ 3. Solution Architecture (5-layer diagram) ]
[ 4. Five Core Capabilities (alternating L/R) ]
[ 5. How It Works (4-step rail) ]
[ 6. Why Agentic AI vs ML (comparison) ]
[ 7. Engineering Defensibility callout ]
[ 8. Supported Formats (icon grid) ]
[ 9. Integrations (logo grid) ]
[ 10. Security & Compliance (3 cards + audit ledger) ]
[ 11. Use Cases (3 detailed) ]
[ 12. Code & Standards Library ]
[ 13. Pricing (3-tier) ]
[ 14. Testimonials (QA-stamp cards) ]
[ 15. FAQ (accordion) ]
[ 16. Final CTA (full-width) ]
[ Footer ]
```

---

## Key Differentiators Recap (use as "Why Us" anchor block)

1. **DWG-native, authoring-format aware** — we read the source DWG directly. Layers, blocks, line types, and real-world mm units all preserved.
2. **Engineering-defensible findings** — every flagged item = sheet + grid + element + formula. No confidence percentages.
3. **Multi-agent architecture** — Ingestion → DWG Extraction → Registration → Normalization → Rules → Reporting.
4. **Click-to-locate UI** — every finding is one click from its exact drawing location.
5. **Polygon-level clash + clearance** — not just bounding boxes. Real geometric intersection with clearance values.
6. **Fuzzy ID matching** — handles inconsistent tagging across firms (Bechtel vs Fluor vs EPC vendors).
7. **Revision ledger** — Git-like tracking of every drawing version. Validate against the right baseline.
8. **Human-in-the-loop sign-off** — Engineer → Reviewer → Admin workflow with audit trail.
9. **Code & standards library** — IBC, ASCE 7, ACI 318, AISC 360, IS 800, Eurocode — citations on every rule.
10. **Open ecosystem** — Procore, ACC, Bluebeam, SharePoint, Revit, IFC.
11. **Zero third-party API — fully on-prem** — self-hosted open-weight LLM (Qwen / Llama / DeepSeek / Mistral / Granite). No tokens, no rate limits, no telemetry to a third party. Drawings never leave your infrastructure. Model is swappable.

---

## Out of Scope for v1 (mention as "coming soon")

- Native 3D clash (full IFC/RVT extrusion pipeline) — foundation ready, full 3D in v2
- Generative drawing fixes ("auto-redesign the missed support") — future capability
- Field verification via mobile camera — v2 feature

---

## Appendix: Sources & Inspiration

- [getstructured.ai](https://getstructured.ai) — blueprint motif, sheet+grid+element grounding, agent playground
- [InspectMind.ai](https://www.inspectmind.ai/) — text-driven trust, code citations, free first check
- [Nonlinear.build](https://www.nonlinear.build/solutions/qa-qc) — accordion features, integrations, dark hero
- [Stru AI](https://stru.ai/blog/ai-tools-construction-drawing-review-automation-2026) — 2D PDF focus, engineer credibility, codes
- [Helonic — Best AI Construction Drawing Review Tools 2026](https://helonic.com/blog/best-ai-construction-drawing-review-tools-2026)
- [Nomic AI — Best AI for Drawing Review](https://www.nomic.ai/compare/best-ai-for-drawing-review)

---

*End of brief. Hand to designer + developer. Sections are independent — order can be tuned. The three pillars (Engineering-Defensible · DWG-Native · Multi-Agent) must echo in copy throughout.*