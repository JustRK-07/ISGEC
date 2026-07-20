const QUOTES = [
  { quote: "We used to spend 3 days per drawing set on cross-discipline reviews. Now it's 30 minutes — and we catch more.", author: "Senior Structural Engineer, EPC firm" },
  { quote: "The click-to-locate feature alone changed how we run reviews. Every flagged item is a one-click zoom.", author: "QA/QC Lead, M&E consultant" },
  { quote: "Every finding shows the exact formula and the exact number. That's the only kind of evidence our sign-off process accepts.", author: "Chief Engineer, data center developer" },
];

export function Testimonials() {
  return (
    <section className="py-20 px-6">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-h2 font-bold mb-10">What engineers say</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {QUOTES.map((q) => (
            <figure key={q.author} className="qa-stamp p-6 bg-white">
              <blockquote className="text-sm mb-4">“{q.quote}”</blockquote>
              <figcaption className="text-xs text-text-muted font-mono">— {q.author}</figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}
