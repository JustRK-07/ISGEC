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

interface Props {
  issues: IssueOut[];
  summary: { pass: number; warn: number; fail: number };
}

export function IssueInspector({ issues, summary }: Props) {
  const [filter, setFilter] = useState<FilterKey>("all");
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
    <aside className="app-panel" aria-label="Findings">
      {/* Header — title + failing-count chip */}
      <header className="panel-header">
        <div className="ph-title">
          FINDINGS
          <span className="count">{summary.fail}</span>
        </div>
      </header>

      {/* Summary stat row — fail / warn / pass */}
      <div className="panel-summary">
        <div className="stat high">
          <span className="n">{summary.fail}</span>
          <span className="l">FAIL</span>
        </div>
        <div className="stat med">
          <span className="n">{summary.warn}</span>
          <span className="l">WARN</span>
        </div>
        <div className="stat low">
          <span className="n">{summary.pass}</span>
          <span className="l">PASS</span>
        </div>
      </div>

      {/* Severity filter pills */}
      <div className="panel-filter">
        <button
          type="button"
          className={`pill${filter === "all" ? " active" : ""}`}
          onClick={() => setFilter("all")}
        >
          ALL · {filterable.length}
        </button>
        <button
          type="button"
          className={`pill${filter === "high" ? " active" : ""}`}
          onClick={() => setFilter("high")}
        >
          FAIL · {summary.fail}
        </button>
        <button
          type="button"
          className={`pill${filter === "medium" ? " active" : ""}`}
          onClick={() => setFilter("medium")}
        >
          WARN · {summary.warn}
        </button>
        <button
          type="button"
          className={`pill${filter === "pass" ? " active" : ""}`}
          onClick={() => setFilter("pass")}
        >
          PASS · {summary.pass}
        </button>
      </div>

      {/* Issue cards */}
      <div className="panel-list">
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
    </aside>
  );
}
