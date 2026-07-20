const CASES = [
  {
    title: "Mechanical GA ↔ Structural GA",
    body: "Mech requires 300×200 duct at TP104-B/2 elevation +13.150m. Str provides 250×200 at +13.350m. Both fail tolerance → flagged.",
  },
  {
    title: "Revision Comparison",
    body: "Upload Rev A and Rev C of the Str GA. Get a structural diff: which beams moved, which openings changed.",
  },
  {
    title: "Multi-Discipline Clash Overlay",
    body: "Upload Mech + Str + Plumbing + Fire Protection. Unified superimposed view with clashes color-coded by severity.",
  },
];

export function UseCases() {
  return (
    <section className="py-20 px-6 bg-white">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-h2 font-bold mb-10">Use cases</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {CASES.map((c) => (
            <div key={c.title} className="border border-border rounded p-5">
              <h3 className="font-semibold mb-3">{c.title}</h3>
              <p className="text-sm text-text-muted">{c.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
