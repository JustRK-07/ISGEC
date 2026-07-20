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

interface Props {
  entities: EntityOut[];
  sheets: string[];
}

export function DrawingCanvas({ entities, sheets }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [scale, setScale] = useState(0.08); // px per mm
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [activeSheet, setActiveSheet] = useState(sheets[0] ?? "0001");

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    // Clear
    ctx.fillStyle = "#0F172A";
    ctx.fillRect(0, 0, rect.width, rect.height);

    // Subtle grid background
    ctx.strokeStyle = "rgba(14, 165, 164, 0.12)";
    ctx.lineWidth = 1;
    const gridStep = 50 * scale;
    for (let x = (offset.x % gridStep) - gridStep; x < rect.width; x += gridStep) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, rect.height);
      ctx.stroke();
    }
    for (let y = (offset.y % gridStep) - gridStep; y < rect.height; y += gridStep) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(rect.width, y);
      ctx.stroke();
    }

    // Draw entities
    const filtered = entities.filter((e) => e.sheet === activeSheet);
    for (const entity of filtered) {
      const color = KIND_COLORS[entity.kind] ?? "#64748B";
      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      ctx.lineWidth = entity.discipline === "str" ? 1.5 : 1;

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
          ctx.fillStyle = "#94A3B8";
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
  }, [entities, activeSheet, scale, offset]);

  return (
    <div className="w-full h-full relative">
      <div className="absolute top-4 right-4 z-10 flex gap-2">
        <select
          value={activeSheet}
          onChange={(e) => setActiveSheet(e.target.value)}
          className="bg-bg-dark text-white border border-border rounded px-2 py-1 text-sm"
        >
          {sheets.map((s) => (
            <option key={s} value={s}>SHEET {s}</option>
          ))}
        </select>
        <button
          onClick={() => setScale((s) => Math.min(s * 1.25, 1))}
          className="bg-bg-dark text-white border border-border rounded px-2 py-1 text-sm"
        >
          +
        </button>
        <button
          onClick={() => setScale((s) => Math.max(s * 0.8, 0.005))}
          className="bg-bg-dark text-white border border-border rounded px-2 py-1 text-sm"
        >
          −
        </button>
      </div>
      <canvas ref={canvasRef} className="w-full h-full block" />
    </div>
  );
}
