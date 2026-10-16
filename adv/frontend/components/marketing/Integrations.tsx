const INTS = [
  { logo: "Pc", name: "Procore", desc: "Push findings as RFIs" },
  { logo: "AC", name: "Autodesk CC", desc: "Pull drawings from project files" },
  { logo: "Bb", name: "Bluebeam", desc: "Push markup overlays to PDF" },
  { logo: "Sp", name: "SharePoint", desc: "File sync" },
  { logo: "Rv", name: "Revit / IFC", desc: "Model query for 3D clashes" },
  { logo: "Ol", name: "Outlook", desc: "Finding notifications" },
  { logo: "Tm", name: "Teams", desc: "Sign-off routing" },
  { logo: "Dr", name: "Google Drive", desc: "Cloud file sync" },
  { logo: "PB", name: "Power BI", desc: "Finding analytics" },
  { logo: "Eg", name: "Egnyte", desc: "Enterprise file sync" },
];

export function Integrations() {
  return (
    <section className="section" id="integrations">
      <div className="container">
        <div className="section-header reveal">
          <div className="section-label">10 / INTEGRATIONS</div>
          <h2>Fits the way your team already works.</h2>
        </div>

        <div className="int-grid reveal">
          {INTS.map((i) => (
            <div key={i.name} className="int-cell">
              <div className="int-logo">{i.logo}</div>
              <div className="name">{i.name}</div>
              <div className="desc">{i.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
