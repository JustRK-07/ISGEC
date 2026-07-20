export function Hero() {
  return (
    <section className="relative blueprint-grid py-24 px-6">
      <div className="max-w-5xl mx-auto text-center">
        <p className="font-mono text-eyebrow uppercase text-text-muted mb-4">
          QA/QC · DWG-Native · On-Prem · Local LLM · Agentic AI
        </p>
        <h1 className="text-h1 font-bold leading-tight mb-6">
          Catch the clashes your Mechanical and Structural GA reviews miss.
        </h1>
        <p className="text-lg text-text-muted max-w-3xl mx-auto mb-8">
          An agentic AI platform that reads native DWG files and validates every support,
          opening, and penetration across disciplines — grounding every finding to a sheet,
          a gridline, and an exact numeric difference. 100% on-prem. Self-hosted local LLM.
          Zero third-party API calls.
        </p>
        <div className="flex gap-3 justify-center">
          <a
            href="/upload"
            className="bg-accent hover:bg-accent-hover text-white font-medium px-6 py-3 rounded"
          >
            Upload a DWG · Free First Check
          </a>
          <a
            href="#contact"
            className="border border-border hover:border-accent text-text-primary font-medium px-6 py-3 rounded"
          >
            Book a 20-min Demo
          </a>
        </div>
      </div>
    </section>
  );
}
