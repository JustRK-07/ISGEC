"use client";

import { useState } from "react";

const QUESTIONS: Array<{ q: string; a: React.ReactNode }> = [
  { q: "Do you support DWG?", a: <>Yes — DWG is our primary format. We convert DWG to DXF (text format) via the free ODA File Converter, then read every entity, layer, block, and line type with ezdxf in pure Python. Coordinates are already in real-world mm — no scale guessing.</> },
  { q: "Do I need a BIM model?", a: <>No — we work directly on DWG files. BIM (IFC, Revit) is supported but not required. The 80% of projects without coordinated BIM is our primary audience.</> },
  { q: "What about scanned or paper-only drawings?", a: <>For paper-only legacy archives, we offer a secondary vision path using a <strong>self-hosted multimodal LLM</strong> with Tesseract OCR fallback. Vision results carry a confidence flag and can be overridden by reviewers. No third-party API is ever called.</> },
  { q: "What file formats are supported?", a: <>DWG (primary), DXF (direct read), IFC, RVT. DWG-exported PDFs and scanned legacy sheets are supported as secondary paths. The system auto-detects format and routes to the appropriate extraction path.</> },
  { q: "Can I run it on-prem?", a: <>Yes — Enterprise tier includes VPC and full on-prem deployment for restricted projects. Your data never leaves your perimeter if you need it not to.</> },
  { q: "Can I add custom rules?", a: <>Yes — via the Prompt Lab and Rule Builder, no code required. Encode client-specific tolerances or jurisdiction-specific standards in plain English.</> },
  { q: "What happens when drawings change?", a: <>Revisions are tracked in a Git-like ledger. Re-run validation on the new revision and diff against the previous one to see exactly what changed.</> },
  { q: "How is the AI trained?", a: <>It isn&apos;t, in the traditional sense. We use <strong>self-hosted open-weight LLMs</strong> (Qwen, Llama, DeepSeek, Mistral, Granite — model is swappable) with structured tool calls and JSON-schema-constrained output. <strong>Zero third-party API calls</strong> — your drawings never leave your infrastructure. No labeled training data needed. DWG structure is parsed deterministically by ezdxf.</> },
  { q: "Can it detect 3D clashes?", a: <>Yes — once BIM (IFC/RVT) is provided, we extrude 2D footprints and run 3D intersection via trimesh. 2D drawing validation is the v1 primary capability.</> },
  { q: "How long does a typical review take?", a: <>5–15 minutes for a single drawing set, depending on size and complexity. Faster than manual review by an order of magnitude.</> },
];

export function FAQ() {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <section className="section" id="faq">
      <div className="container">
        <div className="section-header center reveal">
          <div className="section-label">16 / FAQ</div>
          <h2>Questions engineers actually ask.</h2>
        </div>

        <div className="faq reveal">
          {QUESTIONS.map((item, i) => (
            <div key={item.q} className={`faq-item${open === i ? " open" : ""}`}>
              <button className="faq-q" type="button" onClick={() => setOpen(open === i ? null : i)}>
                {item.q}
              </button>
              <div className="faq-a"><div className="faq-a-inner">{item.a}</div></div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
