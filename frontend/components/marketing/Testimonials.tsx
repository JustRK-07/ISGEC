const QUOTES = [
  { quote: "We used to spend three days per drawing set on cross-discipline reviews. Now it's thirty minutes — and we catch more.", author: "Senior Structural Engineer", role: "EPC firm · Industrial" },
  { quote: "The click-to-locate feature alone changed how we run reviews. Every flagged item is a one-click zoom on the drawing.", author: "QA/QC Lead", role: "M&E consultant · Healthcare" },
  { quote: "Every finding shows the exact formula and the exact number. That's the only kind of evidence our sign-off process accepts.", author: "Chief Engineer", role: "Data center developer" },
];

export function Testimonials() {
  return (
    <section className="section" id="testimonials">
      <div className="container">
        <div className="section-header reveal">
          <div className="section-label">15 / TESTIMONIALS</div>
          <h2>What engineering teams say.</h2>
        </div>

        <div className="test-grid reveal">
          {QUOTES.map((q) => (
            <article key={q.author} className="test-card">
              <span className="test-stamp">REVIEW · PASSED</span>
              <blockquote>&ldquo;{q.quote}&rdquo;</blockquote>
              <div className="test-meta">
                <strong>{q.author}</strong>
                {q.role}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
