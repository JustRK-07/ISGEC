export function UseCases() {
  return (
    <section className="section" id="usecases">
      <div className="container">
        <div className="section-header reveal">
          <div className="section-label">12 / USE CASES</div>
          <h2>Three workflows out of the box.</h2>
        </div>

        <div className="use-grid reveal">
          <article className="use-card">
            <div className="use-tag">USE CASE 01</div>
            <h4>Mechanical GA ↔ Structural GA</h4>
            <p>
              The headline use case. Validate supports, openings, penetrations, and
              elevations between disciplines in a single pass.
            </p>
            <div className="use-example">
              <strong>EXAMPLE</strong><br />
              Mech: 300×200 duct @ TP104-B/2, elev +13.150m<br />
              Str: 250×200 opening @ TP104-B/2, elev +13.350m<br />
              <span className="fail">→ BOTH FAIL TOLERANCE · FLAGGED</span>
            </div>
          </article>
          <article className="use-card">
            <div className="use-tag">USE CASE 02</div>
            <h4>Revision Comparison</h4>
            <p>
              Upload Rev A and Rev C of the Structural GA. Get a structural diff: which
              beams moved, which openings changed, which supports were added or removed.
            </p>
            <div className="use-example">
              <strong>DIFF · REV-A → REV-C</strong><br />
              +2 beams added (TP104-B/2, TP104-B/3)<br />
              -1 support removed (SUP-042)<br />
              ±0 openings changed
            </div>
          </article>
          <article className="use-card">
            <div className="use-tag">USE CASE 03</div>
            <h4>Multi-Discipline Clash Overlay</h4>
            <p>
              Upload Mech + Str + Plumbing + Fire Protection. Get a unified superimposed
              view with all clashes color-coded by severity.
            </p>
            <div className="use-example">
              <strong>OVERLAY · 4 DISCIPLINES</strong><br />
              3 hard clashes (red)<br />
              7 soft intrusions (amber)<br />
              142 pass (green)
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}
