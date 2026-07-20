export function WhyAgentic() {
  return (
    <section className="py-20 px-6 bg-white">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-h2 font-bold mb-10">Why agentic AI, not a trained ML model</h2>
        <div className="grid md:grid-cols-2 gap-8">
          <div>
            <h3 className="font-semibold mb-3 text-accent">Agentic AI (Self-Hosted LLM)</h3>
            <ul className="text-sm space-y-1 text-text-muted">
              <li>✓ No labeled training data</li>
              <li>✓ Days to first working version</li>
              <li>✓ DWG exact — entities, layers, mm units</li>
              <li>✓ Fully deterministic formulas</li>
              <li>✓ 100% on-prem, zero third-party API</li>
              <li>✓ Swappable models (Qwen / Llama / DeepSeek)</li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold mb-3 text-text-muted">Trained ML Model</h3>
            <ul className="text-sm space-y-1 text-text-muted">
              <li>✗ Hundreds–thousands of labeled drawings</li>
              <li>✗ Weeks to months</li>
              <li>✗ Must rasterise DWG first</li>
              <li>✗ Confidence-scored predictions</li>
              <li>✗ Usually cloud-hosted</li>
              <li>✗ Locked to retraining cycle</li>
            </ul>
          </div>
        </div>
        <p className="mt-10 text-text-muted">
          The core checks are exact rule-based math — distance, size, overlap, tolerance.
          Putting exact formulas behind a self-hosted LLM agent gives deterministic,
          audit-defensible findings <em>and</em> full data residency.
        </p>
      </div>
    </section>
  );
}
