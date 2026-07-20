"use client";

import useSWR from "swr";
import Link from "next/link";
import { fetcher, type ProjectSummary } from "@/lib/api";

export default function DashboardPage() {
  const { data: projects, error, isLoading } = useSWR<ProjectSummary[]>(
    "/api/projects",
    fetcher,
    { refreshInterval: 5000 }
  );

  if (isLoading) return <p className="p-8 text-text-muted">Loading…</p>;
  if (error) return <p className="p-8 text-clash-hard">Failed to load projects.</p>;
  if (!projects || projects.length === 0) {
    return (
      <div className="p-8">
        <p className="text-text-muted">No projects yet.</p>
        <Link href="/upload" className="text-accent hover:underline">
          Upload your first drawing →
        </Link>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-h2 font-bold mb-6">Projects</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {projects.map((p) => (
          <Link
            key={p.id}
            href={`/dashboard/${p.id}`}
            className="block p-4 rounded border border-border hover:border-accent transition-colors bg-white"
          >
            <div className="flex items-start justify-between mb-2">
              <h2 className="font-semibold truncate">{p.label}</h2>
              <StatusBadge status={p.status} />
            </div>
            <p className="text-sm text-text-muted mb-3">
              {p.kind} {p.rev ? `· Rev ${p.rev}` : ""}
            </p>
            <div className="flex gap-3 text-sm">
              <SummaryPill label="Fail" value={p.summary.fail} color="text-clash-hard" />
              <SummaryPill label="Warn" value={p.summary.warn} color="text-clash-soft" />
              <SummaryPill label="Pass" value={p.summary.pass} color="text-pass" />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: ProjectSummary["status"] }) {
  const colors: Record<typeof status, string> = {
    ready: "bg-pass/10 text-pass",
    processing: "bg-clash-soft/10 text-clash-soft",
    error: "bg-clash-hard/10 text-clash-hard",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-mono uppercase ${colors[status]}`}>
      {status}
    </span>
  );
}

function SummaryPill({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <span className={`font-mono ${color}`}>
      <strong>{value}</strong> {label}
    </span>
  );
}
