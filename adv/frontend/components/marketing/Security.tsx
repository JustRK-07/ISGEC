export function Security() {
  return (
    <section className="py-20 px-6">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-h2 font-bold mb-10">Security & compliance</h2>
        <div className="grid md:grid-cols-3 gap-4 mb-10">
          <Card title="Enterprise Security" body="SOC 2 Type II, AES-256 at rest, TLS 1.3 in transit." />
          <Card title="Private Cloud / On-Prem" body="VPC deployment or full on-prem for restricted projects." />
          <Card title="Role-Based Access" body="Engineer · Reviewer · Admin · Super Admin + SSO/SAML." />
        </div>
        <div className="border-2 border-accent rounded p-6 bg-accent/5">
          <p className="font-mono text-eyebrow uppercase text-accent mb-2">Zero third-party API</p>
          <p className="text-sm">
            No drawing data ever leaves your infrastructure. All LLM inference runs locally on your
            hardware — Ollama, vLLM, or llama.cpp serving an open-weight model. No tokens, no rate
            limits, no API keys, no telemetry to third parties. Models are swappable.
          </p>
        </div>
      </div>
    </section>
  );
}

function Card({ title, body }: { title: string; body: string }) {
  return (
    <div className="border border-border rounded p-5">
      <h3 className="font-semibold mb-2">{title}</h3>
      <p className="text-sm text-text-muted">{body}</p>
    </div>
  );
}
