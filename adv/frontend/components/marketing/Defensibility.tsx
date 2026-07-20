export function Defensibility() {
  return (
    <section className="py-20 px-6 bg-bg-dark text-white">
      <div className="max-w-4xl mx-auto text-center">
        <h2 className="text-h2 font-bold mb-6">
          Every finding traces back to a sheet, a gridline, an element, and a formula.
        </h2>
        <div className="grid md:grid-cols-3 gap-6 mt-10">
          <div className="border border-text-muted/30 rounded p-6">
            <p className="font-mono text-eyebrow uppercase text-accent mb-3">Sheet</p>
            <p className="text-sm">Every finding cites SHEET-S02 (or M-01, REV-C).</p>
          </div>
          <div className="border border-text-muted/30 rounded p-6">
            <p className="font-mono text-eyebrow uppercase text-accent mb-3">Grid</p>
            <p className="text-sm">Every finding cites the grid intersection, e.g., GRID TP104-B/2.</p>
          </div>
          <div className="border border-text-muted/30 rounded p-6">
            <p className="font-mono text-eyebrow uppercase text-accent mb-3">Formula</p>
            <p className="text-sm">Every finding shows the exact rule and the numeric result.</p>
          </div>
        </div>
        <p className="mt-10 text-text-muted">
          No confidence percentages. No black boxes. If a reviewer asks <em>why was this flagged</em>, the answer is one click away.
        </p>
      </div>
    </section>
  );
}
