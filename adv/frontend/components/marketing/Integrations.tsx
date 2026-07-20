const INTEGRATIONS = [
  "Procore", "Autodesk Construction Cloud", "Bluebeam", "SharePoint / Drive",
  "Revit / IFC", "Outlook / Teams", "Power BI / Tableau",
];

export function Integrations() {
  return (
    <section className="py-20 px-6 bg-white">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-h2 font-bold mb-10">Integrations</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {INTEGRATIONS.map((i) => (
            <div key={i} className="border border-border rounded h-24 flex items-center justify-center text-text-muted font-mono text-sm">
              {i}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
