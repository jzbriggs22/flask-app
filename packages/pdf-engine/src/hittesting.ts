/**
 * Hit Testing (Spec §7)
 *
 * Always performed in WORLD but using a CSS_PX tolerance
 * projected back into WORLD (depends on zoom).
 *
 * Rule: Hit-testing must be stable under zoom changes.
 *
 * Performance (§13): For large measurement counts, use a spatial index
 * (R-tree or uniform grid). For MVP, linear scan is acceptable for
 * typical measurement counts (<1000 per sheet).
 */

import type {
  WorldPoint,
  TransformState,
  Measurement,
  MeasurementType,
} from "@openbuild/types";
import { closestPointOnSegment, distanceBetween } from "./measurement";

export interface HitTestResult {
  measurementId: string;
  type: MeasurementType;
  /** Distance from cursor to nearest geometry edge in WORLD */
  distanceWorld: number;
  /** Which segment or vertex was hit (for future editing) */
  hitType: "edge" | "vertex" | "interior";
  /** Index of the hit vertex or segment start */
  index: number;
}

/**
 * Hit-test a single measurement against a WORLD point.
 * Returns null if the point is outside the tolerance.
 *
 * @param point - cursor position in WORLD
 * @param measurement - the measurement to test
 * @param toleranceWorld - tolerance in WORLD units (computed from CSS_PX / zoom)
 */
export function hitTestMeasurement(
  point: WorldPoint,
  measurement: Measurement,
  toleranceWorld: number
): HitTestResult | null {
  if (measurement.deletedAt !== null) return null;
  const geom = measurement.geometryWorld;
  if (!geom || geom.length === 0) return null;

  switch (measurement.type) {
    case "count":
      return hitTestCount(point, measurement, geom, toleranceWorld);
    case "linear":
      return hitTestPolyline(point, measurement, geom, toleranceWorld);
    case "area":
      return hitTestPolygon(point, measurement, geom, toleranceWorld);
    default:
      return null;
  }
}

/**
 * Hit-test all visible measurements on a sheet revision.
 * Returns the closest hit, or null.
 *
 * @param cursorWorld - cursor position in WORLD
 * @param measurements - visible measurements on this sheet revision
 * @param toleranceWorld - tolerance in WORLD (derived from CSS_PX / effectiveScale)
 */
export function hitTestMeasurements(
  cursorWorld: WorldPoint,
  measurements: Measurement[],
  toleranceWorld: number
): HitTestResult | null {
  let best: HitTestResult | null = null;

  for (const m of measurements) {
    const result = hitTestMeasurement(cursorWorld, m, toleranceWorld);
    if (result && (!best || result.distanceWorld < best.distanceWorld)) {
      best = result;
    }
  }

  return best;
}

/**
 * Convert a CSS_PX tolerance to WORLD tolerance at the current transform.
 * Rule (§7): hit-testing uses CSS_PX tolerance projected back into WORLD.
 */
export function screenToleranceToWorld(
  tolerancePx: number,
  transform: TransformState
): number {
  const effectiveScale = transform.zoom * transform.pdfViewportScale;
  return tolerancePx / effectiveScale;
}

// ============================================================
// Internal hit test implementations
// ============================================================

function hitTestCount(
  point: WorldPoint,
  m: Measurement,
  geom: WorldPoint[],
  tolerance: number
): HitTestResult | null {
  for (let i = 0; i < geom.length; i++) {
    const dist = distanceBetween(point, geom[i]);
    if (dist <= tolerance) {
      return {
        measurementId: m.id,
        type: "count",
        distanceWorld: dist,
        hitType: "vertex",
        index: i,
      };
    }
  }
  return null;
}

function hitTestPolyline(
  point: WorldPoint,
  m: Measurement,
  geom: WorldPoint[],
  tolerance: number
): HitTestResult | null {
  // Check vertices first (higher priority)
  for (let i = 0; i < geom.length; i++) {
    const dist = distanceBetween(point, geom[i]);
    if (dist <= tolerance) {
      return {
        measurementId: m.id,
        type: "linear",
        distanceWorld: dist,
        hitType: "vertex",
        index: i,
      };
    }
  }

  // Check edges
  for (let i = 0; i < geom.length - 1; i++) {
    const { distance } = closestPointOnSegment(point, geom[i], geom[i + 1]);
    if (distance <= tolerance) {
      return {
        measurementId: m.id,
        type: "linear",
        distanceWorld: distance,
        hitType: "edge",
        index: i,
      };
    }
  }

  return null;
}

function hitTestPolygon(
  point: WorldPoint,
  m: Measurement,
  geom: WorldPoint[],
  tolerance: number
): HitTestResult | null {
  // Check vertices
  for (let i = 0; i < geom.length; i++) {
    const dist = distanceBetween(point, geom[i]);
    if (dist <= tolerance) {
      return {
        measurementId: m.id,
        type: "area",
        distanceWorld: dist,
        hitType: "vertex",
        index: i,
      };
    }
  }

  // Check edges (polygon is closed: include last→first)
  for (let i = 0; i < geom.length; i++) {
    const j = (i + 1) % geom.length;
    const { distance } = closestPointOnSegment(point, geom[i], geom[j]);
    if (distance <= tolerance) {
      return {
        measurementId: m.id,
        type: "area",
        distanceWorld: distance,
        hitType: "edge",
        index: i,
      };
    }
  }

  // Check if point is inside the polygon (ray casting)
  if (pointInPolygon(point, geom)) {
    return {
      measurementId: m.id,
      type: "area",
      distanceWorld: 0,
      hitType: "interior",
      index: -1,
    };
  }

  return null;
}

/**
 * Ray-casting point-in-polygon test.
 */
function pointInPolygon(point: WorldPoint, polygon: WorldPoint[]): boolean {
  let inside = false;
  const n = polygon.length;

  for (let i = 0, j = n - 1; i < n; j = i++) {
    const xi = polygon[i].x;
    const yi = polygon[i].y;
    const xj = polygon[j].x;
    const yj = polygon[j].y;

    const intersects =
      yi > point.y !== yj > point.y &&
      point.x < ((xj - xi) * (point.y - yi)) / (yj - yi) + xi;

    if (intersects) inside = !inside;
  }

  return inside;
}
