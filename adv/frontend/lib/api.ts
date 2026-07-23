/** Typed API client for the FastAPI backend. */

export type Severity = "high" | "medium" | "low" | "pass";
export type Discipline = "str" | "mech" | "extra";

export interface ProjectSummary {
  id: string;
  label: string;
  shortName: string;
  rev: string | null;
  kind: string;
  status: "processing" | "ready" | "error" | "archived" | "stale" | "active";
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
  (typeof window !== "undefined" ? `${window.location.protocol}//${window.location.hostname}:8001` : "http://localhost:8001");

async function handle<T>(res: Response): Promise<T> {
  const ct = res.headers.get("content-type") || "";
  const body = ct.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const msg = (body && (body.error || body.message)) || `HTTP ${res.status}`;
    const err = new Error(msg);
    (err as Error & { status?: number }).status = res.status;
    throw err;
  }
  return body as T;
}

export const api = {
  base: API_BASE,

  listProjects(): Promise<ProjectSummary[]> {
    return fetch(`${API_BASE}/api/projects`).then(handle);
  },

  getProject(id: string): Promise<ProjectDetail> {
    return fetch(`${API_BASE}/api/projects/${id}`).then(handle);
  },

  createProject(formData: FormData): Promise<ProjectSummary> {
    return fetch(`${API_BASE}/api/projects`, { method: "POST", body: formData }).then(handle);
  },

  deleteProject(id: string): Promise<{ ok: boolean }> {
    return fetch(`${API_BASE}/api/projects/${id}`, { method: "DELETE" }).then(handle);
  },

  triggerAnalysis(projectId: string): Promise<{ status: string }> {
    return fetch(`${API_BASE}/api/projects/${projectId}/analyze`, { method: "POST" }).then(handle);
  },

  getAnalysisStatus(projectId: string): Promise<ProjectDetail["analysis"]> {
    return fetch(`${API_BASE}/api/projects/${projectId}/analysis`).then(handle);
  },

  patchIssue(id: string, body: { state?: string; assigned?: string }) {
    return fetch(`${API_BASE}/api/issues/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(handle);
  },
};
