const FORMATS = [
  { name: "DWG", path: "ODA + ezdxf", use: "Native AutoCAD authoring — full entity access" },
  { name: "DXF", path: "ezdxf direct", use: "AutoCAD export — text-readable" },
  { name: "IFC", path: "ifcopenshell", use: "BIM model export for 3D validation" },
  { name: "RVT", path: "Forge / Revit API", use: "Direct Revit model query" },
  { name: "DWG → PDF", path: "PyMuPDF", use: "Reference only — falls through to vision path" },
  { name: "Scanned", path: "Local multimodal LLM + Tesseract", use: "Legacy paper archives — fully on-prem" },
];

export function SupportedFormats() {
  return (
    <section className="py-20 px-6">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-h2 font-bold mb-3">Supported formats</h2>
        <p className="text-text-muted mb-10">DWG is primary. Reading DWG natively preserves layer structure, blocks, line types, and real-world mm coordinates.</p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {FORMATS.map((f) => (
            <div key={f.name} className="border border-border rounded p-5">
              <p className="font-mono text-eyebrow uppercase text-accent mb-2">{f.name}</p>
              <p className="text-xs text-text-muted mb-2 font-mono">{f.path}</p>
              <p className="text-sm">{f.use}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
