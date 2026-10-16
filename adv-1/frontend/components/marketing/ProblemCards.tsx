export function ProblemCards() {
  return (
    <section className="section" id="problem">
      <div className="container">
        <div className="section-header reveal">
          <div className="section-label">03 / PROBLEM</div>
          <h2>Manual cross-discipline reviews miss the things that cost the most.</h2>
          <p className="lede">
            Mechanical, structural, and superimposed drawings all describe the same
            physical space — but they&apos;re authored by different teams using different
            conventions. Errors slip through. Always have.
          </p>
        </div>

        <div className="problem-grid reveal">
          <article className="problem-card">
            <div className="problem-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                <rect x="3" y="9" width="18" height="6" /><circle cx="8" cy="12" r="1" /><circle cx="16" cy="12" r="1" />
              </svg>
            </div>
            <div className="problem-tag">PROBLEM 01</div>
            <h3>Missed Supports</h3>
            <p>Mechanical GA requires a support at TP104-B/2; Structural GA doesn&apos;t show it.</p>
            <div className="consequence">→ Equipment sags. Vibration. Premature failure.</div>
          </article>
          <article className="problem-card">
            <div className="problem-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                <rect x="3" y="3" width="18" height="18" /><path d="M3 12h18M12 3v18" />
              </svg>
            </div>
            <div className="problem-tag">PROBLEM 02</div>
            <h3>Wrong-Sized Openings</h3>
            <p>Required 300×200 duct opening. Provided 250×200.</p>
            <div className="consequence">→ Field rework. Cost overruns. Schedule slip.</div>
          </article>
          <article className="problem-card">
            <div className="problem-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                <circle cx="9" cy="9" r="6" /><circle cx="15" cy="15" r="6" />
              </svg>
            </div>
            <div className="problem-tag">PROBLEM 03</div>
            <h3>Undetected Clashes</h3>
            <p>A required opening falls directly on a primary beam.</p>
            <div className="consequence">→ Demo. Rebar redesign. RFI cascade.</div>
          </article>
          <article className="problem-card">
            <div className="problem-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
                <path d="M4 12h16M4 8h16M4 16h16" /><text x="12" y="13" textAnchor="middle" fontSize="6" fill="currentColor" stroke="none">±</text>
              </svg>
            </div>
            <div className="problem-tag">PROBLEM 04</div>
            <h3>Tolerance Drift</h3>
            <p>Position off by 60 mm when only ±25 mm is permitted.</p>
            <div className="consequence">→ Misalignment cascades through the system.</div>
          </article>
        </div>

        <p className="problem-closer">
          [ Today these checks are manual, slow, inconsistent across reviewers, and easy to skip under deadline pressure. ]
        </p>
      </div>
    </section>
  );
}
