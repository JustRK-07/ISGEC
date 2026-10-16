export function LocalModel() {
  return (
    <section className="local-model" id="local-model" aria-label="Self-hosted local model architecture">
      <div className="local-model-inner">
        <div className="section-header local-model-head reveal">
          <div>
            <div className="section-label">02 / LOCAL MODEL</div>
            <h2>
              The model runs <em>on your hardware</em>.
              <br />Not in someone else&apos;s data center.
            </h2>
          </div>
          <p>
            ADV ships with a self-hosted open-weight LLM served on your own
            infrastructure — Ollama, vLLM, or llama.cpp.{" "}
            <strong>Zero third-party API calls. Zero tokens. Zero telemetry leaving your perimeter.</strong>{" "}
            Your drawings, your grids, your sheets — they never touch a vendor cloud, ever.
          </p>
        </div>

        <div className="lm-stack reveal">
          <div className="lm-card">
            <div className="lm-tag">[ LOCAL INFERENCE ]</div>
            <h4>Self-hosted LLM on your hardware</h4>
            <p>Open-weight models served locally via Ollama, vLLM, or llama.cpp. Inference stays on a server you control — behind your firewall, on your VLAN, governed by your IT policies. No packet ever leaves for an external inference provider.</p>
            <div className="lm-tech">Ollama · vLLM · llama.cpp · Qwen2.5-32B · Llama 3.1 · DeepSeek · Mistral · Granite</div>
          </div>
          <div className="lm-card">
            <div className="lm-tag">[ ZERO API ]</div>
            <h4>No third-party API. No cloud LLM.</h4>
            <p>There is no OpenAI, Anthropic, Google, or Azure endpoint in the call path. No per-token billing. No rate limits. No prompt logging to a vendor. The model is a binary you run, not a service you rent.</p>
            <div className="lm-tech">No API keys · No quotas · No vendor prompt retention</div>
          </div>
          <div className="lm-card">
            <div className="lm-tag">[ DATA RESIDENCY ]</div>
            <h4>Drawings never leave your infrastructure</h4>
            <p>DWG bytes, grid coordinates, finding text, reviewer comments — every byte stays on hardware you own. Compatible with restricted-project, IL5, and air-gapped deployments.</p>
            <div className="lm-tech">On-prem · VPC · Air-gap · IL5-compatible architecture</div>
          </div>
          <div className="lm-card">
            <div className="lm-tag">[ SWAPPABLE ]</div>
            <h4>Model is swappable. Pipeline is not locked.</h4>
            <p>Switch between Qwen, Llama, DeepSeek, Mistral, or Granite without rewriting the pipeline. The orchestration layer is model-agnostic — pick the model that fits your compliance review.</p>
            <div className="lm-tech">JSON-schema constrained output · Tool calling · No retraining</div>
          </div>
        </div>

        <div className="lm-rack reveal">
          <div className="lm-diagram">
            <div className="lm-diagram-title">[ DEPLOYMENT TOPOLOGY ]</div>

            <div className="lm-diagram-row">
              <div className="lm-node locked">
                <strong>YOUR HARDWARE</strong>
                ADV · Local LLM (Ollama / vLLM)
                <br />DWG bytes · Findings · Audit ledger
              </div>
              <div className="lm-arrow">→</div>
              <div className="lm-node">
                <strong>REVIEWER</strong>
                Browser · Local network only
              </div>
            </div>

            <div className="lm-diagram-row">
              <div className="lm-node locked">
                <strong>YOUR HARDWARE</strong>
                ADV · Local LLM (Ollama / vLLM)
                <br />DWG bytes · Findings · Audit ledger
              </div>
              <div className="lm-x">✕</div>
              <div className="lm-node cloud">
                <strong>THIRD-PARTY API</strong>
                OpenAI · Anthropic · Google · Azure
                <br />Not in the call path
              </div>
            </div>

            <div className="lm-diagram-row">
              <div className="lm-node">
                <strong>YOUR HARDWARE</strong>
                Optional: on-prem GPU box · air-gapped cluster · secure enclave
              </div>
              <div className="lm-arrow">⇌</div>
              <div className="lm-node locked">
                <strong>YOUR STORAGE</strong>
                DWG originals · Revision ledger · Audit log
                <br />Encrypted at rest (AES-256)
              </div>
            </div>
          </div>

          <div className="lm-pillars">
            <div className="lm-pillar">
              <div className="lm-dot"></div>
              <div>
                <h5>Hardware you already own</h5>
                <p>Runs on a single modern GPU server (24 GB VRAM for 32B-class models) or CPU-only via llama.cpp. No specialized appliance required.</p>
              </div>
            </div>
            <div className="lm-pillar">
              <div className="lm-dot"></div>
              <div>
                <h5>Compliance posture is yours</h5>
                <p>SOC 2, ISO 27001, NIST 800-171, IL5 — your IT owns the audit. We don&apos;t sit in the vendor list.</p>
              </div>
            </div>
            <div className="lm-pillar">
              <div className="lm-dot"></div>
              <div>
                <h5>Air-gapped deployments supported</h5>
                <p>Fully offline mode for classified, federal, and export-controlled projects. No internet egress required at runtime.</p>
              </div>
            </div>
            <div className="lm-pillar">
              <div className="lm-dot"></div>
              <div>
                <h5>Audit ledger stays on-prem</h5>
                <p>Every upload, prompt, finding, override, and sign-off is recorded locally with timestamp + user + IP. Read-only export for compliance teams.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="lm-foot reveal">
          <div className="lm-stat"><strong>0</strong>third-party API calls</div>
          <div className="lm-stat"><strong>100%</strong>on-prem inference</div>
          <div className="lm-stat"><strong>0 bytes</strong>data egress</div>
          <div className="lm-stat"><strong>1</strong>model binary you control</div>
        </div>
      </div>
    </section>
  );
}
