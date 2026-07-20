"use client";

import { use, useEffect } from "react";
import useSWR from "swr";
import { fetcher, type ProjectDetail } from "@/lib/api";
import { DrawingCanvas } from "@/components/workspace/DrawingCanvas";
import { IssueInspector } from "@/components/workspace/IssueInspector";

export default function ProjectWorkspace({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data, error, isLoading } = useSWR<ProjectDetail>(
    `/api/projects/${id}`,
    fetcher,
    { refreshInterval: 3000 }
  );

  useEffect(() => {
    if (!data) return;
    // Phase 2 of analyze is async — keep polling until llmStatus is 'done' or 'failed'
    const llm = data.analysis.llmStatus;
    if (llm && llm !== "done" && llm !== "failed" && llm !== "skipped") return;
  }, [data]);

  if (isLoading) return <p className="p-8 text-text-muted">Loading workspace…</p>;
  if (error) return <p className="p-8 text-clash-hard">Failed to load project.</p>;
  if (!data) return null;

  return (
    <div className="flex h-screen">
      <div className="flex-1 bg-bg-dark relative">
        <DrawingCanvas
          entities={[
            ...data.entities.str.map((e) => ({ ...e, discipline: "str" as const })),
            ...data.entities.mech.map((e) => ({ ...e, discipline: "mech" as const })),
          ]}
          sheets={data.sheets}
        />
        <div className="absolute top-4 left-4 text-white font-mono text-xs">
          <p>{data.label} {data.rev ? `· Rev ${data.rev}` : ""}</p>
          <p className="text-text-muted">
            {data.analysis.status} · {data.analysis.llmStatus ?? "—"}
          </p>
        </div>
      </div>
      <aside className="w-96 border-l border-border overflow-y-auto bg-white">
        <IssueInspector issues={data.issues} summary={data.summary} />
      </aside>
    </div>
  );
}
