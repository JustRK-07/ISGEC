"use client";

import { useState } from "react";
import type { IssueOut } from "@/lib/api";
import { patchIssue } from "@/lib/api";
import { useWorkspace } from "@/lib/store";

const SEVERITY_STYLES: Record<IssueOut["severity"], string> = {
  high: "border-l-clash-hard bg-clash-hard/5",
  medium: "border-l-clash-soft bg-clash-soft/5",
  low: "border-l-text-muted bg-text-muted/5",
  pass: "border-l-pass bg-pass/5",
};

interface Props {
  issues: IssueOut[];
  summary: { pass: number; warn: number; fail: number };
}

export function IssueInspector({ issues, summary }: Props) {
  const [filter, setFilter] = useState<"all" | IssueOut["severity"]>("all");
  const selected = useWorkspace((s) => s.selectedIssueId);
  const select = useWorkspace((s) => s.selectIssue);

  const filtered = filter === "all" ? issues : issues.filter((it) => it.severity === filter);

  async function handlePatch(id: string, state: "open" | "resolved" | "dismissed") {
    try {
      await patchIssue(id, { state });
    } catch (e) {
      console.error(e);
    }
  }

  return (
    <div className="p-4">
      <h2 className="text-h3 font-semibold mb-3">Findings</h2>
      <div className="flex gap-2 mb-4 text-sm font-mono">
        <Pill label="All" value={issues.length} active={filter === "all"} onClick={() => setFilter("all")} />
        <Pill label="Fail" value={summary.fail} active={filter === "high"} onClick={() => setFilter("high")} color="text-clash-hard" />
        <Pill label="Warn" value={summary.warn} active={filter === "medium"} onClick={() => setFilter("medium")} color="text-clash-soft" />
        <Pill label="Pass" value={summary.pass} active={filter === "pass"} onClick={() => setFilter("pass")} color="text-pass" />
      </div>

      <ul className="space-y-2">
        {filtered.map((issue) => (
          <li
            key={issue.id}
            className={`border-l-4 ${SEVERITY_STYLES[issue.severity]} p-3 rounded-r cursor-pointer ${
              selected === issue.id ? "ring-2 ring-accent" : ""
            }`}
            onClick={() => select(issue.id)}
          >
            <div className="flex items-start justify-between mb-1">
              <span className="font-mono text-xs uppercase text-text-muted">
                {issue.code}
              </span>
              <span className="font-mono text-xs text-text-muted">
                {issue.sheet ? `SHEET ${issue.sheet}` : ""}
              </span>
            </div>
            <h3 className="font-medium text-sm mb-1">{issue.title}</h3>
            {issue.evidence && (
              <p className="text-xs text-text-muted mb-2">{issue.evidence}</p>
            )}
            {issue.formula && (
              <p className="text-xs font-mono text-text-primary bg-bg-primary p-2 rounded mb-2">
                {issue.formula}
              </p>
            )}
            <div className="flex gap-2 text-xs">
              {issue.state === "open" && (
                <>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handlePatch(issue.id, "resolved");
                    }}
                    className="text-pass hover:underline"
                  >
                    Resolve
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handlePatch(issue.id, "dismissed");
                    }}
                    className="text-text-muted hover:underline"
                  >
                    Dismiss
                  </button>
                </>
              )}
              {issue.state !== "open" && (
                <span className="font-mono text-text-muted uppercase">
                  {issue.state}
                </span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Pill({
  label,
  value,
  active,
  onClick,
  color,
}: {
  label: string;
  value: number;
  active: boolean;
  onClick: () => void;
  color?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-2 py-1 rounded border ${
        active ? "border-accent bg-accent/10" : "border-border"
      } ${color ?? "text-text-primary"}`}
    >
      {value} {label}
    </button>
  );
}
