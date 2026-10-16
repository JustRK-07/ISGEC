"use client";

import { useState } from "react";
import type { CheckOut, IssueOut, ProjectEventOut } from "@/lib/api";
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
  checks: CheckOut[];
  events: ProjectEventOut[];
}

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: "issues", label: "Issues" },
  { key: "checks", label: "Checks" },
  { key: "activity", label: "Activity" },
  { key: "legend", label: "Legend" },
];

const CHECK_STATE_ICON: Record<CheckOut["state"], string> = {
  ok: "✓",
  warn: "!",
  fail: "✕",
};

const EVENT_TONE_DOT: Record<ProjectEventOut["tone"], string> = {
  info: "info",
  ok: "ok",
  warn: "warn",
  fail: "fail",
};

/** Render an event timestamp relative to today (HH:MM:SS) or with date fallback. */
function formatActivityTime(createdAtMs: number): string {
  const date = new Date(createdAtMs);
  if (Number.isNaN(date.getTime())) return "—";
  const today = new Date();
  const sameDay =
    date.getFullYear() === today.getFullYear() &&
    date.getMonth() === today.getMonth() &&
    date.getDate() === today.getDate();
  const time = date.toLocaleTimeString([], { hour12: false });
  return sameDay ? `${time} · TODAY` : `${date.toISOString().slice(0, 10)} ${time}`;
}

const EMPTY_STATE = "—";

export function IssueInspector({ issues, summary, checks, events }: Props) {
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
          {checks.length === 0 && (
            <div className="panel-list-empty">No checks recorded yet.</div>
          )}
          {checks.map((c) => (
            <div key={c.id} className={`check-row ${c.state}`}>
              <div className={`check-icon ${c.state}`}>
                {CHECK_STATE_ICON[c.state]}
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
          {events.length === 0 && (
            <div className="panel-list-empty">No activity recorded yet.</div>
          )}
          {events.map((e) => (
            <div key={e.id} className="activity-item">
              <div className={`activity-dot ${EVENT_TONE_DOT[e.tone]}`} />
              <div className="activity-body">
                <div className="ab-time">{formatActivityTime(e.createdAt)}</div>
                <div className="ab-text">
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--ink-soft)", marginRight: 6 }}>
                    {e.code}
                  </span>
                  {e.message || EMPTY_STATE}
                </div>
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
