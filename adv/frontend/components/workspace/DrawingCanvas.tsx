"use client";

import { useEffect, useRef, useState } from "react";
import type { EntityOut } from "@/lib/api";

const KIND_COLORS: Record<string, string> = {
  "grid-bubble": "#0EA5A4",
  opening: "#F59E0B",
  beam: "#10B981",
  column: "#10B981",
  pipe: "#3B82F6",
  duct: "#3B82F6",
  equipment: "#A855F7",
  block: "#94A3B8",
  text: "#64748B",
  line: "#475569",
};

/** Tab definitions — what drawings are available to display.
 *  Matches the prototype's STR / MECH / overlay tabs.
 *  The "overlay" tab shows both disciplines in one canvas. */
export type DrawingTab = "str" | "mech" | "overlay";

interface Props {
  entities: EntityOut[];
  sheets: string[];
}

export function DrawingCanvas({ entities, sheets }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [scale, setScale] = useState(0.08); // px per mm
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [activeSheet, setActiveSheet] = useState(sheets[0] ?? "0001");
  const [activeTab, setActiveTab] = useState<DrawingTab>("overlay");

  // Resize + redraw whenever inputs change.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    function draw() {
      if (!canvas || !ctx) return;
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      const cssW = Math.max(1, Math.floor(rect.width));
      const cssH = Math.max(1, Math.floor(rect.height));
      canvas.width = cssW * dpr;
      canvas.height = cssH * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      // Paper background with a faint grid pattern.
      ctx.fillStyle = "#F2EFE6"; // var(--paper)
      ctx.fillRect(0, 0, cssW, cssH);

      ctx.strokeStyle = "rgba(14, 27, 44, 0.08)";
      ctx.lineWidth = 1;
      const gridStep = 28;
      for (let x = (offset.x % gridStep) - gridStep; x < cssW; x += gridStep) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, cssH);
        ctx.stroke();
      }
      for (let y = (offset.y % gridStep) - gridStep; y < cssH; y += gridStep) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(cssW, y);
        ctx.stroke();
      }

      // Pick which discipline to show.
      const filtered = entities.filter((e) => {
        if (e.sheet !== activeSheet) return false;
        if (activeTab === "str") return e.discipline === "str";
        if (activeTab === "mech") return e.discipline === "mech";
        return true; // overlay: show both
      });

      // Sort so mech renders behind str (lighter colour underneath).
      filtered.sort((a, b) => {
        if (a.discipline === b.discipline) return 0;
        return a.discipline === "mech" ? -1 : 1;
      });

      for (const entity of filtered) {
        const color = KIND_COLORS[entity.kind] ?? "#475569";
        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        ctx.lineWidth = entity.discipline === "str" ? 1.6 : 1;

        const cx = entity.x_mm ?? 0;
        const cy = entity.y_mm ?? 0;
        const screenX = cx * scale + offset.x;
        const screenY = cy * scale + offset.y;
        const w = (entity.w_mm ?? 0) * scale;
        const h = (entity.h_mm ?? 0) * scale;

        if (entity.kind === "opening" || entity.kind === "duct" || entity.kind === "beam") {
          ctx.strokeRect(screenX - w / 2, screenY - h / 2, w, h);
        } else if (entity.kind === "pipe") {
          ctx.beginPath();
          ctx.arc(screenX, screenY, Math.max(2, w / 2), 0, Math.PI * 2);
          ctx.stroke();
        } else if (entity.kind === "text") {
          if (entity.label) {
            ctx.font = "11px JetBrains Mono, monospace";
            ctx.fillStyle = "#5C6B82";
            ctx.fillText(entity.label.slice(0, 30), screenX, screenY);
          }
        } else if (entity.meta?.startPoint && entity.meta?.endPoint) {
          ctx.beginPath();
          ctx.moveTo(entity.meta.startPoint.x * scale + offset.x, entity.meta.startPoint.y * scale + offset.y);
          ctx.lineTo(entity.meta.endPoint.x * scale + offset.x, entity.meta.endPoint.y * scale + offset.y);
          ctx.stroke();
        } else {
          ctx.fillRect(screenX - 2, screenY - 2, 4, 4);
        }
      }
    }

    draw();
    const ro = new ResizeObserver(draw);
    ro.observe(canvas);
    return () => ro.disconnect();
  }, [entities, activeSheet, activeTab, scale, offset]);

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
        <button type="button" onClick={() => setScale((s) => Math.min(s * 1.25, 1))} title="Zoom in">
          +
        </button>
        <button type="button" onClick={() => setScale((s) => Math.max(s * 0.8, 0.005))} title="Zoom out">
          −
        </button>
      </div>

      <canvas ref={canvasRef} />
    </>
  );
}