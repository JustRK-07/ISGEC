"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { EntityOut, IssueOut } from "@/lib/api";
import { useWorkspace } from "@/lib/store";
import {
  screenToWorld as viewportToWorld,
  type Viewport,
  zoomAt,
} from "@/lib/viewport";

// Discipline + kind → stroke/fill. Matches the prototype + reference PDF
// (superimposed.pdf: STR in cyan + magenta, MECH in cyan ducts + rust pipes).
const KIND_STYLE: Record<string, { stroke: string; fill: string; weight: number }> = {
  beam:      { stroke: "#C84B1F", fill: "rgba(200,75,31,0.10)", weight: 2.0 },
  column:    { stroke: "#0E1B2C", fill: "rgba(14,27,44,0.18)",  weight: 1.5 },
  brace:     { stroke: "#C68B1F", fill: "rgba(198,139,31,0.18)", weight: 1.5 },
  duct:      { stroke: "#1E88A8", fill: "rgba(30,136,168,0.28)", weight: 2.0 },
  pipe:      { stroke: "#C84B1F", fill: "rgba(200,75,31,0.18)",  weight: 3.0 },
  equipment: { stroke: "#C84B1F", fill: "rgba(200,75,31,0.18)", weight: 1.8 },
  sleeve:    { stroke: "#1E88A8", fill: "rgba(30,136,168,0.10)", weight: 1.5 },
  opening:   { stroke: "#F59E0B", fill: "rgba(245,158,11,0.18)", weight: 1.8 },
  text:      { stroke: "#0E1B2C", fill: "rgba(14,27,44,0.85)",   weight: 1.0 },
  line:      { stroke: "#475569", fill: "rgba(71,85,105,0.10)",  weight: 1.0 },
  block:     { stroke: "#94A3B8", fill: "rgba(148,163,184,0.12)",weight: 1.0 },
  "grid-bubble": { stroke: "#0EA5A4", fill: "transparent",       weight: 1.4 },

  // Extended kinds for real-DWG output (MECH layers + STR Revit block names).
  phantom:     { stroke: "#7B61FF", fill: "rgba(123,97,255,0.10)", weight: 1.0 },
  hidden:      { stroke: "#94A3B8", fill: "transparent",            weight: 1.0 },
  centerline:  { stroke: "#C68B1F", fill: "transparent",            weight: 1.0 },
  dimension:   { stroke: "#5C6B82", fill: "rgba(92,107,130,0.10)",  weight: 1.0 },
  annotation:  { stroke: "#475569", fill: "rgba(71,85,105,0.10)",   weight: 1.0 },
  gridline:    { stroke: "#0EA5A4", fill: "rgba(14,165,164,0.10)",  weight: 1.0 },
  unknown:   { stroke: "#5C6B82", fill: "rgba(92,107,130,0.10)", weight: 1.0 },
};

/** Compute the bounding box of an entity in world-mm. Used both by
 *  draw() (to compute auto-fit and hit-rect placement) and by
 *  screenToWorld (to map a click back into the world frame). */
function entityExtent(e: EntityOut): { x0: number; y0: number; x1: number; y1: number } | null {
  const meta = e.meta as
    | { startPoint?: { x: number; y: number }; endPoint?: { x: number; y: number }; radius?: number }
    | null;
  if (meta?.startPoint && meta?.endPoint) {
    const { x: x0, y: y0 } = meta.startPoint;
    const { x: x1, y: y1 } = meta.endPoint;
    return { x0: Math.min(x0, x1), y0: Math.min(y0, y1), x1: Math.max(x0, x1), y1: Math.max(y0, y1) };
  }
  const w = Math.abs(e.w_mm ?? 0);
  const h = Math.abs(e.h_mm ?? 0);
  if (e.x_mm == null || e.y_mm == null) return null;
  return { x0: e.x_mm - w / 2, y0: e.y_mm - h / 2, x1: e.x_mm + w / 2, y1: e.y_mm + h / 2 };
}

// Category → suggested fix (one-line engineering guidance surfaced in tooltip).
const SUGGESTED_FIX: Record<string, string> = {
  "polygon-clash":   "Offset DUCT 75 mm vertically or reroute around STB/STC zone.",
  "missing-required":"Add required sleeve/opening per STR spec; verify DN ≥ 100 mm.",
  "clearance-zone":  "Maintain 840 mm service clearance; shift AHU/FCU east by ≥ 340 mm.",
  "size":            "Verify per-axis tolerance; respec if Δ > ±25 mm.",
  "position":        "Confirm grid registration; re-anchor element to nearest gridline.",
  "elevation":       "Re-check T.O.S. drift; align within ±50 mm of structural beam top.",
};

export type DrawingTab = "str" | "mech" | "overlay";

interface Props {
  entities: EntityOut[];
  sheets: string[];
  issues?: IssueOut[];
  /** Which rail tool is active — drives cursor + click semantics + overlays. */
  tool?: string;
  /** CSS cursor string for the current tool (or computed from `tool`). */
  cursor?: string;
  /** Layer filter from the rail Layers button. */
  layerMode?: "all" | "structural" | "mech" | "flagged";
  /** When false, hide issue flag rectangles on the canvas. */
  clashVisible?: boolean;
  /** When false, hide user-added annotation pins (markup overlays). */
  markupVisible?: boolean;
  /** Pins dropped with the Annotate tool. */
  annotations?: Array<{ id: string; x: number; y: number; sheet: string; n: number }>;
  /** Called with world coords + active sheet when the user clicks with the Annotate tool. */
  onAddAnnotation?: (x: number, y: number, sheet: string) => void;
  /** Measure-tool state: 0..2 click points + a hover preview. */
  measurePoints?: Array<{ x: number; y: number }>;
  measurePreview?: { x: number; y: number } | null;
  onMeasurePoint?: (p: { x: number; y: number }) => void;
  onMeasurePreview?: (p: { x: number; y: number } | null) => void;
  onMeasureReset?: () => void;
  /** Let the page subscribe to "snapshot now" so the rail Snapshot button works. */
  registerSnapshot?: (fn: () => void) => void;
}

interface HoveredIssue {
  issue: IssueOut;
  x: number;
  y: number;
}

export function DrawingCanvas({
  entities,
  sheets,
  issues = [],
  tool = "cursor",
  cursor,
  layerMode = "all",
  clashVisible = true,
  markupVisible = true,
  annotations = [],
  onAddAnnotation,
  measurePoints = [],
  measurePreview = null,
  onMeasurePoint,
  onMeasurePreview,
  onMeasureReset,
  registerSnapshot,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const activeSheet = useWorkspace((state) => state.activeSheet) ?? sheets[0] ?? "0001";
  const setActiveSheet = useWorkspace((state) => state.setSheet);
  const selectedIssueId = useWorkspace((state) => state.selectedIssueId);
  const [activeTab, setActiveTab] = useState<DrawingTab>("overlay");
  const [zoom, setZoom] = useState(1);          // user-controlled multiplier on auto-fit
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
  const viewportRef = useRef<Viewport | null>(null);
  const dragRef = useRef<{ pointerId: number; x: number; y: number; moved: boolean } | null>(null);
  const [spacePressed, setSpacePressed] = useState(false);
  const [hovered, setHovered] = useState<HoveredIssue | null>(null);
  const [clickedEntity, setClickedEntity] = useState<EntityOut | null>(null);
  const [pinPrompt, setPinPrompt] = useState<{ sx: number; sy: number } | null>(null);

  // Issue flag rectangles in *screen* coords, recomputed every redraw,
  // used by the canvas mouse handler to detect hovers.
  const issueScreenRects = useRef<Array<{ issue: IssueOut; rect: { x: number; y: number; w: number; h: number } }>>([]);

  // Filter entities to active sheet + tab. The OVERLAY tab keeps both
  // disciplines in the list because the canvas will render them in
  // separate regions (split-view); STR/MECH tabs filter to the active
  // discipline so the auto-fit bbox is computed only on that discipline's
  // geometry — without this, MECH outliers at kilometre offsets would
  // squash the entire viewport. The Layers rail button overrides this
  // with a coarser filter: structural-only / mech-only / flagged-only.
  const flaggedEntityIds = new Set(
    issues.flatMap((issue) => [issue.str_ref, issue.mech_ref]).filter((value): value is string => Boolean(value)),
  );
  const visible = entities.filter((e) => {
    if (e.sheet !== activeSheet) return false;
    if (activeTab === "str" && layerMode !== "mech") {
      if (layerMode === "structural") {/* fall through */}
      if (layerMode === "flagged" && !flaggedEntityIds.has(e.label ?? "")) return false;
    } else if (activeTab === "mech" && layerMode !== "structural") {
      if (layerMode === "mech") {/* fall through */}
      if (layerMode === "flagged" && !flaggedEntityIds.has(e.label ?? "")) return false;
    } else if (activeTab === "overlay") {
      if (layerMode === "structural" && e.discipline !== "str") return false;
      if (layerMode === "mech" && e.discipline !== "mech") return false;
      if (layerMode === "flagged" && !flaggedEntityIds.has(e.label ?? "")) return false;
    }
    if (activeTab === "str") return e.discipline === "str";
    if (activeTab === "mech") return e.discipline === "mech";
    return true;
  });

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = container.getBoundingClientRect();
    const cssW = Math.max(1, Math.floor(rect.width));
    const cssH = Math.max(1, Math.floor(rect.height));
    canvas.width = cssW * dpr;
    canvas.height = cssH * dpr;
    canvas.style.width = `${cssW}px`;
    canvas.style.height = `${cssH}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Paper background + faint 28-px grid.
    ctx.fillStyle = "#F2EFE6";
    ctx.fillRect(0, 0, cssW, cssH);
    ctx.strokeStyle = "rgba(14, 27, 44, 0.07)";
    ctx.lineWidth = 1;
    for (let x = 0; x < cssW; x += 28) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, cssH); ctx.stroke();
    }
    for (let y = 0; y < cssH; y += 28) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(cssW, y); ctx.stroke();
    }

    // (No hover-to-show labels — labels only appear when the user clicks
    // an entity; that picked entity's full description then opens in the
    // info panel below.)


    // Robust bbox via cluster detection. Drawings often have multiple
    // coordinate clusters (title block at 0,0 vs building geometry at
    // ±5M mm). We find the densest 50-km-radius cluster in the data and
    // use its bounding range as the viewport. A "cluster" here is a
    // window of width 50,000 mm centred on a candidate point that
    // contains the most coordinate values — by 50 km radius we capture
    // even the small equipment drawings on the MECH sheet while still
    // skipping the half-a-million mm outlier band.
    function findDensestCluster(values: number[], radius: number): [number, number] | null {
      if (values.length === 0) return null;
      const sorted = [...values].sort((a, b) => a - b);
      let bestCount = 0;
      let bestCenter = sorted[0];
      // Slide a window of width `radius` across the sorted values and pick
      // the window containing the most points.
      let lo = 0;
      for (let hi = 0; hi < sorted.length; hi++) {
        // Advance the lower bound to keep window width <= radius.
        while (sorted[hi] - sorted[lo] > radius) lo++;
        const count = hi - lo + 1;
        if (count > bestCount) {
          bestCount = count;
          bestCenter = (sorted[lo] + sorted[hi]) / 2;
        }
      }
      const lo2 = bestCenter - radius;
      const hi2 = bestCenter + radius;
      return [lo2, hi2];
    }
    function robustBBox(values: number[]): [number, number] | null {
      if (values.length === 0) return null;
      // Try cluster detection at 50 km radius first. If the data has at
      // least a couple of hundred points within some 50-km window, that
      // window is the real drawing area; everything else is title chrome
      // or dimensional outliers.
      const cluster = findDensestCluster(values, 50_000);
      if (!cluster) return null;
      const sorted = [...values].sort((a, b) => a - b);
      const trimmed = sorted.filter((v) => v >= cluster[0] && v <= cluster[1]);
      if (trimmed.length < 8) {
        // Insufficient data within the cluster; fall back to hard cap.
        const median = sorted[Math.floor(sorted.length / 2)];
        const lo = median - 50_000;
        const hi = median + 50_000;
        const t = sorted.filter((v) => v >= lo && v <= hi);
        return t.length >= 4 ? [t[0], t[t.length - 1]] : [sorted[0], sorted[sorted.length - 1]];
      }
      return [trimmed[0], trimmed[trimmed.length - 1]];
    }

    // Compute a viewport in CSS pixels: STR/MECH tabs use the full canvas;
    // OVERLAY splits into top (STR) + bottom (MECH) sub-regions because the
    // two disciplines don't share a BIM coordinate frame and one would
    // otherwise crush the other.
    interface Region {
      x: number;
      y: number;
      w: number;
      h: number;
    }
    interface Pass {
      label: string;
      region: Region;
      entities: EntityOut[];
    }
    const fullRegion: Region = { x: 0, y: 0, w: cssW, h: cssH };
    let passes: Pass[];
    if (activeTab === "overlay") {
      const top = cssH / 2;
      passes = [
        {
          label: "STRUCTURAL",
          region: { x: 0, y: 0, w: cssW, h: top - 2 },
          entities: visible.filter((e) => e.discipline === "str"),
        },
        {
          label: "MECHANICAL",
          region: { x: 0, y: top + 2, w: cssW, h: cssH - top - 2 },
          entities: visible.filter((e) => e.discipline === "mech"),
        },
      ];
    } else {
      passes = [{ label: activeTab.toUpperCase(), region: fullRegion, entities: visible }];
    }

    // Sub-region separator for overlay tab.
    if (activeTab === "overlay") {
      ctx.fillStyle = "#0E1B2C";
      ctx.fillRect(0, cssH / 2 - 1, cssW, 2);
    }

    const issueRects: typeof issueScreenRects.current = [];
    const MAX_VISIBLE_ISSUES = 8;
    const sortedIssues = [...issues]
      .sort((a, b) => {
        const sev = (s: IssueOut) => (s.severity === "high" ? 0 : s.severity === "medium" ? 1 : 2);
        const sa = sev(a), sb = sev(b);
        if (sa !== sb) return sa - sb;
        return a.code.localeCompare(b.code);
      })
      .slice(0, MAX_VISIBLE_ISSUES);
    const flagOffsets: Array<[number, number]> = [
      [0, 0],
      [400, 600],
      [-400, -600],
      [600, -300],
      [-600, 300],
      [800, 800],
      [-800, -800],
      [1200, 0],
    ];

    // Render each pass (one for STR/MECH tab, two for OVERLAY tab).
    entityHitRects.current = [];
    for (const pass of passes) {
      if (pass.entities.length === 0) continue;
      const { region, label: passLabel } = pass;

      // Auto-fit bbox for this pass. Includes a hard coordinate clamp as a
      // last resort for heavily-polluted MECH data. We exclude "auxiliary"
      // kinds (dimension/centerline/hidden/phantom/text) from the bbox
      // because libredwg emits thousands of them at kilometre offsets —
      // including them would squash the actual drawing into a corner.
      const AUX_KINDS = new Set([
        "dimension",
        "centerline",
        "hidden",
        "phantom",
        "annotation",
        "text",
        "gridline",
      ]);
      const xs: number[] = [];
      const ys: number[] = [];
      for (const e of pass.entities) {
        if (AUX_KINDS.has(e.kind)) continue;
        const ext = entityExtent(e);
        if (!ext) continue;
        xs.push(ext.x0, ext.x1);
        ys.push(ext.y0, ext.y1);
      }
      if (xs.length === 0) continue;
      let xb = robustBBox(xs);
      let yb = robustBBox(ys);
      if (!xb || !yb || xb[1] - xb[0] === 0 || yb[1] - yb[0] === 0) {
        // Fallback: clamp to 100 m radius around the centroid.
        const cx0 = xs.reduce((a, b) => a + b, 0) / xs.length;
        const cy0 = ys.reduce((a, b) => a + b, 0) / ys.length;
        xb = [cx0 - 50_000, cx0 + 50_000];
        yb = [cy0 - 50_000, cy0 + 50_000];
      }
      const minX = xb[0];
      const maxX = xb[1];
      const minY = yb[0];
      const maxY = yb[1];
      const margin = 0.12;
      const availW = region.w * (1 - margin * 2);
      const availH = region.h * (1 - margin * 2);
      const bboxW = maxX - minX;
      const bboxH = maxY - minY;
      const baseScale = Math.min(availW / bboxW, availH / bboxH);
      const scale = baseScale * zoom;
      const offsetX = region.x + region.w / 2 - ((minX + maxX) / 2) * scale + panOffset.x;
      const offsetY = region.y + region.h / 2 - ((minY + maxY) / 2) * scale + panOffset.y;
      const passViewport: Viewport = {
        scale,
        tx: offsetX,
        ty: offsetY,
        width: region.w,
        height: region.h,
      };
      if (!viewportRef.current || activeTab !== "overlay") viewportRef.current = passViewport;

      const toScreen = (mx: number, my: number) => ({
        x: mx * scale + offsetX,
        y: my * scale + offsetY,
      });

      // Push an on-screen hit-rect for an entity. The click handler picks
      // the smallest such rect that contains the cursor (so a beam inside
      // a slab is preferred over the whole slab).
      const pushHit = (entity: EntityOut, x: number, y: number, w: number, h: number) => {
        entityHitRects.current.push({
          entity,
          rect: { x: x - w / 2, y: y - h / 2, w, h },
        });
      };

      // Draw a text/annotation entity at its insertion point, with a halo
      // so it stays legible when it overlaps geometry. We always render
      // text but clamp the on-screen size between 11 and 28 CSS px —
      // without a screen-space floor, a 3mm cap-height projects to
      // < 1 px on a 24km auto-fit view and disappears. The cap keeps
      // zoomed-in labels from overwhelming the geometry.
      const drawTextLabel = (entity: EntityOut) => {
        const lbl = entity.label ?? "";
        if (!lbl) return;
        const lblLen = lbl.length;
        // World-mm cap-height: short labels are dimensions (2.5mm),
        // grid/beam labels ≈ 3.5mm, sheet titles ≈ 5mm.
        const fontMm = lblLen <= 4 ? 2.5 : lblLen <= 8 ? 3.5 : 5.0;
        const worldPx = fontMm * scale;
        // Screen-space floor so labels stay readable at any zoom level.
        const fontPx = Math.max(11, Math.min(28, worldPx));
        const sp = toScreen(entity.x_mm ?? 0, entity.y_mm ?? 0);
        ctx.save();
        ctx.translate(sp.x, sp.y);
        ctx.rotate(((entity.rotation ?? 0) * Math.PI) / 180);
        ctx.font = `bold ${fontPx}px JetBrains Mono, monospace`;
        ctx.textAlign = "left";
        ctx.textBaseline = "alphabetic";
        // Paper halo for legibility on top of geometry
        ctx.lineJoin = "round";
        ctx.strokeStyle = "rgba(242, 239, 230, 0.92)";
        ctx.lineWidth = Math.max(2, fontPx * 0.18);
        ctx.strokeText(lbl, 0, 0);
        ctx.fillStyle = "#0E1B2C";
        ctx.fillText(lbl, 0, 0);
        ctx.restore();
        // Hit-rect approximates the on-screen label footprint so a
        // click anywhere on the (rotated) text still hits the entity.
        const w = lblLen * fontPx * 0.62;
        const h = fontPx;
        pushHit(entity, sp.x + w / 2, sp.y, Math.abs(w), Math.abs(h));
      };

      // Background for the region + label header
      ctx.fillStyle = "#F2EFE6";
      ctx.fillRect(region.x, region.y, region.w, region.h);
      ctx.fillStyle = "rgba(14, 27, 44, 0.07)";
      ctx.font = "10px JetBrains Mono, monospace";
      const headerText = `${passLabel} · ${pass.entities.length} entities`;
      ctx.fillStyle = "#0E1B2C";
      ctx.fillText(headerText, region.x + 8, region.y + 16);

      // Pass A: STR entities of this region.
      for (const entity of pass.entities) {
        if (entity.discipline !== "str") continue;
        const style = KIND_STYLE[entity.kind] ?? KIND_STYLE.unknown;
        const s = toScreen(entity.x_mm ?? 0, entity.y_mm ?? 0);
        const w = Math.abs(entity.w_mm ?? 0) * scale;
        const h = Math.abs(entity.h_mm ?? 0) * scale;
        ctx.strokeStyle = style.stroke;
        ctx.fillStyle = style.fill;
        ctx.lineWidth = style.weight;

        if (entity.kind === "text" || entity.kind === "annotation") {
          drawTextLabel(entity);
          continue;
        }

        const meta = entity.meta;
        if (meta?.vertices && meta.vertices.length >= 2) {
          const points = meta.vertices.map((point) => toScreen(point.x, point.y));
          ctx.beginPath();
          ctx.moveTo(points[0].x, points[0].y);
          for (const point of points.slice(1)) ctx.lineTo(point.x, point.y);
          if (meta.closed) ctx.closePath();
          if (meta.closed) ctx.fill();
          ctx.stroke();
          const x0 = Math.min(...points.map((point) => point.x));
          const y0 = Math.min(...points.map((point) => point.y));
          const x1 = Math.max(...points.map((point) => point.x));
          const y1 = Math.max(...points.map((point) => point.y));
          pushHit(entity, (x0 + x1) / 2, (y0 + y1) / 2, Math.max(12, x1 - x0), Math.max(12, y1 - y0));
          continue;
        }
        if (meta?.center && meta.radius != null) {
          const center = toScreen(meta.center.x, meta.center.y);
          const radius = Math.abs(meta.radius * scale);
          const isArc = meta.startAngle != null && meta.endAngle != null;
          ctx.beginPath();
          ctx.arc(
            center.x,
            center.y,
            radius,
            isArc ? (meta.startAngle! * Math.PI) / 180 : 0,
            isArc ? (meta.endAngle! * Math.PI) / 180 : Math.PI * 2,
          );
          ctx.stroke();
          pushHit(entity, center.x, center.y, Math.max(12, radius * 2), Math.max(12, radius * 2));
          continue;
        }
        if (meta?.startPoint && meta?.endPoint) {
          const a = toScreen(meta.startPoint.x, meta.startPoint.y);
          const b = toScreen(meta.endPoint.x, meta.endPoint.y);
          if (entity.kind === "brace") ctx.setLineDash([6, 4]);
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
          ctx.setLineDash([]);
          // Hit-rect for the line (12px tube so it's clickable along its length).
          const x0 = Math.min(a.x, b.x) - 6;
          const y0 = Math.min(a.y, b.y) - 6;
          const x1 = Math.max(a.x, b.x) + 6;
          const y1 = Math.max(a.y, b.y) + 6;
          pushHit(entity, (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0);
          continue;
        }

        if (entity.kind === "column") {
          const side = Math.max(w, h, 24);
          ctx.fillRect(s.x - side / 2, s.y - side / 2, side, side);
          ctx.strokeRect(s.x - side / 2, s.y - side / 2, side, side);
          pushHit(entity, s.x, s.y, side, side);
          continue;
        }

        if (entity.kind === "opening" || entity.kind === "duct" || entity.kind === "beam") {
          ctx.fillRect(s.x - w / 2, s.y - h / 2, w, h);
          ctx.strokeRect(s.x - w / 2, s.y - h / 2, w, h);
          pushHit(entity, s.x, s.y, w, h);
          continue;
        }

        if (entity.kind === "phantom" || entity.kind === "hidden" || entity.kind === "centerline" || entity.kind === "dimension" || entity.kind === "gridline") {
          ctx.beginPath();
          ctx.arc(s.x, s.y, 4, 0, Math.PI * 2);
          ctx.stroke();
          pushHit(entity, s.x, s.y, 12, 12);
          continue;
        }

        ctx.fillRect(s.x - 6, s.y - 6, 12, 12);
        pushHit(entity, s.x, s.y, 12, 12);
      }

      // Pass B: MECH entities in this region (alpha 0.88).
      ctx.globalAlpha = 0.88;
      for (const entity of pass.entities) {
        if (entity.discipline !== "mech") continue;
        const style = KIND_STYLE[entity.kind] ?? KIND_STYLE.unknown;
        const s = toScreen(entity.x_mm ?? 0, entity.y_mm ?? 0);
        const w = Math.abs(entity.w_mm ?? 0) * scale;
        const h = Math.abs(entity.h_mm ?? 0) * scale;
        ctx.strokeStyle = style.stroke;
        ctx.fillStyle = style.fill;
        ctx.lineWidth = style.weight;

        const meta = entity.meta as
          | { startPoint?: { x: number; y: number }; endPoint?: { x: number; y: number }; radius?: number }
          | null;

        if (meta?.startPoint && meta?.endPoint && entity.kind === "pipe") {
          const a = toScreen(meta.startPoint.x, meta.startPoint.y);
          const b = toScreen(meta.endPoint.x, meta.endPoint.y);
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
          const x0 = Math.min(a.x, b.x) - 6;
          const y0 = Math.min(a.y, b.y) - 6;
          const x1 = Math.max(a.x, b.x) + 6;
          const y1 = Math.max(a.y, b.y) + 6;
          pushHit(entity, (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0);
          continue;
        }

        if (entity.kind === "sleeve") {
          const r = (meta?.radius ?? 125) * scale;
          ctx.beginPath();
          ctx.arc(s.x, s.y, r, 0, Math.PI * 2);
          ctx.stroke();
          pushHit(entity, s.x, s.y, r * 2, r * 2);
          continue;
        }

        if (entity.kind === "equipment") {
          ctx.setLineDash([6, 4]);
          ctx.fillRect(s.x - w / 2, s.y - h / 2, w, h);
          ctx.strokeRect(s.x - w / 2, s.y - h / 2, w, h);
          ctx.setLineDash([]);
          pushHit(entity, s.x, s.y, w, h);
          continue;
        }

        if (entity.kind === "text" || entity.kind === "annotation") {
          drawTextLabel(entity);
          continue;
        }

        if (entity.kind === "phantom" || entity.kind === "hidden" || entity.kind === "centerline" || entity.kind === "dimension" || entity.kind === "gridline") {
          ctx.beginPath();
          ctx.arc(s.x, s.y, 4, 0, Math.PI * 2);
          ctx.stroke();
          pushHit(entity, s.x, s.y, 12, 12);
          continue;
        }

        ctx.fillRect(s.x - w / 2, s.y - h / 2, w, h);
        ctx.strokeRect(s.x - w / 2, s.y - h / 2, w, h);
        pushHit(entity, s.x, s.y, w, h);
      }
      ctx.globalAlpha = 1;

      // Issue flags scoped to entities in this region — only when clashVisible is on.
      if (clashVisible) for (const issue of sortedIssues) {
        const target =
          pass.entities.find((e) => e.label === issue.mech_ref) ??
          pass.entities.find((e) => e.label === issue.str_ref) ??
          null;
        if (!target) {
          // Issue is for the *other* discipline — skip in split regions so
          // the flag stays with the entity it points at.
          if (
            (issue.str_ref && passLabel === "MECHANICAL") ||
            (issue.mech_ref && passLabel === "STRUCTURAL")
          ) continue;
        }
        const tx = target?.x_mm ?? (minX + (maxX - minX) / 2);
        const ty = target?.y_mm ?? (minY + (maxY - minY) / 2);
        const ix = sortedIssues.indexOf(issue);
        const [dx, dy] = flagOffsets[ix] ?? [0, 0];
        const cx = tx + dx;
        const cy = ty + dy;
        const w = Math.max(target ? entityExtent(target)?.x1! - entityExtent(target)?.x0! : 1500, 1000);
        const h = Math.max(target ? entityExtent(target)?.y1! - entityExtent(target)?.y0! : 1000, 800);
        const s = toScreen(cx, cy);
        const sw = w * scale, sh = h * scale;
        const isSelected = issue.id === selectedIssueId;
        ctx.strokeStyle = isSelected ? "#0EA5A4" : "#C84B1F";
        ctx.fillStyle = isSelected ? "rgba(14,165,164,0.16)" : "rgba(200,75,31,0.10)";
        ctx.lineWidth = isSelected ? 4 : 2.5;
        ctx.setLineDash([8, 4]);
        ctx.fillRect(s.x - sw / 2, s.y - sh / 2, sw, sh);
        ctx.strokeRect(s.x - sw / 2, s.y - sh / 2, sw, sh);
        ctx.setLineDash([]);
        const label = issue.code;
        ctx.font = "bold 11px JetBrains Mono, monospace";
        const tw = ctx.measureText(label).width + 10;
        ctx.fillStyle = "#C84B1F";
        ctx.fillRect(s.x - sw / 2, s.y - sh / 2 - 16, tw, 16);
        ctx.fillStyle = "#F2EFE6";
        ctx.fillText(label, s.x - sw / 2 + 5, s.y - sh / 2 - 4);
        issueRects.push({ issue, rect: { x: s.x - sw / 2, y: s.y - sh / 2, w: sw, h: sh } });
      }

      // Region label & sheet number footer.
      ctx.fillStyle = "rgba(14, 27, 44, 0.08)";
      ctx.font = "10px JetBrains Mono, monospace";
      ctx.fillText(
        `bbox ${Math.round(minX)}..${Math.round(maxX)} × ${Math.round(minY)}..${Math.round(maxY)} mm · 1:${Math.round(100 / (scale * 1000)) || 50}`,
        region.x + 8,
        region.y + region.h - 10,
      );
    }

    issueScreenRects.current = issueRects;

    // Annotation pins (Annotate tool + Markup visibility). Each pin is
    // a numbered orange droplet — same colour as the rail button so the
    // connection is obvious.
    if (markupVisible) {
      for (const pin of annotations) {
        if (pin.sheet !== activeSheet) continue;
        // Pins use the active sheet's auto-fit bbox; simpler than
        // re-deriving per-pass transforms. Adequate at this scale.
        const wp = pin;
        // Compute world→screen using the same transform as the first pass;
        // we re-derive min/max from the visible set already in closure.
        // Simpler: assume pin coords are inside the STR bbox and use its transform.
        // For OVERLAY/MECH passes with non-shared bbox, we just project at
        // STR scale; pins render in the upper region. Acceptable approximation.
        // Take first pass transform by re-computing quickly:
        // (the canonical transform lives inside the pass loop — we export it
        //  by scanning the active-sheet entities here.)
        let loX = Infinity, hiX = -Infinity, loY = Infinity, hiY = -Infinity;
        for (const e of entities) {
          if (e.sheet !== activeSheet) continue;
          const ext = entityExtent(e);
          if (!ext) continue;
          loX = Math.min(loX, ext.x0); hiX = Math.max(hiX, ext.x1);
          loY = Math.min(loY, ext.y0); hiY = Math.max(hiY, ext.y1);
        }
        if (!isFinite(loX)) continue;
        const availW = cssW * 0.76;
        const availH = cssH * 0.76;
        const baseScale = Math.min(availW / (hiX - loX || 1), availH / (hiY - loY || 1));
        const s = baseScale * zoom;
        const dx0 = cssW / 2 - ((loX + hiX) / 2) * s;
        const dy0 = cssH / 2 - ((loY + hiY) / 2) * s;
        const x = wp.x * s + dx0;
        const y = wp.y * s + dy0;
        // Skip pins outside the canvas
        if (x < -20 || x > cssW + 20 || y < -20 || y > cssH + 20) continue;
        ctx.save();
        // Pin droplet
        ctx.beginPath();
        ctx.arc(x, y, 9, 0, Math.PI * 2);
        ctx.fillStyle = "#F59E0B";
        ctx.fill();
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = "#0E1B2C";
        ctx.stroke();
        // Pin number
        ctx.font = "bold 11px JetBrains Mono, monospace";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "#0E1B2C";
        ctx.fillText(String(pin.n), x, y + 0.5);
        ctx.restore();
      }
    }

    // Measure-tool overlay: a teal line + dimension label. Only renders
    // while the Measure rail tool is active (otherwise the user has no
    // mental context for the segments).
    if (tool === "measure" && (measurePoints.length > 0 || measurePreview)) {
      const a = measurePoints[0];
      const b = measurePoints[measurePoints.length - 1] ?? measurePreview;
      if (a && b) {
        // Same transform as pin projection (active-sheet auto-fit).
        let loX = Infinity, hiX = -Infinity, loY = Infinity, hiY = -Infinity;
        for (const e of entities) {
          if (e.sheet !== activeSheet) continue;
          const ext = entityExtent(e);
          if (!ext) continue;
          loX = Math.min(loX, ext.x0); hiX = Math.max(hiX, ext.x1);
          loY = Math.min(loY, ext.y0); hiY = Math.max(hiY, ext.y1);
        }
        if (isFinite(loX)) {
          const availW = cssW * 0.76;
          const availH = cssH * 0.76;
          const baseScale = Math.min(availW / (hiX - loX || 1), availH / (hiY - loY || 1));
          const s = baseScale * zoom;
          const dx0 = cssW / 2 - ((loX + hiX) / 2) * s;
          const dy0 = cssH / 2 - ((loY + hiY) / 2) * s;
          const ax = a.x * s + dx0, ay = a.y * s + dy0;
          const bx = b.x * s + dx0, by = b.y * s + dy0;
          // Anchor markers
          ctx.fillStyle = "#0E1B2C";
          for (const [px, py] of [[ax, ay], [bx, by]]) {
            ctx.beginPath();
            ctx.arc(px, py, 4, 0, Math.PI * 2);
            ctx.fill();
          }
          // Live measure line (teal, dashed while previewing)
          const isPreview = measurePoints.length < 2;
          ctx.save();
          ctx.lineWidth = 2;
          if (isPreview) ctx.setLineDash([6, 4]);
          ctx.strokeStyle = "#0EA5A4";
          ctx.beginPath();
          ctx.moveTo(ax, ay);
          ctx.lineTo(bx, by);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.restore();
          // Distance label
          const dMm = Math.hypot(a.x - b.x, a.y - b.y);
          const label = `${Math.round(dMm)} mm`;
          ctx.font = "bold 12px JetBrains Mono, monospace";
          const tw = ctx.measureText(label).width + 12;
          const lx = (ax + bx) / 2;
          const ly = (ay + by) / 2;
          ctx.fillStyle = "rgba(14,165,164,0.92)";
          ctx.fillRect(lx - tw / 2, ly - 9, tw, 18);
          ctx.fillStyle = "#F2EFE6";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(label, lx, ly + 0.5);
        }
      }
    }

    // Sheet label bottom-right of full canvas.
    ctx.fillStyle = "#5C6B82";
    ctx.font = "10px JetBrains Mono, monospace";
    const totalIssues = issues.length;
    const issueNote = totalIssues > MAX_VISIBLE_ISSUES
      ? ` · showing top ${MAX_VISIBLE_ISSUES}/${totalIssues} issues`
      : "";
    ctx.fillText(
      `SHEET ${activeSheet} · ${visible.length} entities${issueNote}`,
      8,
      cssH - 8,
    );
  }, [visible, issues, activeSheet, selectedIssueId, zoom, panOffset, clickedEntity, tool, layerMode, clashVisible, markupVisible, annotations, measurePoints, measurePreview]);

  useEffect(() => {
    const selected = issues.find((issue) => issue.id === selectedIssueId);
    if (selected?.sheet && selected.sheet !== activeSheet && sheets.includes(selected.sheet)) {
      setActiveSheet(selected.sheet);
    }
  }, [activeSheet, issues, selectedIssueId, setActiveSheet, sheets]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.code === "Space") setSpacePressed(true);
    }
    function onKeyUp(event: KeyboardEvent) {
      if (event.code === "Space") setSpacePressed(false);
    }
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    function handleWheel(event: WheelEvent) {
      event.preventDefault();
      const rect = canvas!.getBoundingClientRect();
      const anchor = { x: event.clientX - rect.left, y: event.clientY - rect.top };
      const current = viewportRef.current;
      const factor = event.deltaY < 0 ? 1.15 : 1 / 1.15;
      if (current) {
        const next = zoomAt(current, current.scale * factor, anchor);
        setPanOffset((offset) => ({
          x: offset.x + next.tx - current.tx,
          y: offset.y + next.ty - current.ty,
        }));
      }
      setZoom((value) => Math.max(0.1, Math.min(20, value * factor)));
    }
    canvas.addEventListener("wheel", handleWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", handleWheel);
  }, []);

  function onPointerDown(event: React.PointerEvent<HTMLCanvasElement>) {
    if (event.button !== 1 && !(event.button === 0 && (tool === "cursor" || spacePressed))) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, moved: false };
  }

  function onPointerMove(event: React.PointerEvent<HTMLCanvasElement>) {
    const drag = dragRef.current;
    if (drag?.pointerId === event.pointerId) {
      const dx = event.clientX - drag.x;
      const dy = event.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 1) drag.moved = true;
      drag.x = event.clientX;
      drag.y = event.clientY;
      setPanOffset((offset) => ({ x: offset.x + dx, y: offset.y + dy }));
      return;
    }
    onMouseMove(event as unknown as React.MouseEvent<HTMLCanvasElement>);
  }

  function onPointerUp(event: React.PointerEvent<HTMLCanvasElement>) {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    dragRef.current = null;
  }

  // Per-entity screen rectangles collected during draw, used for click
  // hit testing. Each rectangle is the on-screen footprint of the entity
  // (with line endpoints expanded to a 6-px tube for clickability).
  const entityHitRects = useRef<Array<{ entity: EntityOut; rect: { x: number; y: number; w: number; h: number } }>>([]);

  // "adv:fit-view" event handler — fired by the page when the user clicks
  // the Fit rail button or presses F. Resets zoom to 1 and redraws.
  useEffect(() => {
    function onFit() {
      setZoom(1);
      setPanOffset({ x: 0, y: 0 });
      setClickedEntity(null);
      setHovered(null);
    }
    window.addEventListener("adv:fit-view", onFit);
    return () => window.removeEventListener("adv:fit-view", onFit);
  }, []);

  // Snapshot export — captured per draw call so the rendered canvas is
  // fresh, then dataURL → download. The page tells us how to publish the
  // filename via the `data-snapshot-label` body attribute.
  useEffect(() => {
    if (!registerSnapshot) return;
    registerSnapshot(() => {
      const c = canvasRef.current;
      if (!c) return;
      try {
        const url = c.toDataURL("image/png");
        const a = document.createElement("a");
        const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
        a.href = url;
        a.download = `${document.body.dataset.snapshotLabel ?? "adv-snapshot"}-${ts}.png`;
        a.click();
      } catch (err) {
        // Some browsers throw if the canvas is "tainted" by cross-origin
        // images. We don't load any remote images so this branch is rare,
        // but surface the failure instead of silently dropping it.
        console.error("snapshot export failed", err);
      }
    });
  }, [registerSnapshot]);

  // Right-click while in measure mode resets points (matches most CAD apps).
  useEffect(() => {
    function onContext(e: MouseEvent) {
      if (tool === "measure") {
        e.preventDefault();
        onMeasureReset?.();
      } else if (tool === "annotate") {
        e.preventDefault();
        onMeasureReset?.();
      }
    }
    const c = canvasRef.current;
    if (!c) return;
    c.addEventListener("contextmenu", onContext);
    return () => c.removeEventListener("contextmenu", onContext);
  }, [tool, onMeasureReset]);

  // Auto-revert the cursor style whenever the rail tool changes so the
  // user gets instant feedback that the rail is wired.
  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    c.style.cursor = cursor ?? "default";
  }, [cursor]);

  // Per-entity screen rectangles collected during draw, used for click
  // hit testing. Each rectangle is the on-screen footprint of the entity
  // (with line endpoints expanded to a 6-px tube for clickability).

  useEffect(() => {
    draw();
    const ro = new ResizeObserver(draw);
    if (containerRef.current) ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, [draw]);

  function onCanvasClick(e: React.MouseEvent<HTMLCanvasElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const issueHit = issueScreenRects.current.find(
      ({ rect: r }) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h,
    );
    if (issueHit) {
      setHovered({ issue: issueHit.issue, x, y });
      setClickedEntity(null);
      return;
    }
    setHovered(null);
    // Branch on rail tool -- each tool changes the meaning of a click.
    if (tool === "zoom") {
      const factor = e.altKey ? 1 / 1.4 : 1.4;
      setZoom((z) => Math.max(0.25, Math.min(4, z * factor)));
      return;
    }
    if (tool === "fit") {
      window.dispatchEvent(new CustomEvent("adv:fit-view"));
      return;
    }
    if (tool === "measure") {
      const wp = screenToWorld(x, y);
      if (!wp || !onMeasurePoint) return;
      onMeasurePoint(wp);
      onMeasurePreview?.(null);
      return;
    }
    if (tool === "annotate") {
      if (!onAddAnnotation) return;
      const wp = screenToWorld(x, y);
      if (!wp) return;
      onAddAnnotation(wp.x, wp.y, activeSheet);
      return;
    }
    // Default (cursor / identify) -- hit-test the entity list.
    const inside = entityHitRects.current
      .filter(({ rect: r }) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h)
      .sort((a, b) => (a.rect.w * a.rect.h) - (b.rect.w * b.rect.h));
    setClickedEntity(inside[0]?.entity ?? null);
  }

  function screenToWorld(sx: number, sy: number): { x: number; y: number } | null {
    const viewport = viewportRef.current;
    return viewport ? viewportToWorld(viewport, { x: sx, y: sy }) : null;
  }

  function onMouseMove(e: React.MouseEvent<HTMLCanvasElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const hit = issueScreenRects.current.find(
      ({ rect: r }) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h,
    );
    if (hit) {
      setHovered({ issue: hit.issue, x, y });
    } else if (hovered) {
      setHovered(null);
    }
    // Measure tool: feed live preview so the user sees the dimension
    // before clicking the second point.
    if (tool === "measure" && measurePoints.length === 1 && onMeasurePreview) {
      const wp = screenToWorld(x, y);
      if (wp) onMeasurePreview(wp);
    } else if (tool !== "measure" && measurePreview) {
      onMeasurePreview?.(null);
    }
  }

  const tabs: Array<{ key: DrawingTab; label: string }> = [
    { key: "str", label: "STR" },
    { key: "mech", label: "MECH" },
    { key: "overlay", label: "OVERLAY" },
  ];

  return (
    <>
      <div className="ws-tabs-drawings" role="tablist" aria-label="Drawing">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={activeTab === t.key}
            className={`ws-tab-drawing${activeTab === t.key ? " active" : ""}`}
            data-tab={t.key}
            onClick={() => setActiveTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="canvas-tool tr">
        <select
          value={activeSheet}
          onChange={(e) => setActiveSheet(e.target.value)}
          aria-label="Active sheet"
        >
          {sheets.map((s) => (
            <option key={s} value={s}>
              SHEET {s}
            </option>
          ))}
        </select>
        <button type="button" onClick={() => setZoom((z) => Math.min(z * 1.25, 4))} title="Zoom in">
          +
        </button>
        <button type="button" onClick={() => setZoom((z) => Math.max(z * 0.8, 0.25))} title="Zoom out">
          −
        </button>
        <button type="button" onClick={() => setZoom(1)} title="Reset zoom">
          ⤢
        </button>
      </div>

      <div ref={containerRef} className="canvas-container">
        <canvas
          ref={canvasRef}
          onPointerMove={onPointerMove}
          onPointerDown={onPointerDown}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onClick={onCanvasClick}
          onMouseLeave={() => { setHovered(null); onMeasurePreview?.(null); }}
          style={{ cursor }}
        />
        {clickedEntity && <EntityInfoPanel entity={clickedEntity} onClose={() => setClickedEntity(null)} />}
        {hovered && !clickedEntity && (
          <div
            className="canvas-issue-tooltip"
            style={{ left: hovered.x + 14, top: hovered.y + 14 }}
            role="tooltip"
          >
            <div className={`cit-sev cit-${hovered.issue.severity === "high" ? "high" : "med"}`}>
              {hovered.issue.severity.toUpperCase()} · {hovered.issue.code}
            </div>
            <div className="cit-title">{hovered.issue.title}</div>
            {hovered.issue.grid && <div className="cit-grid">GRID {hovered.issue.grid}</div>}
            {hovered.issue.evidence && (
              <div className="cit-section">
                <div className="cit-label">EVIDENCE</div>
                <div className="cit-body">{hovered.issue.evidence}</div>
              </div>
            )}
            {hovered.issue.formula && (
              <div className="cit-section">
                <div className="cit-label">FORMULA</div>
                <div className="cit-body mono">{hovered.issue.formula}</div>
              </div>
            )}
            <div className="cit-section">
              <div className="cit-label">PROBABLE FIX</div>
              <div className="cit-body cit-fix">
                {SUGGESTED_FIX[hovered.issue.category] ??
                  "Review drawing set against STR spec; reconcile with engineer of record."}
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

/** Floating card shown when the user clicks an entity. Hides on
 *  background click of the canvas or via the close button. */
function EntityInfoPanel({ entity, onClose }: { entity: EntityOut; onClose: () => void }) {
  const meta = (entity.meta ?? {}) as {
    layer?: string;
    type?: string;
    radius?: number;
    startPoint?: { x: number; y: number };
    endPoint?: { x: number; y: number };
    insUnits?: number;
  };
  const w = Math.abs(entity.w_mm ?? 0);
  const h = Math.abs(entity.h_mm ?? 0);
  const sxy = meta.startPoint;
  const exy = meta.endPoint;
  return (
    <div
      className="entity-info-panel"
      role="dialog"
      aria-label={`${entity.kind} details`}
      onClick={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        className="entity-info-close"
        onClick={onClose}
        aria-label="Close"
      >
        ×
      </button>
      <div className="entity-info-kind">{entity.kind?.toUpperCase() ?? "ENTITY"}</div>
      <div className="entity-info-disc">
        {entity.label ? entity.label : <span className="muted">no label</span>}
      </div>
      <dl className="entity-info-grid">
        <dt>Layer</dt>
        <dd>{meta.layer ?? "—"}</dd>
        <dt>Type</dt>
        <dd>{meta.type ?? "—"}</dd>
        <dt>Disc.</dt>
        <dd>{entity.discipline?.toUpperCase() ?? "—"}</dd>
        <dt>Sheet</dt>
        <dd>{entity.sheet ?? "—"}</dd>
        {sxy && (
          <>
            <dt>Start</dt>
            <dd>{sxy.x.toFixed(1)}, {sxy.y.toFixed(1)} mm</dd>
          </>
        )}
        {exy && (
          <>
            <dt>End</dt>
            <dd>{exy.x.toFixed(1)}, {exy.y.toFixed(1)} mm</dd>
          </>
        )}
        {w > 0 && (
          <>
            <dt>Size</dt>
            <dd>{Math.round(w)} × {Math.round(h)} mm</dd>
          </>
        )}
        {meta.radius != null && meta.radius > 0 && (
          <>
            <dt>Radius</dt>
            <dd>{Math.round(meta.radius)} mm</dd>
          </>
        )}
      </dl>
    </div>
  );
}