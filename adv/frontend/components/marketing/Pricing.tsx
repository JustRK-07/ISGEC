const TIERS = [
  { name: "Starter", price: "Free first check", features: ["1 project, 5 sheets", "Standard support", "Vector + scanned"], featured: false },
  { name: "Professional", price: "$X / project", features: ["Unlimited projects + sheets", "Priority support + Slack", "+ Revision comparison"], featured: true },
  { name: "Enterprise", price: "Custom", features: ["Unlimited + on-prem + SSO", "Dedicated CSM + SLA", "+ Custom rules + private deploy"], featured: false },
];

export function Pricing() {
  return (
    <section className="py-20 px-6 bg-white">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-h2 font-bold mb-10 text-center">Pricing</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {TIERS.map((t) => (
            <div
              key={t.name}
              className={`border rounded p-6 ${
                t.featured ? "border-accent ring-2 ring-accent" : "border-border"
              }`}
            >
              <h3 className="font-semibold mb-2">{t.name}</h3>
              <p className="text-2xl font-bold mb-4">{t.price}</p>
              <ul className="space-y-2 text-sm text-text-muted">
                {t.features.map((f) => (
                  <li key={f}>• {f}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
