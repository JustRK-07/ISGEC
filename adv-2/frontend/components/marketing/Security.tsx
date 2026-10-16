export function Security() {
  return (
    <section className="section" id="security">
      <div className="container">
        <div className="section-header reveal">
          <div className="section-label">11 / SECURITY</div>
          <h2>
            Self-hosted by design. <span className="accent">Zero third-party API.</span>{" "}
            Audited by default.
          </h2>
          <p className="lede">
            The architecture is local-model-first — every inference, every byte, every audit
            row stays on hardware you own. Enterprise controls wrap that foundation:
            encryption, RBAC, audit ledger, and the compliance frameworks your security team
            already audits against.
          </p>
        </div>

        <div className="sec-grid reveal">
          <div className="sec-card featured">
            <div className="sec-tag">[ ZERO API ]</div>
            <h4>Self-Hosted Local LLM</h4>
            <p>
              The cornerstone of our security model. All inference runs on your hardware
              via Ollama, vLLM, or llama.cpp.{" "}
              <strong>No third-party API. No tokens. No telemetry. No prompt logging to a vendor.</strong>{" "}
              The model is a binary you run, not a service you rent. Swappable across Qwen,
              Llama, DeepSeek, Mistral, and Granite.
            </p>
          </div>
          <div className="sec-card">
            <div className="sec-tag">[ SOC 2 TYPE II ]</div>
            <h4>Compliance &amp; Encryption</h4>
            <p>
              SOC 2 Type II audited. AES-256 encryption at rest, TLS 1.3 in transit.
              KMS-managed keys with optional HSM-backed root of trust. Aligns with ISO 27001,
              NIST 800-171, and IL5-compatible architecture for restricted-project deployments.
            </p>
          </div>
          <div className="sec-card">
            <div className="sec-tag">[ ON-PREM / VPC ]</div>
            <h4>On-Prem &amp; Air-Gap</h4>
            <p>
              VPC, full on-prem, or fully air-gapped deployment.{" "}
              <strong>Your data never leaves your perimeter.</strong> No internet egress
              required at runtime. Compatible with classified, federal, and export-controlled
              project environments.
            </p>
          </div>
          <div className="sec-card">
            <div className="sec-tag">[ RBAC + SSO ]</div>
            <h4>Access Control</h4>
            <p>
              Engineer · Reviewer · Admin · Super Admin. SSO via SAML 2.0, OIDC. SCIM
              provisioning. Project-, sheet-, and finding-level permissions. RBAC extends to
              the local LLM access layer — only authorized reviewers can invoke inference.
            </p>
          </div>
        </div>

        <div className="audit-ledger reveal">
          <div className="audit-ledger-tag">AUDIT LEDGER · LOCAL-ONLY</div>
          <p>
            Every action — upload, view, override, sign-off, export, LLM prompt, LLM response
            — is logged with timestamp, user ID, and IP.{" "}
            <strong>The ledger itself never leaves your infrastructure.</strong> Drawings are
            immutable once sealed. Compliance teams get read-only export on demand; auditors
            never reach a third-party server.
          </p>
          <div className="audit-meta">
            TS · USER · IP · LLM-PROMPT · LLM-RESPONSE<br />
            READ-ONLY · EXPORT · LOCAL-ONLY
          </div>
        </div>
      </div>
    </section>
  );
}
