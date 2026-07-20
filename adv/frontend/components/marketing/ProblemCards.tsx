const CARDS = [
  { icon: "⚓", title: "Missed Supports", problem: "Mech requires support at TP104-B/2; Str omits it.", consequence: "Equipment sags, vibration, premature failure." },
  { icon: "📏", title: "Wrong-Sized Openings", problem: "Required 300×200 duct; provided 250×200.", consequence: "Field rework, cost overruns, schedule slip." },
  { icon: "💥", title: "Undetected Clashes", problem: "Required opening falls on a primary beam.", consequence: "Demo, rebar redesign, RFI cascade." },
  { icon: "±", title: "Tolerance Drift", problem: "Off by 60 mm when ±25 mm is permitted.", consequence: "Misalignment cascades through the whole system." },
];

export function ProblemCards() {
  return (
    <section className="py-20 px-6 bg-white">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-h2 font-bold mb-10 text-center">What slips past manual review</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {CARDS.map((c) => (
            <div key={c.title} className="border border-border rounded p-5">
              <div className="text-3xl mb-3">{c.icon}</div>
              <h3 className="font-semibold mb-2">{c.title}</h3>
              <p className="text-sm text-text-muted mb-2">{c.problem}</p>
              <p className="text-xs text-clash-hard">{c.consequence}</p>
            </div>
          ))}
        </div>
        <p className="text-center text-text-muted mt-10">
          Today these checks are manual, slow, inconsistent across reviewers, and easy to skip under deadline pressure.
        </p>
      </div>
    </section>
  );
}
