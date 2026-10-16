"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
  { key: "layers", label: "Layers", title: "Cycle layer mode — all / structure / mech / flagged (L)", glyph: (
    <svg viewBox="0 0 24 24"><path d="M3 8 L12 4 L21 8 L12 12 Z"/><path d="M3 13 L12 17 L21 13"/><path d="M3 18 L12 22 L21 18"/></svg>
  )},
];

const INSPECT_TOOLS: Array<{ key: string; label: string; title: string; glyph: React.ReactNode }> = [
  { key: "measure", label: "Measure", title: "Measure distance — click 2 points (M)", glyph: (
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
  { key: "markup", label: "Markup", title: "Toggle markup overlays (Shift+O)", glyph: (
    <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
  )},
];

const ACTION_TOOLS: Array<{ key: string; label: string; title: string; glyph: React.ReactNode }> = [
  { key: "snapshot", label: "Snapshot", title: "Snapshot current view as PNG (S)", glyph: (
    <svg viewBox="0 0 24 24"><rect x="3" y="6" width="18" height="14" rx="1"/><path d="M8 6 L9.5 3.5 H14.5 L16 6"/><circle cx="12" cy="13" r="3.5"/></svg>
  )},
  { key: "undo", label: "Undo", title: "Undo last annotation change (U or Cmd+Z)", glyph: (
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

// Tool → CSS cursor (instant visual feedback so the user knows the rail is live).
const TOOL_CURSOR: Record<string, string> = {
  cursor:    "grab",
  zoom:      "zoom-in",
  fit:       "default",
  layers:    "default",
  measure:   "crosshair",
  identify:  "help",
  clash:     "pointer",
  annotate:  "crosshair",
  markup:    "default",
  snapshot:  "cell",
  undo:      "default",
  redo:      "default",
};

type LayerMode = "all" | "structural" | "mech" | "flagged";
const LAYER_MODES: LayerMode[] = ["all", "structural", "mech", "flagged"];
const LAYER_LABEL: Record<LayerMode, string> = {
  all: "All layers",
  structural: "Structural only",
  mech: "Mechanical only",
  flagged: "Flagged issues only",
};

export default function ProjectWorkspace({ params }: { params: { id: string } }) {
  const { id } = params;
  const [data, setData] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tool, setToolRaw] = useState("cursor");
  const setTool = useCallback((t: string) => {
    setToolRaw(t);
    if (t === "measure") {
      setMeasurePoints([]);
      setMeasurePreview(null);
    }
    if (t === "annotate") {
      // no-op — annotations are accumulated.
    }
    if (t === "snapshot") {
      // take the snapshot immediately; auto-revert to cursor after.
      exportSnapshotRef.current?.();
      setTimeout(() => setToolRaw("cursor"), 80);
    }
  }, []);
  const [running, setRunning] = useState(false);
  const openUpload = useModals((s) => s.openUpload);
  const activeSheet = useWorkspace((s) => s.activeSheet);
  const setSheets = useWorkspace((s) => s.setSheets);
  const nextSheet = useWorkspace((s) => s.nextSheet);
  const previousSheet = useWorkspace((s) => s.previousSheet);

  // Rail-driven state — all wired through DrawingCanvas via props.
  const [layerMode, setLayerMode] = useState<LayerMode>("all");
  const [clashVisible, setClashVisible] = useState(true);
  const [markupVisible, setMarkupVisible] = useState(true);
  const [annotations, setAnnotations] = useState<Array<{ id: string; x: number; y: number; sheet: string; n: number }>>([]);
  const [measurePoints, setMeasurePoints] = useState<Array<{ x: number; y: number }>>([]);
  const [measurePreview, setMeasurePreview] = useState<{ x: number; y: number } | null>(null);
  const undoStack = useRef<Array<{ annotations: typeof annotations }>>([]);
  const redoStack = useRef<Array<{ annotations: typeof annotations }>>([]);

  // Snapshot ref so the Snapshot button can call into the canvas without
  // threading the canvas DOM node up here.
  const exportSnapshotRef = useRef<(() => void) | null>(null);

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

  useEffect(() => {
    setSheets(data?.sheets ?? []);
  }, [data?.sheets, setSheets]);

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

  function addAnnotation(x: number, y: number, sheet: string) {
    setAnnotations((prev) => {
      undoStack.current.push({ annotations: prev });
      redoStack.current = [];
      const n = prev.length + 1;
      return [...prev, { id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, x, y, sheet, n }];
    });
  }

  function undo() {
    const last = undoStack.current.pop();
    if (!last) return;
    setAnnotations((cur) => {
      redoStack.current.push({ annotations: cur });
      return last.annotations;
    });
  }

  function redo() {
    const next = redoStack.current.pop();
    if (!next) return;
    setAnnotations((cur) => {
      undoStack.current.push({ annotations: cur });
      return next.annotations;
    });
  }

  function cycleLayerMode() {
    setLayerMode((cur) => LAYER_MODES[(LAYER_MODES.indexOf(cur) + 1) % LAYER_MODES.length]);
  }

  // Keyboard shortcuts — match the rail button tooltips.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) return;
      // Cmd/Ctrl combos first
      if (e.metaKey || e.ctrlKey) {
        if (e.key.toLowerCase() === "z") {
          e.preventDefault();
          if (e.shiftKey) redo(); else undo();
          return;
        }
        if (e.key.toLowerCase() === "y") {
          e.preventDefault();
          redo();
          return;
        }
        return;
      }
      const k = e.key.toLowerCase();
      if (k === "v") return setTool("cursor");
      if (k === "z") return setTool("zoom");
      if (k === "f") return setTool("fit");
      if (k === "l") return cycleLayerMode();
      if (k === "m") return setTool("measure");
      if (k === "i") return setTool("identify");
      if (k === "c") return setClashVisible((v) => !v);
      if (k === "a") return setTool("annotate");
      if (k === "o" && e.shiftKey) return setMarkupVisible((v) => !v);
      if (k === "s") return setTool("snapshot");
      if (k === "u") return undo();
      if (k === "y") return redo();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setTool]);

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
              onClick={() => {
                if (t.key === "fit") {
                  // fit is one-shot: tell the canvas to reset its zoom, then revert.
                  window.dispatchEvent(new CustomEvent("adv:fit-view"));
                  setTool("cursor");
                  return;
                }
                if (t.key === "layers") {
                  cycleLayerMode();
                  return;
                }
                setTool(t.key);
              }}
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
              onClick={() => {
                if (t.key === "clash") {
                  setClashVisible((v) => !v);
                  return;
                }
                setTool(t.key);
              }}
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
              className={`app-rail-btn${tool === t.key ? " active" : ""}${t.key === "markup" && markupVisible ? " active" : ""}`}
              data-tool={t.key}
              title={t.title}
              onClick={() => {
                if (t.key === "markup") {
                  setMarkupVisible((v) => !v);
                  return;
                }
                setTool(t.key);
              }}
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
              onClick={() => {
                if (t.key === "snapshot") {
                  setTool("snapshot"); // setTool handles the export + reverts
                  return;
                }
                if (t.key === "undo") { undo(); return; }
                if (t.key === "redo") { redo(); return; }
                setTool(t.key);
              }}
            >
              <span className="rb-glyph">{t.glyph}</span>
              <span className="rb-label">{t.label}</span>
            </button>
          ))}
          <div className="rail-mode">
            MODE
            <strong id="railMode">{(ALL_RAIL_KEYS.has(tool) ? tool : "cursor").toUpperCase()}</strong>
            {tool === "layers" && (
              <span className="rail-mode-sub">{LAYER_LABEL[layerMode]}</span>
            )}
            {tool === "measure" && measurePoints.length === 1 && measurePreview && (
              <span className="rail-mode-sub">Δ click again</span>
            )}
            {tool === "measure" && measurePoints.length >= 2 && (() => {
              const a = measurePoints[0]; const b = measurePoints[measurePoints.length - 1];
              const dx = b.x - a.x; const dy = b.y - a.y;
              return <span className="rail-mode-sub">{Math.round(Math.hypot(dx, dy))} mm</span>;
            })()}
            {tool === "annotate" && (
              <span className="rail-mode-sub">{annotations.length} pins</span>
            )}
            {annotations.length > 0 && tool !== "annotate" && (
              <span className="rail-mode-sub">{annotations.length}📍</span>
            )}
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
                <button className="vt-btn" type="button" id="vtPrev" title="Previous sheet ([)" onClick={previousSheet}>← Prev sheet</button>
                <button className="vt-btn" type="button" id="vtNext" title="Next sheet (])" onClick={nextSheet}>Next sheet →</button>
                {data && (
                  <span id="vtSheetMeta">
                    {data.sheets.length > 0
                      ? `Page ${Math.max(1, data.sheets.indexOf(activeSheet ?? "") + 1)} / ${data.sheets.length} · Sheet ${activeSheet ?? data.sheets[0]} · ${data.label}`
                      : `Sheet — · ${data.label}`}
                  </span>
                )}
              </div>
              <div className="vt-right">
                {data?.files?.map((f) => {
                  const meta = (f.parseMeta ?? {}) as {
                    entityCount?: number;
                    layers?: unknown[];
                    error?: string;
                  };
                  const status = f.parseStatus ?? "pending";
                  const label =
                    status === "ok" && meta.entityCount != null
                      ? `${f.discipline.toUpperCase()} · parsed ${meta.entityCount} entities / ${Array.isArray(meta.layers) ? meta.layers.length : 0} layers`
                      : status === "partial"
                        ? `${f.discipline.toUpperCase()} · partial parse (metadata only)`
                        : status === "failed"
                          ? `${f.discipline.toUpperCase()} · parser failed: ${meta.error ?? "unknown"}`
                          : status === "pending"
                            ? `${f.discipline.toUpperCase()} · parsing…`
                            : `${f.discipline.toUpperCase()} · ${status}`;
                  return (
                    <span
                      key={f.id}
                      className="vt-status"
                      title={JSON.stringify(f.parseMeta ?? {}, null, 2)}
                    >
                      <span className={`vt-status-dot vt-status-${status}`} />
                      {label}
                    </span>
                  );
                })}
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
                    issues={data.issues.filter((issue) => issue.sheet === (activeSheet ?? data.sheets[0]))}
                    tool={tool}
                    cursor={TOOL_CURSOR[tool] ?? "default"}
                    layerMode={layerMode}
                    clashVisible={clashVisible}
                    markupVisible={markupVisible}
                    annotations={annotations}
                    onAddAnnotation={addAnnotation}
                    measurePoints={measurePoints}
                    measurePreview={measurePreview}
                    onMeasurePoint={(p) => setMeasurePoints((pts) => [...pts, p])}
                    onMeasurePreview={(p) => setMeasurePreview(p)}
                    onMeasureReset={() => { setMeasurePoints([]); setMeasurePreview(null); }}
                    registerSnapshot={(fn) => { exportSnapshotRef.current = fn; }}
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
          <IssueInspector
            issues={data.issues}
            summary={data.summary}
            checks={data.checks}
            events={data.events}
          />
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
