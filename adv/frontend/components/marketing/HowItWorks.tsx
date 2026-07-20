const STEPS = [
  { n: 1, title: "Upload Drawings", desc: "Drop in your Mech GA, Str GA, optional superimposed." },
  { n: 2, title: "Auto-Detect Format & Grid", desc: "Ingestion Agent hashes files and registers sheets to a unified frame." },
  { n: 3, title: "Match & Check", desc: "Normalization + 8 deterministic checks; findings stream in." },
  { n: 4, title: "Review & Sign Off", desc: "Click any finding → zoom to its location. Export signed PDF." },
];

export function HowItWorks() {
  return (
    <section className="py-20 px-6">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-h2 font-bold mb-10 text-center">How it works</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {STEPS.map((s) => (
            <div key={s.n} className="border-l-4 border-accent pl-4">
              <p className="font-mono text-2xl text-accent mb-2">{s.n}</p>
              <h3 className="font-semibold mb-1">{s.title}</h3>
              <p className="text-sm text-text-muted">{s.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
