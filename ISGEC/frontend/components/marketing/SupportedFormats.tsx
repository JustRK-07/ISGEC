const FORMATS = [
  { name: "DWG", path: "PRIMARY", use: "Native AutoCAD. Layers, blocks, line types preserved.", style: "background: rgba(30, 136, 168, 0.06);" },
  { name: "DXF", path: "DIRECT READ", use: "Text format. ezdxf reads it without conversion." },
  { name: "IFC", path: "3D VALIDATION", use: "BIM model export for 3D clash." },
  { name: "RVT", path: "REVIT QUERY", use: "Direct Revit model query." },
  { name: "DWG → PDF", path: "REFERENCE ONLY", use: "Generated PDF for visual reference." },
  { name: "S–PDF", path: "SECONDARY", use: "Vision + OCR — for paper-only archives." },
];

export function SupportedFormats() {
  return (
    <section className="section" id="formats">
      <div className="container">
        <div className="section-header reveal">
          <div className="section-label">09 / FORMATS</div>
          <h2>DWG-native. The authoring format engineers actually draft in.</h2>
          <p className="lede">
            DWG carries layers, blocks, line types, and real-world mm coordinates — information
            that gets flattened or lost in any raster export. We read it directly.
          </p>
        </div>

        <div className="formats reveal">
          {FORMATS.map((f) => (
            <div key={f.name} className="format-cell" style={f.style ? { background: "rgba(30, 136, 168, 0.06)" } : undefined}>
              <div className="format-icon">{f.name}</div>
              <h4>{f.name}</h4>
              <div className="path">{f.path}</div>
              <p>{f.use}</p>
            </div>
          ))}
        </div>

        <div className="format-path-explainer reveal">
          <div className="format-path fast">
            <div className="format-path-head">▶ PRIMARY PATH · DWG-NATIVE</div>
            <h4>Layers, blocks, and real-world units.</h4>
            <p>
              DWG files are converted to DXF (text format) via the free ODA File Converter,
              then parsed by ezdxf in pure Python. We read every entity — lines, polylines,
              text, hatches, blocks, dimensions — with its layer, color, and line type intact.
              Coordinates are already in millimeters.
            </p>
          </div>
          <div className="format-path vision">
            <div className="format-path-head">▶ SECONDARY PATH · LEGACY SCANS</div>
            <h4>AI reads what humans read.</h4>
            <p>
              For paper-only legacy archives, scanned sheets go through a{" "}
              <strong>local multimodal LLM</strong> with Tesseract OCR fallback. The agent
              reads tags, dimensions, and symbols — and produces the same canonical JSON
              schema as the DWG path. All inference runs on-prem.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
