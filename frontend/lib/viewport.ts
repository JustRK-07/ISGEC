import type { EntityOut } from "./api";

export interface WorldPoint {
  x: number;
  y: number;
}

export interface ScreenPoint {
  x: number;
  y: number;
}

export interface BBox {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

export interface Viewport {
  scale: number;
  tx: number;
  ty: number;
  width: number;
  height: number;
}

export const MIN_SCALE = 0.00001;
export const MAX_SCALE = 20;

export function clampScale(scale: number): number {
  if (!Number.isFinite(scale) || scale <= 0) return MIN_SCALE;
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale));
}

export function worldToScreen(viewport: Viewport, point: WorldPoint): ScreenPoint {
  return {
    x: point.x * viewport.scale + viewport.tx,
    y: point.y * viewport.scale + viewport.ty,
  };
}

export function screenToWorld(viewport: Viewport, point: ScreenPoint): WorldPoint {
  return {
    x: (point.x - viewport.tx) / viewport.scale,
    y: (point.y - viewport.ty) / viewport.scale,
  };
}

export function zoomAt(viewport: Viewport, nextScale: number, anchor: ScreenPoint): Viewport {
  const scale = clampScale(nextScale);
  const worldAnchor = screenToWorld(viewport, anchor);
  return {
    ...viewport,
    scale,
    tx: anchor.x - worldAnchor.x * scale,
    ty: anchor.y - worldAnchor.y * scale,
  };
}

export function panViewport(viewport: Viewport, dx: number, dy: number): Viewport {
  return { ...viewport, tx: viewport.tx + dx, ty: viewport.ty + dy };
}

export function entityExtent(entity: EntityOut): BBox | null {
  const points: WorldPoint[] = [];
  const meta = entity.meta;
  if (entity.x_mm != null && entity.y_mm != null) {
    const halfW = Math.abs(entity.w_mm ?? 0) / 2;
    const halfH = Math.abs(entity.h_mm ?? 0) / 2;
    points.push(
      { x: entity.x_mm - halfW, y: entity.y_mm - halfH },
      { x: entity.x_mm + halfW, y: entity.y_mm + halfH },
    );
  }
  if (meta?.startPoint) points.push(meta.startPoint);
  if (meta?.endPoint) points.push(meta.endPoint);
  if (meta?.position) points.push(meta.position);
  if (meta?.vertices) points.push(...meta.vertices);
  if (meta?.center && meta.radius != null) {
    points.push(
      { x: meta.center.x - meta.radius, y: meta.center.y - meta.radius },
      { x: meta.center.x + meta.radius, y: meta.center.y + meta.radius },
    );
  }
  const finite = points.filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
  if (!finite.length) return null;
  return {
    minX: Math.min(...finite.map((point) => point.x)),
    minY: Math.min(...finite.map((point) => point.y)),
    maxX: Math.max(...finite.map((point) => point.x)),
    maxY: Math.max(...finite.map((point) => point.y)),
  };
}

export function robustBBox(entities: readonly EntityOut[], padMm = 50): BBox | null {
  const extents = entities.map(entityExtent).filter((extent): extent is BBox => extent != null);
  if (!extents.length) return null;
  let minX = Math.min(...extents.map((extent) => extent.minX));
  let minY = Math.min(...extents.map((extent) => extent.minY));
  let maxX = Math.max(...extents.map((extent) => extent.maxX));
  let maxY = Math.max(...extents.map((extent) => extent.maxY));
  if (minX === maxX) {
    minX -= padMm;
    maxX += padMm;
  }
  if (minY === maxY) {
    minY -= padMm;
    maxY += padMm;
  }
  return { minX, minY, maxX, maxY };
}

export function fitViewport(
  bbox: BBox,
  region: { x: number; y: number; width: number; height: number },
  marginRatio = 0.12,
): Viewport {
  const width = Math.max(1, bbox.maxX - bbox.minX);
  const height = Math.max(1, bbox.maxY - bbox.minY);
  const availableWidth = region.width * (1 - marginRatio * 2);
  const availableHeight = region.height * (1 - marginRatio * 2);
  const scale = clampScale(Math.min(availableWidth / width, availableHeight / height));
  return {
    scale,
    tx: region.x + region.width / 2 - ((bbox.minX + bbox.maxX) / 2) * scale,
    ty: region.y + region.height / 2 - ((bbox.minY + bbox.maxY) / 2) * scale,
    width: region.width,
    height: region.height,
  };
}
