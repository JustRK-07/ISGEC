const STAGES = [
  { id: "L0", title: "Ingestion & Revision Lock", desc: "Git-like ledger of file revs" },
  { id: "L1", title: "DWG → DXF & Entity Extract", desc: "ezdxf + ODA, layers + blocks preserved" },
  { id: "L2", title: "Grid & Coordinate Registration", desc: "Real-world mm units already in DWG" },
  { id: "L3", title: "Semantic Normalization (Agent)", desc: "Local LLM with JSON-schema enforcement" },
  { id: "L4", title: "Rule Engine & Reporting", desc: "Distance, size, clash, tolerance — exact math" },
];

export function Pipeline() {
  return (
    <section className="py-20 px-6">
      <div className="max-w-6xl mx-auto">
        <p className="font-mono text-eyebrow uppercase text-text-muted mb-2">Architecture</p>
        <h2 className="text-h2 font-bold mb-10">5-layer pipeline</h2>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          {STAGES.map((s) => (
            <div key={s.id} className="border border-border rounded p-4">
              <p className="font-mono text-eyebrow uppercase text-accent mb-2">{s.id}</p>
              <h3 className="font-semibold text-sm mb-1">{s.title}</h3>
              <p className="text-xs text-text-muted">{s.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
