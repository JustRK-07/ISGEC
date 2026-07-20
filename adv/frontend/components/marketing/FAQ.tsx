"use client";

import { useState } from "react";

const QUESTIONS = [
  { q: "Do you support DWG?", a: "Yes — DWG is our primary format, read natively via ezdxf + ODA File Converter. Scanned legacy sheets supported via AI vision as a secondary path." },
  { q: "Do I need a BIM model?", a: "No — we work directly on PDFs and DWGs. BIM (IFC, Revit) is supported but not required." },
  { q: "How accurate is the AI vision on scanned drawings?", a: "We use a self-hosted multimodal LLM with Tesseract OCR fallback. Vector files are extracted exactly. Vision results carry a confidence flag." },
  { q: "What file formats are supported?", a: "DWG (primary), DXF (direct read), IFC, RVT. DWG-exported PDFs and scanned legacy sheets as secondary paths." },
  { q: "Can I run it on-prem?", a: "Yes — Enterprise tier includes VPC and on-prem deployment." },
  { q: "Can I add custom rules?", a: "Yes — via the Prompt Lab and Rule Builder (no code required)." },
  { q: "What happens when drawings change?", a: "Revisions are tracked. Re-run validation on the new rev and diff against the previous one." },
  { q: "How is the AI trained — and where does it run?", a: "It isn't, in the traditional sense. We use self-hosted open-weight LLMs with structured tool calls. Zero third-party API calls." },
  { q: "Can it detect 3D clashes?", a: "Yes — once BIM (IFC/RVT) is provided, we extrude 2D footprints and run 3D intersection." },
  { q: "How long does a typical review take?", a: "5–15 minutes for a single drawing set, depending on size." },
];

export function FAQ() {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <section className="py-20 px-6 bg-white">
      <div className="max-w-3xl mx-auto">
        <h2 className="text-h2 font-bold mb-10 text-center">FAQ</h2>
        <div className="space-y-2">
          {QUESTIONS.map((item, i) => (
            <div key={item.q} className="border border-border rounded">
              <button
                onClick={() => setOpen(open === i ? null : i)}
                className="w-full text-left p-4 font-medium flex justify-between items-center"
              >
                <span>{item.q}</span>
                <span className="text-text-muted">{open === i ? "−" : "+"}</span>
              </button>
              {open === i && <p className="px-4 pb-4 text-sm text-text-muted">{item.a}</p>}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
