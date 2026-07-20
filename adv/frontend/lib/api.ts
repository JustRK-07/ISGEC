/** Typed API client for the FastAPI backend. */

export type Severity = "high" | "medium" | "low" | "pass";
export type Discipline = "str" | "mech" | "extra";

export interface ProjectSummary {
  id: string;
  label: string;
  shortName: string;
  rev: string | null;
  kind: string;
  status: "processing" | "ready" | "error";
  createdAt: number;
  lastOpened: number;
  summary: { pass: number; warn: number; fail: number };
}

export interface FileOut {
  id: string;
  discipline: Discipline;
  filename: string;
  format: string;
  sizeBytes: number;
  sha256: string;
  parseStatus: string;
  parseMeta: unknown;
}

export interface IssueOut {
  id: string;
  severity: Severity;
  category: string;
  code: string;
  title: string;
  evidence: string | null;
  sheet: string | null;
  grid: string | null;
  mech_ref: string | null;
  str_ref: string | null;
  formula: string | null;
  result: unknown;
  state: string;
  assigned: string | null;
  created_at: number;
}

export interface EntityOut {
  id: string;
  discipline: Discipline;
  sheet: string;
  kind: string;
  label: string | null;
  x_mm: number | null;
  y_mm: number | null;
  w_mm: number | null;
  h_mm: number | null;
  rotation: number | null;
  meta: {
    layer?: string;
    type?: string;
    startPoint?: { x: number; y: number } | null;
    endPoint?: { x: number; y: number } | null;
    position?: { x: number; y: number } | null;
    center?: { x: number; y: number } | null;
    vertices?: Array<{ x: number; y: number }> | null;
    radius?: number | null;
    insUnits?: number | null;
  } | null;
}

export interface ProjectDetail extends ProjectSummary {
  files: FileOut[];
  issues: IssueOut[];
  entities: { str: EntityOut[]; mech: EntityOut[] };
  sheets: string[];
  analysis: {
    status: string;
    phase: string | null;
    llmStatus: string | null;
    llmError: string | null;
    summary: { pass: number; warn: number; fail: number } | null;
    issueCount: number | null;
    error: string | null;
    startedAt: number | null;
    finishedAt: number | null;
  };
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ||
  (typeof window !== "undefined" ? "" : "http://localhost:8000");

export async function fetcher<T>(path: string): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export async function patchIssue(id: string, body: { state?: string; assigned?: string }) {
  const res = await fetch(`${API_BASE}/api/issues/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
  return res.json();
}

export async function triggerAnalysis(projectId: string) {
  const res = await fetch(`${API_BASE}/api/projects/${projectId}/analyze`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Analyze failed: ${res.status}`);
  return res.json();
}
