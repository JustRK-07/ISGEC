const CAPS = [
  { id: "01", title: "Semantic Normalization", body: "Reads firm-specific conventions and emits one canonical schema." },
  { id: "02", title: "Opening & Penetration Verification", body: "Required-vs-provided, sized, located, and elevation-checked." },
  { id: "03", title: "Smart ID Matching", body: "Fuzzy IDs across firms using Levenshtein + embeddings + grid proximity." },
  { id: "04", title: "Geometric Clash & Clearance", body: "Polygon-level intersection with real clearance values — not bounding boxes." },
  { id: "05", title: "Click-to-Locate Findings", body: "Every flagged item is one click from its exact drawing location." },
];

export function Capabilities() {
  return (
    <section className="py-20 px-6 bg-white">
      <div className="max-w-6xl mx-auto">
        <p className="font-mono text-eyebrow uppercase text-text-muted mb-2">Capabilities</p>
        <h2 className="text-h2 font-bold mb-10">Five things it does that manual review doesn't</h2>
        <div className="space-y-8">
          {CAPS.map((c, i) => (
            <div key={c.id} className={`grid md:grid-cols-2 gap-6 ${i % 2 ? "md:[direction:rtl]" : ""}`}>
              <div className="[direction:ltr]">
                <p className="font-mono text-eyebrow uppercase text-accent mb-2">
                  Capability {c.id}
                </p>
                <h3 className="text-h3 font-semibold mb-3">{c.title}</h3>
                <p className="text-text-muted">{c.body}</p>
              </div>
              <div className="[direction:ltr] bg-bg-dark rounded h-48 flex items-center justify-center text-text-muted font-mono text-sm">
                [ screenshot placeholder ]
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
