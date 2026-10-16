export function Defensibility() {
  return (
    <section className="defensibility" id="defensibility">
      <div className="section-label">08 / DEFENSIBILITY</div>
      <h2>
        Every finding traces back to a <em>sheet</em>, a <em>gridline</em>, an{" "}
        <em>element</em>, and a <em>formula</em>.
      </h2>

      <div className="def-grid">
        <div className="def-cell">
          <div className="def-icon">[ SHEET ]</div>
          <h4>Sheet-located</h4>
          <p>Every finding cites SHEET-S02, M-01, or REV-C. Jump directly from the report to the exact drawing sheet.</p>
        </div>
        <div className="def-cell">
          <div className="def-icon">[ GRID ]</div>
          <h4>Grid-anchored</h4>
          <p>Every finding cites the grid intersection, e.g. GRID TP104-B / 2. No &quot;somewhere on the drawing.&quot;</p>
        </div>
        <div className="def-cell">
          <div className="def-icon">[ FORMULA ]</div>
          <h4>Formula-grounded</h4>
          <p>Every finding shows the exact rule applied and the numeric result. Auditable. Defensible. Sign-off ready.</p>
        </div>
      </div>

      <p className="def-closer">
        [ No confidence percentages. No black boxes. If a reviewer asks &quot;why was this flagged&quot;, the answer is one click away. ]
      </p>
    </section>
  );
}
