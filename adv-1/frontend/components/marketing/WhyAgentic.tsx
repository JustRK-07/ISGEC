const ROWS: Array<{ label: string; us: string; them: string }> = [
  { label: "Labeled training data", us: "None — self-hosted open-weight LLM with structured tool calls", them: "Hundreds to thousands of manually labeled drawings" },
  { label: "Data residency", us: "100% on-prem — zero third-party API", them: "Depends on hosting — usually cloud" },
  { label: "Model swap-ability", us: "Swappable — Qwen, Llama, DeepSeek, Mistral, Granite", them: "Locked to retraining cycle" },
  { label: "Time to first version", us: "Days to a few weeks", them: "Weeks to months (labeling + training + tuning)" },
  { label: "DWG accuracy", us: "Exact — entities, layers, blocks, real-world mm", them: "Lost — must convert DWG to image first" },
  { label: "Drawing style robustness", us: "Handles any DWG style out of the box", them: "Struggles until retrained on similar style" },
  { label: "New drawing styles", us: "Reasonably well out of the box", them: "Struggles until retrained" },
  { label: "Math check determinism", us: "Fully deterministic formulas", them: "Confidence-scored predictions" },
  { label: "Audit / compliance", us: "Every finding = exact formula + number", them: "Every finding = predicted box + score" },
  { label: "Ongoing maintenance", us: "Light — prompt tuning", them: "Heavy — labeling + retraining loop" },
  { label: "Team required", us: "Software engineers", them: "Engineers + ML team + labeling team" },
];

export function WhyAgentic() {
  return (
    <section className="section" id="why">
      <div className="container">
        <div className="section-header reveal">
          <div className="section-label">07 / WHY AGENTIC AI</div>
          <h2>Why a self-hosted local LLM agent — not a trained ML model.</h2>
          <p className="lede">
            The core checks are exact rule-based math — distance, size, overlap, tolerance
            — not pattern recognition. Putting those exact formulas behind a{" "}
            <strong>self-hosted local LLM</strong> gives you deterministic, audit-defensible
            findings <em>and</em> full data residency: zero third-party API calls, zero data
            egress, zero tokens billed to a vendor.
          </p>
        </div>

        <div className="compare reveal">
          <div className="compare-row header">
            <div>Factor</div>
            <div>Self-hosted local LLM agent (us)</div>
            <div>Trained ML Model</div>
          </div>
          {ROWS.map((r) => (
            <div key={r.label} className="compare-row">
              <div className="compare-cell label">{r.label}</div>
              <div className="compare-cell us">{r.us}</div>
              <div className="compare-cell them">{r.them}</div>
            </div>
          ))}
        </div>

        <div className="compare-rec reveal">
          <div className="compare-rec-tag">RECOMMENDATION</div>
          <p>
            We treat ML as an optional narrow add-on (e.g., for scanned-only symbol detection)
            only once enough real project drawings exist as training data. For v1, a{" "}
            <strong>self-hosted local LLM agent</strong> is the right primary approach because
            the checks are exact math, the inputs are mostly vector, and AEC clients demand
            full data residency. The model is swappable — Qwen, Llama, DeepSeek, Mistral,
            Granite — without rewriting the pipeline, and nothing in the call path ever leaves
            your hardware.
          </p>
        </div>
      </div>
    </section>
  );
}
