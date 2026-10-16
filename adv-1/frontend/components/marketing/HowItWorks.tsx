export function HowItWorks() {
  return (
    <section className="section section-narrow" id="how">
      <div className="container">
        <div className="section-header reveal">
          <div className="section-label">06 / HOW IT WORKS</div>
          <h2>From upload to signed report in 5–15 minutes.</h2>
        </div>

        <div className="how-rail reveal">
          <div className="how-step">
            <div className="how-step-num"><span>01</span>STEP</div>
            <h4>Upload Drawings</h4>
            <p>Drop in Mechanical GA, Structural GA, and (optional) Superimposed as native DWG files. DXF, IFC, and RVT also supported.</p>
          </div>
          <div className="how-step">
            <div className="how-step-num"><span>02</span>STEP</div>
            <h4>Detect &amp; Register</h4>
            <p>The Ingestion Agent hashes files, detects vector vs raster, and registers each sheet to a unified coordinate frame using grid bubbles.</p>
          </div>
          <div className="how-step">
            <div className="how-step-num"><span>03</span>STEP</div>
            <h4>Match &amp; Check</h4>
            <p>The Normalization Agent builds canonical element lists. The Rule Engine runs 8 deterministic checks. Findings stream into the inspector panel.</p>
          </div>
          <div className="how-step">
            <div className="how-step-num"><span>04</span>STEP</div>
            <h4>Sign Off</h4>
            <p>Click any finding to jump to its location. Approve, override, or comment. Export a signed PDF report with full audit trail.</p>
          </div>
        </div>
      </div>
    </section>
  );
}
