export function Capabilities() {
  return (
    <section className="section" id="capabilities">
      <div className="container">
        <div className="section-header reveal">
          <div className="section-label">05 / CAPABILITIES</div>
          <h2>Five capabilities built for engineering defensibility.</h2>
          <p className="lede">
            Not abstract AI. Specific, auditable capabilities that map to the things your
            reviewers actually check.
          </p>
        </div>

        {/* CAP 01 — NORMALIZATION */}
        <div className="capability reveal">
          <div className="cap-text">
            <div className="cap-eyebrow"><span className="num">01</span> SCHEMA</div>
            <h3>One canonical schema for every firm&apos;s drawing convention.</h3>
            <p className="lede">
              The Normalization Agent reads each drawing in its native style — Bechtel
              tags, Fluor section codes, EPC vendor conventions — and emits a single
              canonical JSON schema. Downstream rules never have to learn firm-specific formats.
            </p>
            <ul className="cap-list">
              <li>Support taxonomy: <em>restraint | anchor | guide | saddle</em></li>
              <li>Opening taxonomy: <em>duct | pipe | cable-tray | sleeve | trench</em></li>
              <li>Member taxonomy: <em>beam | column | brace | truss | joist</em></li>
              <li>Auto-detection of tag patterns: F11WE, TP4BM101, M-OP-203</li>
              <li>Sheet metadata: rev, drawn-by, scale, units</li>
            </ul>
          </div>
          <div className="cap-visual">
            <span className="cap-visual-tag">FIG 01 · SCHEMA</span>
            <div className="cap-visual-frame"></div>
            <pre style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--ink)", lineHeight: 1.7, whiteSpace: "pre-wrap", margin: 0 }}>
{`<span style="color: var(--cyan-deep);">{</span>
  <span style="color: var(--rust);">"support"</span>: <span style="color: var(--cyan-deep);">{</span>
    <span style="color: var(--rust);">"id"</span>:        <span style="color: var(--pass);">"SUP-042"</span>,
    <span style="color: var(--rust);">"type"</span>:      <span style="color: var(--pass);">"restraint"</span>,
    <span style="color: var(--rust);">"grid"</span>:      <span style="color: var(--pass);">"TP104-B/2"</span>,
    <span style="color: var(--rust);">"x_mm"</span>:      <span style="color: var(--pass);">4200</span>,
    <span style="color: var(--rust);">"y_mm"</span>:      <span style="color: var(--pass);">2800</span>,
    <span style="color: var(--rust);">"load_kg"</span>:   <span style="color: var(--pass);">850</span>,
    <span style="color: var(--rust);">"fluid"</span>:     <span style="color: var(--pass);">"chilled-water"</span>
  <span style="color: var(--cyan-deep);">}</span>,
  <span style="color: var(--rust);">"opening"</span>: <span style="color: var(--cyan-deep);">{</span>
    <span style="color: var(--rust);">"id"</span>:        <span style="color: var(--pass);">"OP-203"</span>,
    <span style="color: var(--rust);">"service"</span>:   <span style="color: var(--pass);">"duct"</span>,
    <span style="color: var(--rust);">"w_mm"</span>:      <span style="color: var(--pass);">300</span>,
    <span style="color: var(--rust);">"h_mm"</span>:      <span style="color: var(--pass);">200</span>,
    <span style="color: var(--rust);">"elev"</span>:      <span style="color: var(--pass);">"+13.150"</span>
  <span style="color: var(--cyan-deep);">}</span>
<span style="color: var(--cyan-deep);">}</span>`}
            </pre>
          </div>
        </div>

        {/* CAP 02 — OPENING VERIFICATION */}
        <div className="capability reverse reveal">
          <div className="cap-text">
            <div className="cap-eyebrow"><span className="num">02</span> OPENINGS</div>
            <h3>Every opening matched, sized, located, and elevation-checked.</h3>
            <p className="lede">
              Required openings from the Mechanical GA are matched to provided openings
              in the Structural GA using fuzzy ID + grid proximity. Each match is checked
              for size, position, and T.O.S. elevation alignment.
            </p>
            <ul className="cap-list">
              <li>Required-vs-provided inventory diff</li>
              <li>Per-axis size tolerance (width AND height)</li>
              <li>Euclidean position tolerance</li>
              <li>Elevation / T.O.S. alignment</li>
              <li>Sleeve vs trench vs opening detection</li>
              <li>Required-but-missing flag · Orphan-provided flag</li>
            </ul>
          </div>
          <div className="cap-visual">
            <span className="cap-visual-tag">FIG 02 · OPENING DIFF</span>
            <div className="cap-visual-frame"></div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: "8px", alignItems: "center", marginBottom: "12px" }}>
                <div style={{ background: "var(--paper)", border: "1px solid var(--rule-strong)", padding: "12px" }}>
                  <div style={{ color: "var(--ink-mute)", fontSize: "9px", letterSpacing: "0.16em", marginBottom: "6px" }}>REQUIRED · MECH GA</div>
                  <div style={{ color: "var(--ink)", fontWeight: 700 }}>OP-203 · DUCT</div>
                  <div style={{ color: "var(--ink-soft)", marginTop: "4px" }}>300 × 200 mm</div>
                  <div style={{ color: "var(--ink-soft)" }}>@ TP104-B/2</div>
                  <div style={{ color: "var(--ink-soft)" }}>elev +13.150m</div>
                </div>
                <div style={{ color: "var(--rust)", fontSize: "18px" }}>→</div>
                <div style={{ background: "var(--paper)", border: "1px solid var(--rule-strong)", padding: "12px" }}>
                  <div style={{ color: "var(--ink-mute)", fontSize: "9px", letterSpacing: "0.16em", marginBottom: "6px" }}>PROVIDED · STR GA</div>
                  <div style={{ color: "var(--ink)", fontWeight: 700 }}>TP4BM-OP203</div>
                  <div style={{ color: "var(--rust)", marginTop: "4px" }}>250 × 200 mm</div>
                  <div style={{ color: "var(--ink-soft)" }}>@ TP104-B/2</div>
                  <div style={{ color: "var(--rust)" }}>elev +13.350m</div>
                </div>
              </div>
              <div style={{ background: "var(--ink)", color: "var(--paper)", padding: "12px", fontSize: "10px", lineHeight: 1.6 }}>
                <div style={{ color: "var(--rust)", fontWeight: 700, marginBottom: "4px" }}>⚠ FLAGGED · 2 violations</div>
                <div>Δ width: <span style={{ color: "var(--rust)" }}>-50mm</span> (tol ±25mm)</div>
                <div>Δ elev: <span style={{ color: "var(--rust)" }}>+200mm</span> (tol ±50mm)</div>
              </div>
            </div>
          </div>
        </div>

        {/* CAP 03 — FUZZY ID MATCHING */}
        <div className="capability reveal">
          <div className="cap-text">
            <div className="cap-eyebrow"><span className="num">03</span> MATCHING</div>
            <h3>Fuzzy ID matching that handles inconsistent tagging.</h3>
            <p className="lede">
              Mech and Str drawings rarely share the same tag for the same physical item.
              The matching engine combines Levenshtein distance, semantic embeddings, and
              grid proximity to pair items correctly.
            </p>
            <ul className="cap-list">
              <li>Levenshtein-based fuzzy string match</li>
              <li>Sentence-transformer semantic similarity</li>
              <li>Grid-bubble proximity weighting</li>
              <li>Confidence-banded output (Pass / Verify / Manual)</li>
              <li>Reviewer override on every match</li>
            </ul>
          </div>
          <div className="cap-visual">
            <span className="cap-visual-tag">FIG 03 · MATCH SCORE</span>
            <div className="cap-visual-frame"></div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", lineHeight: 1.7 }}>
              {[
                { a: "F11WE", b: "TP4BM101", s: "0.89", c: "pass", l: "✓ MATCH" },
                { a: "M-OP-203", b: "OP203", s: "0.78", c: "amber", l: "⚠ VERIFY" },
                { a: "SUP-042", b: "?", s: "0.00", c: "rust", l: "✗ MISSING" },
              ].map((row, i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "auto auto auto auto 1fr", gap: "10px", alignItems: "center", padding: "10px", borderBottom: "1px dashed var(--rule-strong)" }}>
                  <span style={{ color: "var(--cyan-deep)" }}>{row.a}</span>
                  <span>↔</span>
                  <span style={{ color: "var(--cyan-deep)" }}>{row.b}</span>
                  <span style={{ color: `var(--${row.c})`, fontWeight: 700 }}>{row.s}</span>
                  <span style={{ color: `var(--${row.c})` }}>{row.l}</span>
                </div>
              ))}
              <div style={{ padding: "12px", background: "var(--paper-3)", marginTop: "8px", fontSize: "10px", color: "var(--ink-soft)" }}>
                score = 0.5·levenshtein + 0.3·semantic + 0.2·grid_proximity
              </div>
            </div>
          </div>
        </div>

        {/* CAP 04 — CLASH DETECTION */}
        <div className="capability reverse reveal">
          <div className="cap-text">
            <div className="cap-eyebrow"><span className="num">04</span> CLASH</div>
            <h3>Polygon-level clash with real clearance values.</h3>
            <p className="lede">
              Bounding boxes are too coarse. The clash engine converts every footprint and
              member into polygons (or extruded shapes for 3D), then computes true
              geometric intersection and clearance distance using Shapely.
            </p>
            <ul className="cap-list">
              <li>Polygon intersection — not bounding boxes</li>
              <li>Clearance zone violations (mm)</li>
              <li>Hard clash vs soft intrusion classification</li>
              <li>Multi-discipline overlays (Mech + Str + Arch + Plumbing)</li>
              <li>3D-ready (trimesh + IFC support)</li>
              <li>Beam-vs-opening conflict as first-class check</li>
            </ul>
          </div>
          <div className="cap-visual">
            <span className="cap-visual-tag">FIG 04 · CLASH GEOMETRY</span>
            <div className="cap-visual-frame"></div>
            <svg viewBox="0 0 360 220" style={{ width: "100%", height: "auto" }}>
              <defs>
                <pattern id="cap04grid" width="16" height="16" patternUnits="userSpaceOnUse">
                  <path d="M 16 0 L 0 0 0 16" fill="none" stroke="rgba(14,27,44,0.06)" strokeWidth="0.5" />
                </pattern>
              </defs>
              <rect width="360" height="220" fill="url(#cap04grid)" />
              <rect x="40" y="100" width="280" height="20" fill="rgba(30,136,168,0.18)" stroke="#1E88A8" strokeWidth="1.4" />
              <text x="180" y="113" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="9" fill="#0E1B2C">TP4BM203 · UB203×133×25</text>
              <rect x="120" y="60" width="140" height="80" fill="rgba(200,75,31,0.16)" stroke="#C84B1F" strokeWidth="1.4" strokeDasharray="4 3" />
              <text x="190" y="100" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="9" fill="#C84B1F" fontWeight="700">DUCT 300×200</text>
              <text x="190" y="112" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="7" fill="#C84B1F">REQ'D @ TP104-B/2</text>
              <circle cx="190" cy="110" r="8" fill="#C84B1F" />
              <text x="190" y="114" textAnchor="middle" fontFamily="JetBrains Mono" fontSize="11" fontWeight="700" fill="#F2EFE6">!</text>
              <line x1="190" y1="110" x2="290" y2="50" stroke="#C84B1F" strokeWidth="0.8" strokeDasharray="2 2" />
              <rect x="266" y="32" width="92" height="38" fill="#F2EFE6" stroke="#C84B1F" strokeWidth="0.8" />
              <text x="270" y="44" fontFamily="JetBrains Mono" fontSize="7" fill="#0E1B2C" fontWeight="700">HARD CLASH</text>
              <text x="270" y="54" fontFamily="JetBrains Mono" fontSize="6.5" fill="#5C6B82">overlap: 200×20 mm</text>
              <text x="270" y="64" fontFamily="JetBrains Mono" fontSize="6.5" fill="#C84B1F" fontWeight="700">distance: 0 mm</text>
              <g fontFamily="JetBrains Mono" fontSize="7">
                <rect x="20" y="20" width="8" height="8" fill="rgba(30,136,168,0.5)" />
                <text x="32" y="27" fill="#0E1B2C">STRUCTURAL</text>
                <rect x="100" y="20" width="8" height="8" fill="rgba(200,75,31,0.4)" />
                <text x="112" y="27" fill="#0E1B2C">MECH OPENING</text>
              </g>
              <text x="350" y="210" textAnchor="end" fontFamily="JetBrains Mono" fontSize="7" fill="#5C6B82">SHEET S-02 · GRID B/2</text>
            </svg>
          </div>
        </div>

        {/* CAP 05 — CLICK-TO-LOCATE */}
        <div className="capability reveal">
          <div className="cap-text">
            <div className="cap-eyebrow"><span className="num">05</span> LOCATABILITY</div>
            <h3>Every flagged item is one click from its drawing location.</h3>
            <p className="lede">
              Findings aren&apos;t abstract reports. Each card shows the sheet, grid, X-Y
              coords, and a click-to-zoom button. Reviewers jump from the inspector panel
              straight to the issue — no scrolling, no guessing.
            </p>
            <ul className="cap-list">
              <li>Sheet + grid + X-Y metadata per finding</li>
              <li>One-click zoom in the drawing viewer</li>
              <li>Highlighted overlay on the relevant geometry</li>
              <li>Side-by-side Mech vs Str view</li>
              <li>Annotation layer for reviewer comments</li>
              <li>Export to Word/PDF with embedded screenshots</li>
            </ul>
          </div>
          <div className="cap-visual">
            <span className="cap-visual-tag">FIG 05 · CLICK-TO-LOCATE</span>
            <div className="cap-visual-frame"></div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", background: "var(--paper)", border: "1px solid var(--rule-strong)", padding: "16px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "9px", letterSpacing: "0.16em", color: "var(--ink-mute)", textTransform: "uppercase", marginBottom: "12px", paddingBottom: "8px", borderBottom: "1px solid var(--rule)" }}>
                <span>FINDING F-01 · CLASH</span>
                <span style={{ color: "var(--rust)" }}>⚠ FLAGGED</span>
              </div>
              <div style={{ marginBottom: "10px" }}>
                <span style={{ color: "var(--ink-mute)", fontSize: "9px", letterSpacing: "0.14em" }}>SHEET</span><br />
                <span style={{ color: "var(--ink)", fontWeight: 700 }}>S-01 · TP104 · LVL +13.150m · REV-C</span>
              </div>
              <div style={{ marginBottom: "10px" }}>
                <span style={{ color: "var(--ink-mute)", fontSize: "9px", letterSpacing: "0.14em" }}>GRID</span><br />
                <span style={{ color: "var(--ink)", fontWeight: 700 }}>TP104-B / 2</span>
              </div>
              <div style={{ marginBottom: "10px" }}>
                <span style={{ color: "var(--ink-mute)", fontSize: "9px", letterSpacing: "0.14em" }}>COORDS</span><br />
                <span style={{ color: "var(--ink)" }}>x = 4200 mm, y = 2800 mm</span>
              </div>
              <div style={{ marginBottom: "14px" }}>
                <span style={{ color: "var(--ink-mute)", fontSize: "9px", letterSpacing: "0.14em" }}>RULE</span><br />
                <span style={{ color: "var(--ink)" }}>polygon.intersects() == TRUE</span>
              </div>
              <button style={{ width: "100%", background: "var(--ink)", color: "var(--paper)", padding: "10px", fontFamily: "var(--font-mono)", fontSize: "11px", letterSpacing: "0.1em", fontWeight: 600 }}>→ JUMP TO LOCATION ON DRAWING</button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
