"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { AppShell } from "@/components/workspace/AppShell";
import { useProjects, useModals } from "@/lib/store";
import type { ProjectSummary } from "@/lib/api";

type Filter = "all" | "active" | "stale" | "archived";
type Sort = "recent" | "name" | "issues" | "pass";

function statusLabel(p: ProjectSummary): string {
  switch (p.status) {
    case "processing":
      return "● Analyzing";
    case "error":
      return "✕ Error";
    case "archived":
      return "○ Archived";
    case "stale":
      return "⚠ Stale";
    case "active":
    case "ready":
    default:
      return "● Ready";
  }
}

function statusAttr(p: ProjectSummary): "active" | "stale" | "archived" {
  if (p.status === "processing" || p.status === "active" || p.status === "ready") return "active";
  if (p.status === "error" || p.status === "stale") return "stale";
  return "archived";
}

function relTime(ts: number): string {
  if (!ts) return "—";
  const delta = Date.now() - ts;
  if (delta < 60_000) return "just now";
  if (delta < 3_600_000) return `${Math.floor(delta / 60_000)}m ago`;
  if (delta < 86_400_000) return `${Math.floor(delta / 3_600_000)}h ago`;
  return new Date(ts).toLocaleString();
}

export default function DashboardPage() {
  const list = useProjects((s) => s.list);
  const loading = useProjects((s) => s.loading);
  const error = useProjects((s) => s.error);
  const fetchList = useProjects((s) => s.fetchList);
  const removeOne = useProjects((s) => s.removeOne);
  const openUpload = useModals((s) => s.openUpload);

  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<Sort>("recent");
  const [query, setQuery] = useState("");

  useEffect(() => {
    void fetchList();
  }, [fetchList]);

  // Prototype: body.dash-empty toggles visibility of the empty state
  // and hides the grid. Keep them in sync.
  useEffect(() => {
    document.body.classList.toggle("dash-empty", list.length === 0 && !loading);
    return () => document.body.classList.remove("dash-empty");
  }, [list.length, loading]);

  const filtered = list
    .filter((p) => {
      if (filter !== "all" && p.status !== filter) return false;
      if (query) {
        const hay = `${p.label} ${p.shortName} ${p.rev ?? ""}`.toLowerCase();
        if (!hay.includes(query.toLowerCase())) return false;
      }
      return true;
    })
    .sort((a, b) => {
      switch (sort) {
        case "name":
          return a.label.localeCompare(b.label);
        case "issues":
          return b.summary.fail - a.summary.fail;
        case "pass":
          return b.summary.pass - a.summary.pass;
        case "recent":
        default:
          return b.lastOpened - a.lastOpened;
      }
    });

  const totalWarn = list.reduce((acc, p) => acc + p.summary.warn, 0);
  const totalFail = list.reduce((acc, p) => acc + p.summary.fail, 0);
  const countLabel = list.length === 0 ? "—" : `${list.length} total`;
  const summaryText = loading
    ? "Loading your workspace…"
    : list.length === 0
    ? "No projects yet — upload a Structural + Mechanical GA pair to begin."
    : `${list.length} project${list.length === 1 ? "" : "s"} · ${totalWarn} flagged · ${totalFail} critical`;

  return (
    <AppShell>
      <section className="app-dashboard" id="appDashboard" aria-label="Projects dashboard">
        <div className="dash-inner">
          <div className="dash-head">
            <div>
              <div className="dash-sub">ADV · PROJECTS · ON-PREM</div>
              <h1>
                Your projects <em id="dashCount">{countLabel}</em>
              </h1>
              <div className="dash-sub" id="dashSummary">{summaryText}</div>
            </div>
            <div className="dash-cta">
              <label className="dash-search" htmlFor="dashSearch">
                <span>🔍</span>
                <input
                  type="search"
                  id="dashSearch"
                  placeholder="Search projects, revisions, sheets…"
                  autoComplete="off"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </label>
              <button type="button" className="btn btn-primary" id="dashNewProject" onClick={openUpload}>
                + New Project
              </button>
            </div>
          </div>

          <div className="dash-filters">
            <div className="dash-filter-chips" role="tablist" aria-label="Filter projects by status">
              {(["all", "active", "stale", "archived"] as Filter[]).map((f) => (
                <button
                  key={f}
                  type="button"
                  className={`dash-chip${filter === f ? " active" : ""}`}
                  data-filter={f}
                  onClick={() => setFilter(f)}
                >
                  {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
            <label className="dash-sort">
              <span>Sort:</span>
              <select id="dashSort" value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
                <option value="recent">Last opened</option>
                <option value="name">Name (A–Z)</option>
                <option value="issues">Most issues</option>
                <option value="pass">Most passes</option>
              </select>
            </label>
          </div>

          {error && <div className="dash-error">{error}</div>}

          <div className="dash-grid" id="dashGrid">
            {filtered.map((p) => (
              <ProjectCard
                key={p.id}
                p={p}
                onDelete={async () => {
                  if (confirm(`Delete project ${p.label}? This cannot be undone.`)) {
                    await removeOne(p.id);
                  }
                }}
              />
            ))}
          </div>

          <div className="dash-empty" id="dashEmpty">
            <div className="dash-empty-glyph">∅</div>
            <h2>No projects yet</h2>
            <p>
              Upload your first <strong>Structural + Mechanical GA pair</strong> to start a clash and
              tolerance review. Files stay on-prem — nothing leaves your infrastructure.
            </p>
            <button type="button" className="btn btn-primary" id="dashEmptyCta" onClick={openUpload}>
              + New Project
            </button>
          </div>
        </div>
      </section>
    </AppShell>
  );
}

function ProjectCard({ p, onDelete }: { p: ProjectSummary; onDelete: () => void }) {
  const isProcessing = p.status === "processing";
  const s = p.summary;
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const openUpload = useModals((s) => s.openUpload);

  // Close menu on outside click.
  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [menuOpen]);

  return (
    <article className="proj-card" data-project={p.id}>
      <span className="proj-status" data-status={statusAttr(p)}>
        <span className="dot" />
        {statusLabel(p)}
      </span>
      <h3 className="proj-title">
        {p.shortName || p.label}
        <small>{p.kind || "Str + Mech"} · REV {p.rev || "—"}</small>
      </h3>
      <div className="proj-summary">
        <span className="ps-pass">✓ <strong>{s.pass}</strong> pass</span>
        <span className="ps-warn">⚠ <strong>{s.warn}</strong> warn</span>
        <span className="ps-fail">✕ <strong>{s.fail}</strong> fail</span>
      </div>
      <div className="proj-meta">
        <span>{p.label}</span>
        <span>{relTime(p.lastOpened)}</span>
      </div>
      <div className="proj-actions" ref={menuRef}>
        <Link href={`/dashboard/${p.id}`} className={`btn btn-primary proj-open${isProcessing ? " disabled" : ""}`}>
          {isProcessing ? "Analyzing…" : "Open →"}
        </Link>
        <button
          type="button"
          className="proj-more"
          aria-label="More actions"
          onClick={(e) => {
            e.stopPropagation();
            setMenuOpen((o) => !o);
          }}
        >
          ⋯
        </button>
        <div className={`proj-menu${menuOpen ? " open" : ""}`} role="menu">
          <button
            type="button"
            className="pm-add"
            role="menuitem"
            onClick={() => {
              setMenuOpen(false);
              openUpload();
            }}
          >
            <span className="pm-icon">＋</span> Add DWG pair
          </button>
          <button
            type="button"
            className="pm-duplicate"
            role="menuitem"
            onClick={() => {
              setMenuOpen(false);
              alert(`Duplicate "${p.label}" is not supported yet — coming soon.`);
            }}
          >
            <span className="pm-icon">⎘</span> Duplicate
          </button>
          <button
            type="button"
            className="pm-archive"
            role="menuitem"
            onClick={() => {
              setMenuOpen(false);
              alert(`Archive "${p.label}" is not supported yet — coming soon.`);
            }}
          >
            <span className="pm-icon">▣</span> Archive
          </button>
          <button
            type="button"
            className="pm-delete danger"
            role="menuitem"
            onClick={() => {
              setMenuOpen(false);
              onDelete();
            }}
          >
            <span className="pm-icon">✕</span> Delete
          </button>
        </div>
      </div>
    </article>
  );
}
