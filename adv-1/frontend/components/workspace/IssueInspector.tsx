"use client";

import { useState } from "react";
import type { IssueOut } from "@/lib/api";
import { api } from "@/lib/api";
import { useWorkspace } from "@/lib/store";

// Map IssueOut severities to the prototype's 3-bucket CSS modifiers
// (high / med / low). The "pass" severity is counted in the summary but
// not rendered as a finding card.
const SEVERITY_BUCKET: Record<IssueOut["severity"], "high" | "med" | "low"> = {
  high: "high",
  medium: "med",
  low: "low",
  pass: "low",
};

const SEVERITY_LABEL: Record<IssueOut["severity"], string> = {
  high: "FAIL",
  medium: "WARN",
  low: "INFO",
  pass: "PASS",
};

type FilterKey = "all" | IssueOut["severity"];
type TabKey = "issues" | "checks" | "activity" | "legend";

interface Props {
  issues: IssueOut[];
  summary: { pass: number; warn: number; fail: number };
}

const CHECKS = [
  { id: "fuzzy", name: "Fuzzy ID match", meta: "Levenshtein + sentence-transformer + grid proximity", state: "ok", count: 47 },
  { id: "pos", name: "Position tolerance", meta: "Euclidean · default ±25 mm", state: "ok", count: 142 },
  { id: "size", name: "Size tolerance", meta: "Per-axis · default ±25 mm", state: "warn", count: 1 },
  { id: "poly", name: "Polygon clash", meta: "Shapely polygon intersection", state: "fail", count: 3 },
  { id: "clear", name: "Clearance zone", meta: "Min. distance threshold per service type", state: "ok", count: 0 },
  { id: "elev", name: "Elevation alignment", meta: "T.O.S. drift · default ±50 mm", state: "warn", count: 1 },
  { id: "req", name: "Required-not-missing", meta: "Required element not present on partner sheet", state: "warn", count: 2 },
  { id: "orph", name: "Orphan-provided", meta: "Provided element not required", state: "ok", count: 0 },
];

const ACTIVITY = [
  { tone: "fail", time: "16:42:18 · TODAY", text: "Rule Engine flagged 3 issues on sheet 0301. Codes: WBE-B46 × 3." },
  { tone: "", time: "16:42:12", text: "Rule Engine completed 8/8 deterministic checks across 17 sheets. 142 elements passed." },
  { tone: "warn", time: "16:41:54", text: "Normalization Agent (Qwen2.5-32B · local) emitted canonical schema for 142 elements." },
  { tone: "ok", time: "16:41:31", text: "Grid registration resolved 6 grid bubbles (G, C, B × 2 levels). Coordinate frame unified." },
  { tone: "ok", time: "16:41:08", text: "DWG → DXF conversion via ODA File Converter. 17 sheets · 142 elements." },
  { tone: "ok", time: "16:40:55", text: "Ingestion: 3 DWG files hashed · revision ledger updated · Rev-C baseline locked." },
  { tone: "ok", time: "16:40:42", text: "User engineer@firm.com uploaded Mech GA + Str GA + Superimposed." },
];

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: "issues", label: "Issues" },
  { key: "checks", label: "Checks" },
  { key: "activity", label: "Activity" },
  { key: "legend", label: "Legend" },
];

export function IssueInspector({ issues, summary }: Props) {
  const [filter, setFilter] = useState<FilterKey>("all");
  const [tab, setTab] = useState<TabKey>("issues");
  const selected = useWorkspace((s) => s.selectedIssueId);
  const select = useWorkspace((s) => s.selectIssue);

  const filtered = filter === "all" ? issues : issues.filter((it) => it.severity === filter);
  const filterable = issues.filter((it) => it.severity !== "pass");

  async function handlePatch(id: string, state: "open" | "resolved" | "dismissed") {
    try {
      await api.patchIssue(id, { state });
    } catch (e) {
      console.error(e);
    }
  }

  return (
    <aside className="app-panel" id="appPanel" aria-label="QA/QC issues panel">
      {/* Header — title + tab bar */}
      <header className="panel-header">
        <div className="ph-title">
          <span>QA/QC &amp; Issues</span>
          <span className="count">{summary.fail + summary.warn} ISSUES</span>
        </div>
        <div className="panel-tabs" role="tablist" aria-label="Findings panel">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              data-tab={t.key}
              className={tab === t.key ? "active" : ""}
              aria-selected={tab === t.key}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </header>

      {/* Issues tab */}
      <div className={`panel-tab-content${tab === "issues" ? " active" : ""}`} data-tab-content="issues">
        <div className="panel-summary">
          <div className="stat high">
            <span className="n">{summary.fail}</span>
            <span className="l">High</span>
          </div>
          <div className="stat med">
            <span className="n">{summary.warn}</span>
            <span className="l">Medium</span>
          </div>
          <div className="stat low">
            <span className="n">{summary.pass}</span>
            <span className="l">Pass</span>
          </div>
        </div>

        <div className="panel-filter">
          <span
            className={`pill${filter === "all" ? " active" : ""}`}
            data-filter="all"
            role="button"
            tabIndex={0}
            onClick={() => setFilter("all")}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setFilter("all")}
          >
            All · {filterable.length}
          </span>
          <span
            className={`pill${filter === "high" ? " active" : ""}`}
            data-filter="high"
            role="button"
            tabIndex={0}
            onClick={() => setFilter("high")}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setFilter("high")}
          >
            Fail · {summary.fail}
          </span>
          <span
            className={`pill${filter === "medium" ? " active" : ""}`}
            data-filter="medium"
            role="button"
            tabIndex={0}
            onClick={() => setFilter("medium")}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setFilter("medium")}
          >
            Warn · {summary.warn}
          </span>
          <span
            className={`pill${filter === "pass" ? " active" : ""}`}
            data-filter="pass"
            role="button"
            tabIndex={0}
            onClick={() => setFilter("pass")}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setFilter("pass")}
          >
            Pass · {summary.pass}
          </span>
        </div>

        <div className="panel-list" id="issueList">
          {filtered.length === 0 && (
            <div className="panel-list-empty">No findings match this filter.</div>
          )}
          {filtered.map((issue) => {
            const bucket = SEVERITY_BUCKET[issue.severity];
            const isSelected = selected === issue.id;
            return (
              <article
                key={issue.id}
                className={`issue-card ${bucket}${isSelected ? " selected" : ""}`}
                onClick={() => select(issue.id)}
              >
                <header className="issue-head">
                  <span className="ih-loc">
                    {issue.sheet && <span className="sh">SHEET {issue.sheet}</span>}
                    {issue.grid && (
                      <>
                        <span className="pg">·</span>
                        <span className="sh">GRID {issue.grid}</span>
                      </>
                    )}
                  </span>
                  <span className={`ih-sev ${bucket}`}>{SEVERITY_LABEL[issue.severity]}</span>
                </header>

                <div className="issue-code">{issue.code}</div>
                <div className="issue-finding">{issue.title}</div>

                {issue.evidence && (
                  <>
                    <div className="issue-section-label">EVIDENCE</div>
                    <div className="issue-section-body">{issue.evidence}</div>
                  </>
                )}

                {issue.formula && (
                  <>
                    <div className="issue-section-label">FORMULA</div>
                    <div className="issue-section-body mono">{issue.formula}</div>
                  </>
                )}

                <div className="issue-actions">
                  {issue.state === "open" ? (
                    <>
                      <button
                        type="button"
                        className="ia-btn resolve"
                        onClick={(e) => {
                          e.stopPropagation();
                          void handlePatch(issue.id, "resolved");
                        }}
                      >
                        Resolve
                      </button>
                      <button
                        type="button"
                        className="ia-btn dismiss"
                        onClick={(e) => {
                          e.stopPropagation();
                          void handlePatch(issue.id, "dismissed");
                        }}
                      >
                        Dismiss
                      </button>
                    </>
                  ) : (
                    <span className="ia-btn" aria-label={`State: ${issue.state}`}>
                      {issue.state.toUpperCase()}
                    </span>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      </div>

      {/* Checks tab */}
      <div className={`panel-tab-content${tab === "checks" ? " active" : ""}`} data-tab-content="checks">
        <div className="checks-list">
          {CHECKS.map((c) => (
            <div key={c.id} className={`check-row ${c.state}`}>
              <div className={`check-icon ${c.state}`}>
                {c.state === "ok" ? "✓" : c.state === "warn" ? "!" : "✕"}
              </div>
              <div>
                <div className="check-name">{c.name}</div>
                <div className="check-meta">{c.meta}</div>
              </div>
              <div className="check-count">{c.count}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Activity tab */}
      <div className={`panel-tab-content${tab === "activity" ? " active" : ""}`} data-tab-content="activity">
        <div className="activity-list">
          {ACTIVITY.map((a, i) => (
            <div key={i} className="activity-item">
              <div className={`activity-dot ${a.tone}`} />
              <div className="activity-body">
                <div className="ab-time">{a.time}</div>
                <div className="ab-text">{a.text}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Legend tab */}
      <div className={`panel-tab-content${tab === "legend" ? " active" : ""}`} data-tab-content="legend">
        <div className="legend-list">
          <div className="legend-section-h">Severity</div>
          <div className="legend-item">
            <div className="legend-swatch" style={{ background: "var(--rust)", color: "var(--paper)" }}>
              !
            </div>
            <div>
              <div className="li-name">High · hard clash</div>
              <div className="li-desc">Required element missing, hard polygon intersection, or rule-blocked violation</div>
            </div>
          </div>
          <div className="legend-item">
            <div className="legend-swatch" style={{ background: "var(--amber)", color: "var(--paper)" }}>
              ~
            </div>
            <div>
              <div className="li-name">Medium · soft intrusion</div>
              <div className="li-desc">Tolerance drift, clearance zone near miss, or partial match</div>
            </div>
          </div>
          <div className="legend-item">
            <div className="legend-swatch" style={{ background: "var(--pass)", color: "var(--paper)" }}>
              ✓
            </div>
            <div>
              <div className="li-name">Pass · compliant</div>
              <div className="li-desc">All deterministic checks satisfied. Element appears in signed report.</div>
            </div>
          </div>

          <div className="legend-section-h">Click to locate</div>
          <p style={{ fontSize: 12, color: "var(--ink-soft)", lineHeight: 1.55, padding: "8px 0" }}>
            Click any <strong>issue card</strong> in the Issues tab to drop a cyan pulse ring on the matching
            element in the viewer. The element&apos;s grid + coordinates appear in the bottom status bar.
          </p>

          <div className="legend-section-h">Quick actions</div>
          <p style={{ fontSize: 12, color: "var(--ink-soft)", lineHeight: 1.55, padding: "8px 0" }}>
            <kbd style={{
              background: "var(--paper-2)",
              border: "1px solid var(--rule-strong)",
              padding: "1px 5px",
              fontFamily: "var(--font-mono)",
              fontSize: 10,
            }}>⌘K</kbd> global search ·
            <kbd style={{
              background: "var(--paper-2)",
              border: "1px solid var(--rule-strong)",
              padding: "1px 5px",
              fontFamily: "var(--font-mono)",
              fontSize: 10,
            }}>⌘\</kbd> toggle panel ·
            <kbd style={{
              background: "var(--paper-2)",
              border: "1px solid var(--rule-strong)",
              padding: "1px 5px",
              fontFamily: "var(--font-mono)",
              fontSize: 10,
            }}>Esc</kbd> close palette
          </p>
        </div>
      </div>
    </aside>
  );
}
