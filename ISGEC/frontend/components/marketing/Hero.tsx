export function Hero() {
  return (
    <header className="hero">
      <div className="hero-inner">
        <div className="hero-text">
          <div className="eyebrow">QA/QC · DWG-Native · On-Prem · Local LLM · Agentic AI</div>
          <h1>
            Catch the clashes your Mechanical &amp; Structural GA reviews{" "}
            <span className="accent">miss</span>.
          </h1>
          <p className="sub">
            An agentic AI platform that reads native DWG files and validates every
            support, opening, and penetration across disciplines — grounding every
            finding to a sheet, a gridline, and an exact numeric difference.{" "}
            <strong>
              100% on-prem. Self-hosted local LLM. Zero third-party API calls —
              your drawings never leave your infrastructure.
            </strong>
          </p>
          <div className="hero-ctas">
            <a href="#cta" className="btn btn-primary">Upload a DWG · Free Check →</a>
            <a href="#cta" className="btn btn-secondary">Book a 20-min Demo</a>
          </div>
        </div>

        <div className="viewer" aria-label="Live drawing inspection viewer mockup">
          <div className="viewer-header">
            <div className="viewer-title">
              <span className="stamp">QA/QC</span>
              <span>TP-104 · LVL +13.150m · REV-C</span>
            </div>
            <div className="viewer-meta">
              <span className="ok">✓ 47 PASS</span>
              <span style={{ color: "var(--rust)" }}>⚠ 03 FLAGGED</span>
            </div>
          </div>
          <div className="viewer-body">
            <div className="viewer-canvas">
              <svg viewBox="0 0 480 360" xmlns="http://www.w3.org/2000/svg" aria-label="Drawing clash detection example">
                <defs>
                  <pattern id="heroGrid" width="24" height="24" patternUnits="userSpaceOnUse">
                    <path d="M 24 0 L 0 0 0 24" fill="none" stroke="rgba(14,27,44,0.07)" strokeWidth="0.5" />
                  </pattern>
                </defs>
                <rect width="480" height="360" fill="url(#heroGrid)" />
                <g fontFamily="JetBrains Mono" fontSize="9" fill="#5C6B82">
                  <text x="6" y="14">A</text><text x="158" y="14">B</text>
                  <text x="310" y="14">C</text><text x="430" y="14">D</text>
                  <text x="6" y="180">1</text><text x="466" y="180">2</text>
                  <text x="6" y="346">3</text><text x="466" y="346">FUTURE</text>
                </g>
                <g stroke="#0E1B2C" strokeWidth="0.7" fill="none">
                  <rect x="38" y="32" width="22" height="22" />
                  <rect x="190" y="32" width="22" height="22" />
                  <rect x="342" y="32" width="22" height="22" />
                  <rect x="38" y="306" width="22" height="22" />
                  <rect x="190" y="306" width="22" height="22" />
                  <rect x="342" y="306" width="22" height="22" />
                </g>
                <g stroke="#1E88A8" strokeWidth="2.2" fill="none" opacity="0.85">
                  <line x1="38" y1="55" x2="468" y2="55" />
                  <line x1="38" y1="180" x2="468" y2="180" />
                  <line x1="38" y1="305" x2="468" y2="305" />
                  <line x1="49" y1="32" x2="49" y2="328" />
                  <line x1="201" y1="32" x2="201" y2="328" />
                  <line x1="353" y1="32" x2="353" y2="328" />
                </g>
                <g stroke="#1E88A8" strokeWidth="0.9" fill="none" opacity="0.55">
                  <line x1="49" y1="180" x2="201" y2="180" />
                  <line x1="201" y1="55" x2="201" y2="180" />
                  <line x1="201" y1="180" x2="353" y2="180" />
                </g>
                <g>
                  <rect x="170" y="100" width="120" height="36" fill="rgba(200,75,31,0.12)" stroke="#C84B1F" strokeWidth="1.6" strokeDasharray="3 2" />
                  <text x="178" y="118" fontFamily="JetBrains Mono" fontSize="8" fill="#C84B1F" fontWeight="700">DUCT 300×200</text>
                  <text x="178" y="128" fontFamily="JetBrains Mono" fontSize="7" fill="#C84B1F">REQ'D @ TP104-B/2</text>
                </g>
                <g>
                  <circle cx="220" cy="180" r="9" fill="#C84B1F" />
                  <text x="220" y="184" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="11" fontWeight="700" fill="#F2EFE6">!</text>
                  <line x1="220" y1="180" x2="320" y2="220" stroke="#C84B1F" strokeWidth="0.8" strokeDasharray="2 2" />
                  <rect x="320" y="208" width="138" height="34" fill="#F2EFE6" stroke="#C84B1F" strokeWidth="0.8" />
                  <text x="324" y="220" fontFamily="JetBrains Mono" fontSize="7" fill="#0E1B2C" fontWeight="700">⚠ HARD CLASH</text>
                  <text x="324" y="230" fontFamily="JetBrains Mono" fontSize="6.5" fill="#5C6B82">duct ↔ beam @ TP104-B/2</text>
                  <text x="324" y="239" fontFamily="JetBrains Mono" fontSize="6.5" fill="#C84B1F" fontWeight="700">+50mm elevation</text>
                </g>
                <g>
                  <rect x="68" y="200" width="40" height="40" fill="rgba(47,122,77,0.1)" stroke="#2F7A4D" strokeWidth="1" />
                  <text x="71" y="223" fontFamily="JetBrains Mono" fontSize="7" fill="#2F7A4D">EQP-A1</text>
                </g>
                <g fontFamily="JetBrains Mono" fontSize="7" fill="#5C6B82">
                  <line x1="49" y1="14" x2="201" y2="14" stroke="#5C6B82" strokeWidth="0.5" />
                  <text x="118" y="10" textAnchor="middle">5500</text>
                  <line x1="201" y1="14" x2="353" y2="14" stroke="#5C6B82" strokeWidth="0.5" />
                  <text x="270" y="10" textAnchor="middle">8500</text>
                </g>
                <text x="470" y="354" textAnchor="end" fontFamily="JetBrains Mono" fontSize="7" fill="#1E88A8">SHEET S-01 · GRID B/2 · LVL +13.150m</text>
              </svg>
            </div>
            <aside className="viewer-rail" aria-label="Findings rail">
              <div className="viewer-rail-head">FINDINGS · 03 FLAGGED</div>
              <div className="finding">
                <div className="finding-id">F-01 · CLASH</div>
                <div className="finding-grid">TP104-B / 2 · LVL +13.150m</div>
                <div className="finding-text">Duct 300×200 ↔ primary beam</div>
                <div className="finding-diff">Δ +50mm elevation</div>
              </div>
              <div className="finding soft">
                <div className="finding-id">F-02 · OPENING</div>
                <div className="finding-grid">TP104-B / 2 · LVL +13.150m</div>
                <div className="finding-text">Required 300×200, provided 250×200</div>
                <div className="finding-diff" style={{ color: "var(--amber)" }}>Δ -50mm width</div>
              </div>
              <div className="finding">
                <div className="finding-id">F-03 · SUPPORT</div>
                <div className="finding-grid">TP104-C / 2 · LVL +13.150m</div>
                <div className="finding-text">Restraint required, none on Str GA</div>
                <div className="finding-diff">MISSING</div>
              </div>
              <div className="finding pass">
                <div className="finding-id">F-04 · OPENING ✓</div>
                <div className="finding-grid">TP104-A / 1 · LVL +13.150m</div>
                <div className="finding-text">Required ↔ provided match</div>
                <div className="finding-diff" style={{ color: "var(--pass)" }}>PASS</div>
              </div>
            </aside>
          </div>
        </div>
      </div>
    </header>
  );
}
