const STANDARDS = {
  Structural: ["ACI 318", "AISC 360", "IS 800", "Eurocode 3"],
  "Load & General": ["ASCE 7", "IS 875", "Eurocode 1"],
  Seismic: ["IBC Ch 16/18/19", "IS 1893"],
  "Building Code": ["IBC", "CBC", "NFPA"],
};

export function Standards() {
  return (
    <section className="py-20 px-6">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-h2 font-bold mb-3">Code & standards library</h2>
        <p className="text-text-muted mb-10">
          Each rule cites the standard it's enforcing against.
        </p>
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {Object.entries(STANDARDS).map(([family, codes]) => (
            <div key={family}>
              <p className="font-mono text-eyebrow uppercase text-accent mb-3">{family}</p>
              <ul className="space-y-1">
                {codes.map((c) => (
                  <li key={c} className="text-sm">{c}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
