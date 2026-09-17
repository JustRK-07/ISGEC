export function Pipeline() {
  return (
    <section className="section section-narrow" id="architecture">
      <div className="container">
        <div className="section-header reveal">
          <div className="section-label">04 / ARCHITECTURE</div>
          <h2>Five specialized layers. One deterministic answer.</h2>
          <p className="lede">
            Each drawing flows through five coordinated agents. Reading is probabilistic.
            Checking is exact. Findings are auditable.
          </p>
        </div>

        <div className="pipeline-layer0 reveal">
          <span className="ll0-tag">L0</span>
          <span>
            <strong>Revision Lock</strong> — every file is hashed, every revision is ledgered.
            The system always validates against the right baseline.
          </span>
        </div>

        <div className="pipeline reveal">
          <div className="pipeline-stage">
            <div className="pipeline-num"><strong>L1</strong>DWG → DXF &amp; ENTITY EXTRACT</div>
            <h4>Authoring-format native</h4>
            <p>Convert DWG to DXF, then read every entity — lines, polylines, text, blocks, layers, hatches.</p>
            <div className="pipeline-tech">ezdxf (pure Python)<br />ODA File Converter (DWG → DXF)</div>
            <span className="pipeline-arrow">→</span>
          </div>
          <div className="pipeline-stage">
            <div className="pipeline-num"><strong>L2</strong>GRID &amp; COORDINATE REGISTRATION</div>
            <h4>Real-world units, one frame</h4>
            <p>Detect grid bubble labels. DWG already stores mm — no scale guess. Build unified coordinate frame.</p>
            <div className="pipeline-tech">Grid-line group extraction<br />Layer-based convention detect</div>
            <span className="pipeline-arrow">→</span>
          </div>
          <div className="pipeline-stage">
            <div className="pipeline-num"><strong>L3</strong>SEMANTIC NORMALIZATION (AGENT)</div>
            <h4>Firm-native → canonical</h4>
            <p>AI agent reads each drawing in its native style and emits a canonical JSON schema.</p>
            <div className="pipeline-tech">Local LLM · tool calling<br />Self-hosted · JSON-schema enforced</div>
            <span className="pipeline-arrow">→</span>
          </div>
          <div className="pipeline-stage">
            <div className="pipeline-num"><strong>L4</strong>RULE ENGINE (DETERMINISTIC)</div>
            <h4>Eight exact checks</h4>
            <p>Distance, size, clash, clearance, elevation, ID match, missing, orphaned — all exact math.</p>
            <div className="pipeline-tech">Shapely · NumPy · RapidFuzz<br />sentence-transformers</div>
            <span className="pipeline-arrow">→</span>
          </div>
          <div className="pipeline-stage">
            <div className="pipeline-num"><strong>L5</strong>REPORTING &amp; SIGN-OFF</div>
            <h4>Sheet-locatable findings</h4>
            <p>Each finding cites sheet, grid, X-Y coords, exact diff, and the rule applied. Reviewer sign-off loop.</p>
            <div className="pipeline-tech">React + deck.gl viewer<br />python-docx · reportlab · audit ledger</div>
          </div>
        </div>
      </div>
    </section>
  );
}
