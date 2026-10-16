const COLS = [
  { h: "[ STRUCTURAL ]", items: [
    ["ACI 318", "Concrete"],
    ["AISC 360", "Steel"],
    ["IS 800", "Indian Steel"],
    ["Eurocode 3", "European Steel"],
    ["AISI S100", "Cold-formed"],
  ]},
  { h: "[ LOAD & GENERAL ]", items: [
    ["ASCE 7", "Min. Design Loads"],
    ["IS 875", "Indian Loads"],
    ["Eurocode 1", "European Loads"],
    ["AS/NZS 1170", "Australia/NZ"],
    ["GB 50009", "Chinese Loads"],
  ]},
  { h: "[ SEISMIC ]", items: [
    ["IBC Ch.16", "US Building"],
    ["IBC Ch.18", "Soils & Found."],
    ["IBC Ch.19", "Concrete"],
    ["ASCE 7-16", "Seismic"],
    ["IS 1893", "Indian Seismic"],
  ]},
  { h: "[ BUILDING CODE ]", items: [
    ["IBC", "Int'l Building"],
    ["CBC", "California"],
    ["NFPA", "Fire / Life Safety"],
    ["IMC", "Mechanical"],
    ["IPC", "Plumbing"],
  ]},
];

export function Standards() {
  return (
    <section className="section" id="codes">
      <div className="container">
        <div className="section-header reveal">
          <div className="section-label">13 / STANDARDS LIBRARY</div>
          <h2>Every rule cites its standard.</h2>
          <p className="lede">
            When the system flags a tolerance violation, it cites the standard it&apos;s
            enforcing against.
          </p>
        </div>

        <div className="codes-grid reveal">
          {COLS.map((col) => (
            <div key={col.h} className="code-col">
              <h4>{col.h}</h4>
              <ul className="code-list">
                {col.items.map(([code, desc]) => (
                  <li key={code}><strong>{code}</strong><span>{desc}</span></li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="code-note">
          [ NOTE ] Custom rules can be added via the Prompt Lab — no code required. Encode
          any client-specific tolerance or jurisdiction-specific standard in plain English.
        </div>
      </div>
    </section>
  );
}
