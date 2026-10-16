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
    startAngle?: number | null;
    endAngle?: number | null;
    closed?: boolean | null;
    insUnits?: number | null;
  } | null;
}

export interface ProjectEventOut {
  id: string;
  projectId: string;
  category: string;
  code: string;
  tone: "info" | "ok" | "warn" | "fail";
  message: string;
  payload: Record<string, unknown> | null;
  createdAt: number;
}

export interface CheckOut {
  id: string;
  name: string;
  meta: string;
  state: "ok" | "warn" | "fail";
  count: number;
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
  checks: CheckOut[];
  events: ProjectEventOut[];
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ||
  (typeof window !== "undefined" ? `${window.location.protocol}//${window.location.hostname}:8001` : "http://localhost:8001");

export function extractDetail(body: unknown): string {
  if (!body) return "";
  if (typeof body === "string") return body;
  if (typeof body !== "object") return "";
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((entry) => {
        if (!entry || typeof entry !== "object") return "";
        const item = entry as { loc?: unknown; msg?: unknown };
        const location = Array.isArray(item.loc) ? item.loc.join(".") : "";
        const message = typeof item.msg === "string" ? item.msg : "";
        return location && message ? `${location}: ${message}` : message;
      })
      .filter(Boolean)
      .join("; ");
  }
  const fallback = body as { error?: unknown; message?: unknown };
  if (typeof fallback.error === "string") return fallback.error;
  if (typeof fallback.message === "string") return fallback.message;
  return "";
}

async function handle<T>(res: Response): Promise<T> {
  const ct = res.headers.get("content-type") || "";
  const body = ct.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const msg = extractDetail(body) || `HTTP ${res.status}`;
    const err = new Error(msg);
    (err as Error & { status?: number }).status = res.status;
    throw err;
  }
  return body as T;
}

export const api = {
  base: API_BASE,

  listProjects(): Promise<ProjectSummary[]> {
    return fetch(`${API_BASE}/api/projects`).then((res) => handle<ProjectSummary[]>(res));
  },

  getProject(id: string): Promise<ProjectDetail> {
    return fetch(`${API_BASE}/api/projects/${id}`).then((res) => handle<ProjectDetail>(res));
  },

  createProject(formData: FormData): Promise<ProjectSummary> {
    return fetch(`${API_BASE}/api/projects`, { method: "POST", body: formData }).then((res) =>
      handle<ProjectSummary>(res),
    );
  },

  deleteProject(id: string): Promise<{ ok: boolean }> {
    return fetch(`${API_BASE}/api/projects/${id}`, { method: "DELETE" }).then((res) =>
      handle<{ ok: boolean }>(res),
    );
  },

  triggerAnalysis(projectId: string): Promise<{ status: string }> {
    return fetch(`${API_BASE}/api/projects/${projectId}/analyze`, { method: "POST" }).then((res) =>
      handle<{ status: string }>(res),
    );
  },

  getAnalysisStatus(projectId: string): Promise<ProjectDetail["analysis"]> {
    return fetch(`${API_BASE}/api/projects/${projectId}/analysis`).then((res) =>
      handle<ProjectDetail["analysis"]>(res),
    );
  },

  patchIssue(id: string, body: { state?: string; assigned?: string }): Promise<IssueOut> {
    return fetch(`${API_BASE}/api/issues/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((res) => handle<IssueOut>(res));
  },
};
