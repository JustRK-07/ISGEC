"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/workspace/AppShell";
import { DrawingCanvas } from "@/components/workspace/DrawingCanvas";
import { IssueInspector } from "@/components/workspace/IssueInspector";
import { useWorkspace, useModals } from "@/lib/store";
import { api, type ProjectDetail } from "@/lib/api";

const RAIL_TOOLS: Array<{ key: string; label: string; title: string; glyph: React.ReactNode }> = [
  { key: "cursor", label: "Cursor", title: "Cursor / Select & drag-pan (V)", glyph: (
    <svg viewBox="0 0 24 24"><path className="fill" d="M5 3 L5 19 L9 15 L11 21 L13 20 L11 14 L17 14 Z"/></svg>
  )},
  { key: "zoom", label: "Zoom", title: "Zoom in/out (Z)", glyph: (
    <svg viewBox="0 0 24 24"><circle cx="10" cy="10" r="6"/><path d="M14.5 14.5 L20 20"/><path d="M7 10 H13 M10 7 V13"/></svg>
  )},
  { key: "fit", label: "Fit", title: "Fit drawing to view (F)", glyph: (
    <svg viewBox="0 0 24 24"><path d="M4 9 V4 H9 M20 9 V4 H15 M4 15 V20 H9 M20 15 V20 H15"/></svg>
  )},
  { key: "layers", label: "Layers", title: "Cycle layer mode — all / flagged / structure (L)", glyph: (
    <svg viewBox="0 0 24 24"><path d="M3 8 L12 4 L21 8 L12 12 Z"/><path d="M3 13 L12 17 L21 13"/><path d="M3 18 L12 22 L21 18"/></svg>
  )},
];

const INSPECT_TOOLS: Array<{ key: string; label: string; title: string; glyph: React.ReactNode }> = [
  { key: "measure", label: "Measure", title: "Measure distance / area (M)", glyph: (
    <svg viewBox="0 0 24 24"><path d="M3 16 L18 6 L21 9 L6 19 Z"/><path d="M6 14 L8 12 M9 15 L11 13 M12 12 L14 10 M15 9 L17 7"/></svg>
  )},
  { key: "identify", label: "Identify", title: "Identify element — click to read properties (I)", glyph: (
    <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M8 12 L11 15 L16 9"/></svg>
  )},
  { key: "clash", label: "Clash", title: "Toggle issue / clash flag visibility (C)", glyph: (
    <svg viewBox="0 0 24 24"><path d="M12 3 L22 21 L2 21 Z"/><path d="M12 10 V14 M12 17.5 V18"/></svg>
  )},
];

const ANNOTATE_TOOLS: Array<{ key: string; label: string; title: string; glyph: React.ReactNode }> = [
  { key: "annotate", label: "Annotate", title: "Annotate — drop a pin (A)", glyph: (
    <svg viewBox="0 0 24 24"><path d="M4 20 L8 19 L19 8 L16 5 L5 16 Z"/><path d="M14 7 L17 10"/></svg>
  )},
  { key: "markup", label: "Markup", title: "Toggle markup overlays (M+O)", glyph: (
    <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
  )},
];

const ACTION_TOOLS: Array<{ key: string; label: string; title: string; glyph: React.ReactNode }> = [
  { key: "snapshot", label: "Snapshot", title: "Snapshot current view as PNG (S)", glyph: (
    <svg viewBox="0 0 24 24"><rect x="3" y="6" width="18" height="14" rx="1"/><path d="M8 6 L9.5 3.5 H14.5 L16 6"/><circle cx="12" cy="13" r="3.5"/></svg>
  )},
  { key: "undo", label: "Undo", title: "Undo last change (Z or Cmd+Z)", glyph: (
    <svg viewBox="0 0 24 24"><path d="M9 14 L4 9 L9 4"/><path d="M4 9 H14 a5 5 0 0 1 5 5 v0 a5 5 0 0 1-5 5 H10"/></svg>
  )},
  { key: "redo", label: "Redo", title: "Redo (Y or Cmd+Shift+Z)", glyph: (
    <svg viewBox="0 0 24 24"><path d="M15 14 L20 9 L15 4"/><path d="M20 9 H10 a5 5 0 0 0-5 5 v0 a5 5 0 0 0 5 5 H14"/></svg>
  )},
];

const ALL_RAIL_KEYS = new Set([
  ...RAIL_TOOLS.map((t) => t.key),
  ...INSPECT_TOOLS.map((t) => t.key),
  ...ANNOTATE_TOOLS.map((t) => t.key),
  ...ACTION_TOOLS.map((t) => t.key),
]);

export default function ProjectWorkspace({ params }: { params: { id: string } }) {
  const { id } = params;
  const [data, setData] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tool, setTool] = useState("cursor");
  const [running, setRunning] = useState(false);
  const openUpload = useModals((s) => s.openUpload);

  async function load() {
    try {
      setLoading(true);
      const p = await api.getProject(id);
      setData(p);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Keep polling while LLM analysis is in progress.
  useEffect(() => {
    if (!data) return;
    const llm = data.analysis.llmStatus;
    if (!llm || llm === "done" || llm === "failed" || llm === "skipped") return;
    const t = setTimeout(load, 2500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  async function runAnalysis() {
    setRunning(true);
    try {
      await api.triggerAnalysis(id);
      setTimeout(load, 1500);
    } finally {
      setRunning(false);
    }
  }

  return (
    <AppShell>
      <main className="app-main">
        <aside className="app-rail" aria-label="Tools">
          {RAIL_TOOLS.map((t) => (
            <button
              key={t.key}
              type="button"
              className={`app-rail-btn${tool === t.key ? " active" : ""}`}
              data-tool={t.key}
              title={t.title}
              onClick={() => setTool(t.key)}
            >
              <span className="rb-glyph">{t.glyph}</span>
              <span className="rb-label">{t.label}</span>
            </button>
          ))}
          <div className="app-rail-divider" />
          {INSPECT_TOOLS.map((t) => (
            <button
              key={t.key}
              type="button"
              className={`app-rail-btn${tool === t.key ? " active" : ""}`}
              data-tool={t.key}
              title={t.title}
              onClick={() => setTool(t.key)}
            >
              <span className="rb-glyph">{t.glyph}</span>
              <span className="rb-label">{t.label}</span>
            </button>
          ))}
          <div className="app-rail-divider" />
          {ANNOTATE_TOOLS.map((t) => (
            <button
              key={t.key}
              type="button"
              className={`app-rail-btn${tool === t.key ? " active" : ""}`}
              data-tool={t.key}
              title={t.title}
              onClick={() => setTool(t.key)}
            >
              <span className="rb-glyph">{t.glyph}</span>
              <span className="rb-label">{t.label}</span>
            </button>
          ))}
          <div className="app-rail-divider" />
          {ACTION_TOOLS.map((t) => (
            <button
              key={t.key}
              type="button"
              className={`app-rail-btn${tool === t.key ? " active" : ""}`}
              data-tool={t.key}
              title={t.title}
              onClick={() => setTool(t.key)}
            >
              <span className="rb-glyph">{t.glyph}</span>
              <span className="rb-label">{t.label}</span>
            </button>
          ))}
          <div className="rail-mode">
            MODE
            <strong id="railMode">{(ALL_RAIL_KEYS.has(tool) ? tool : "cursor").toUpperCase()}</strong>
          </div>
        </aside>

        <section className="workspace" aria-label="Drawing workspace">
          <div className="workspace-tabs">
            <button className="ws-tab-new" type="button" onClick={openUpload} title="Open another drawing">+ NEW TAB</button>
            <span className="ws-tabs-spacer" />
            <button className="ws-run-btn" type="button" disabled={running} onClick={runAnalysis}>
              {running ? "Running…" : "▶ Run QA/QC check"}
            </button>
            <button className="ws-super-btn" type="button" title="Generate superimposed view, open in new browser tab">⚡ SUPERIMPOSE</button>
          </div>

          <section className="app-viewer" aria-label="Drawing viewer">
            <div className="viewer-toolbar">
              <div className="vt-left">
                <button className="vt-btn" type="button" id="vtPrev" title="Previous sheet ([)">← Prev sheet</button>
                <button className="vt-btn" type="button" id="vtNext" title="Next sheet (])">Next sheet →</button>
                {data && (
                  <span id="vtSheetMeta">
                    {data.sheets.length > 0
                      ? `Page 1 / ${data.sheets.length} · Sheet ${data.sheets[0]} · ${data.label}`
                      : `Sheet — · ${data.label}`}
                  </span>
                )}
              </div>
              <div className="vt-right">
                <span className="vt-zoom">Zoom <strong>100%</strong></span>
                <button className="vt-btn" type="button" title="Fit drawing to view (F)">Fit</button>
                <button className="vt-btn" type="button" title="Reset zoom to 100% (1)">100%</button>
                <button className="vt-btn" type="button" title="Cycle layer mode (L)">Layers</button>
                <button className="vt-btn" type="button" title="Undo (U / Cmd+Z)">⟲ Undo</button>
                <button className="vt-btn" type="button" title="Redo (Y / Cmd+Shift+Z)">⟳ Redo</button>
                <button className="vt-btn diff-toggle" type="button" title="Toggle REV-A vs REV-C overlay">REV-A ⇄ REV-C</button>
                <button className="vt-btn" type="button" title="Snapshot current view as PNG (S)">⇪ Export</button>
              </div>
            </div>

            <div className="viewer-canvas-app" id="canvasViewport">
              <div className="canvas-frame-stack" id="canvasFrameStack" />
              {loading && <div className="ws-loading">Loading project…</div>}
              {error && <div className="ws-error">{error}</div>}
              {data && (
                <>
                  <div className="canvas-tool tl">
                    <span className="swatch s-mech" /> MECH
                    <span className="swatch s-str" /> STR
                  </div>
                  <div className="canvas-tool bl" aria-label="Nudge">
                    ←7m nudge · ↑10pt
                  </div>
                  <DrawingCanvas
                    entities={[
                      ...data.entities.str.map((e) => ({ ...e, discipline: "str" as const })),
                      ...data.entities.mech.map((e) => ({ ...e, discipline: "mech" as const })),
                    ]}
                    sheets={data.sheets}
                  />
                  <div className="pulse-tooltip" id="svgTooltip" />
                  <button
                    className="canvas-add-frame"
                    type="button"
                    title="Add a frame from another drawing"
                  >
                    + FRAME
                  </button>
                </>
              )}
              {!loading && data && data.sheets.length === 0 && (
                <div className="ws-empty">
                  <p>No sheets extracted yet.</p>
                  <button className="btn btn-primary" onClick={runAnalysis}>▶ Run analysis</button>
                </div>
              )}
            </div>

            <div className="frame-chips" id="frameChips">
              <span className="frame-chips-label">FRAMES</span>
              <button className="frame-chip-add" type="button" title="Add a frame from another drawing">
                + add
              </button>
            </div>

            <div className="sheet-filmstrip" aria-label="Sheet filmstrip">
              <div className="sheet-filmstrip-label">
                Sheets · <strong>{data?.sheets.length ?? 0}</strong>
              </div>
              <div className="sheet-filmstrip-scroll">
                {(data?.sheets ?? []).map((s, i) => (
                  <SheetThumb key={s} sheet={s} index={i} />
                ))}
              </div>
            </div>
          </section>
        </section>

        {data && (
          <IssueInspector issues={data.issues} summary={data.summary} />
        )}

        <button className="chat-tab" type="button" title="Open chat">
          CHAT
        </button>
      </main>

      <div className="status-bar" aria-label="Status bar">
        <div className="sb-item">
          <strong>x=4200mm</strong> <strong>y=2800mm</strong>
        </div>
        <div className="sb-item sb-divider" />
        <div className="sb-item">
          GRID <strong>TP104-C/2</strong>
        </div>
        <div className="sb-item sb-divider" />
        <div className="sb-item">
          REV <strong>C</strong>
        </div>
        <div className="sb-item sb-divider" />
        <div className="sb-item">
          SHEET <strong>{data?.sheets.length ?? 0} / {data?.sheets.length ?? 0}</strong>
        </div>
        <div className="sb-item sb-divider" />
        <div className="sb-item">SCALE <strong>1:50</strong></div>
        <div className="sb-item sb-divider" />
        <div className="sb-item">
          PROJECT <strong style={{ color: "var(--cyan-deep)" }}>{data?.label?.toUpperCase() ?? "—"}</strong>
        </div>
        <div className="sb-spacer" />
        <div className="sb-item">
          TOOL <strong>{tool.toUpperCase()}</strong>
        </div>
        <div className="sb-item sb-divider" />
        <div className="sb-item">
          LLM <span className="sb-llm-badge">LOCAL · QWEN2.5-32B</span>
        </div>
        <div className="sb-item sb-divider" />
        <div className="sb-item">
          API CALLS <span className="sb-api">0</span>
        </div>
        <div className="sb-item sb-divider" />
        <div className="sb-item">
          SYNC <strong>just now</strong>
        </div>
      </div>
    </AppShell>
  );
}

function SheetThumb({ sheet, index }: { sheet: string; index: number }) {
  const active = useWorkspace((s) => s.activeSheet);
  const setSheet = useWorkspace((s) => s.setSheet);
  const isActive = active === sheet;
  return (
    <div
      className={`sheet-thumb${isActive ? " active" : ""}`}
      data-sheet={sheet}
      onClick={() => setSheet(sheet)}
    >
      <svg viewBox="0 0 60 40">
        <rect x="6" y="6" width="6" height="20" fill="#0E1B2C" opacity=".5" />
        <rect x="6" y="6" width="48" height="3" fill="#0E1B2C" opacity=".5" />
      </svg>
      <span className="st-num">S-{String(index + 1).padStart(2, "0")}</span>
      <span className="st-badge">{sheet}</span>
    </div>
  );
}
