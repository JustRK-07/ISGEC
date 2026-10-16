import { describe, expect, it } from "vitest";

import type { EntityOut } from "./api";
import {
  clampScale,
  entityExtent,
  fitViewport,
  panViewport,
  robustBBox,
  screenToWorld,
  worldToScreen,
  zoomAt,
  type Viewport,
} from "./viewport";

function entity(overrides: Partial<EntityOut>): EntityOut {
  return {
    id: "entity-1",
    discipline: "str",
    sheet: "S-101",
    kind: "line",
    label: null,
    x_mm: null,
    y_mm: null,
    w_mm: null,
    h_mm: null,
    rotation: null,
    meta: null,
    ...overrides,
  };
}

describe("viewport transforms", () => {
  const viewport: Viewport = { scale: 0.1, tx: 40, ty: -20, width: 800, height: 600 };

  it("round-trips world and screen coordinates", () => {
    const point = { x: 1234, y: -567 };
    const result = screenToWorld(viewport, worldToScreen(viewport, point));
    expect(result.x).toBeCloseTo(point.x, 8);
    expect(result.y).toBeCloseTo(point.y, 8);
  });

  it("keeps the cursor world point stable while zooming", () => {
    const anchor = { x: 420, y: 250 };
    const before = screenToWorld(viewport, anchor);
    const next = zoomAt(viewport, viewport.scale * 2, anchor);
    expect(screenToWorld(next, anchor)).toEqual(before);
  });

  it("pans in screen pixels", () => {
    expect(panViewport(viewport, 12, -8)).toMatchObject({ tx: 52, ty: -28 });
  });

  it("clamps invalid scales", () => {
    expect(clampScale(Number.NaN)).toBeGreaterThan(0);
    expect(clampScale(-1)).toBeGreaterThan(0);
  });
});

describe("viewport bounds", () => {
  it("uses vertices and radius in entity extents", () => {
    expect(
      entityExtent(entity({ meta: { vertices: [{ x: -10, y: 2 }, { x: 40, y: 30 }] } })),
    ).toEqual({ minX: -10, minY: 2, maxX: 40, maxY: 30 });
    expect(
      entityExtent(entity({ meta: { center: { x: 100, y: 50 }, radius: 20 } })),
    ).toEqual({ minX: 80, minY: 30, maxX: 120, maxY: 70 });
  });

  it("aggregates drawing bounds and fits them into a region", () => {
    const bbox = robustBBox([
      entity({ x_mm: 0, y_mm: 0, w_mm: 100, h_mm: 100 }),
      entity({ x_mm: 1000, y_mm: 500, w_mm: 100, h_mm: 100 }),
    ]);
    expect(bbox).not.toBeNull();
    const fitted = fitViewport(bbox!, { x: 0, y: 0, width: 800, height: 600 });
    const topLeft = worldToScreen(fitted, { x: bbox!.minX, y: bbox!.minY });
    const bottomRight = worldToScreen(fitted, { x: bbox!.maxX, y: bbox!.maxY });
    expect(topLeft.x).toBeGreaterThanOrEqual(0);
    expect(topLeft.y).toBeGreaterThanOrEqual(0);
    expect(bottomRight.x).toBeLessThanOrEqual(800);
    expect(bottomRight.y).toBeLessThanOrEqual(600);
  });
});
