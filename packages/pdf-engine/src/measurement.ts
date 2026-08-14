/**
 * Measurement calculation engine for construction takeoff.
 * Aligned with Takeoff Engine Spec v0.1 §6, §10.
 *
 * All calculations are performed in WORLD coordinates (PDF_PT),
 * then converted to real-world units via a Calibration.
 *
 * Accuracy note: Construction tolerances matter. A 1% error on a $10M
 * project is $100K. Use precise math, never approximate.
 */

import type {
  WorldPoint,
  MeasurementType,
  Calibration,
  UOM_PRECISION,
} from "@openbuild/types";

// Re-export the precision table so callers don't need a separate import
export { UOM_PRECISION } from "@openbuild/types";

// ============================================================
// Core geometry computations (all in WORLD / PDF_PT)
// ============================================================

/**
 * Polyline length in WORLD (PDF_PT).
 * Linear measurements: sum of Euclidean segment distances.
 */
export function calculateLinearDistance(points: WorldPoint[]): number {
  if (points.length < 2) return 0;

  let total = 0;
  for (let i = 1; i < points.length; i++) {
    const dx = points[i].x - points[i - 1].x;
    const dy = points[i].y - points[i - 1].y;
    total += Math.sqrt(dx * dx + dy * dy);
  }
  return total;
}

/**
 * Polygon area in WORLD (PDF_PT²).
 * Uses the Shoelace formula (Gauss's area formula).
 * The polygon is implicitly closed (last→first edge included).
 */
export function calculatePolygonArea(points: WorldPoint[]): number {
  if (points.length < 3) return 0;

  let area = 0;
  const n = points.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    area += points[i].x * points[j].y;
    area -= points[j].x * points[i].y;
  }
  return Math.abs(area) / 2;
}

/**
 * Count quantity = number of points.
 */
export function calculateCountQuantity(points: WorldPoint[]): number {
  return points.length;
}

// ============================================================
// Quantity computation (Spec §6)
// ============================================================

/**
 * Compute the raw quantity from geometry in WORLD coordinates.
 * Returns value in PDF_PT (linear), PDF_PT² (area), or count.
 */
export function computeQuantityRaw(
  type: MeasurementType,
  points: WorldPoint[]
): number {
  switch (type) {
    case "linear":
      return calculateLinearDistance(points);
    case "area":
      return calculatePolygonArea(points);
    case "count":
      return calculateCountQuantity(points);
    case "volume":
      // Volume deferred in MVP — spec §6 placeholder
      return 0;
  }
}

/**
 * Convert a raw WORLD quantity to real-world units using a calibration.
 * Returns null if no calibration is provided (measurement is uncalibrated).
 *
 * Rule (§5): A measurement is "calibrated" if it references a calibration_id
 * tied to the same sheet revision.
 */
export function computeQuantityReal(
  type: MeasurementType,
  quantityRaw: number,
  calibration: Calibration | null
): number | null {
  // Counts are unit-independent — they need no calibration
  if (type === "count") return quantityRaw;

  if (!calibration || calibration.scaleFactor === 0) return null;

  switch (type) {
    case "linear":
      // scaleFactor = real units per PDF_PT
      return quantityRaw * calibration.scaleFactor;
    case "area":
      // Area scales by factor²
      return quantityRaw * calibration.scaleFactor * calibration.scaleFactor;
    case "volume":
      return null;
    default:
      return null;
  }
}

// ============================================================
// Calibration (Spec §5)
// ============================================================

/**
 * Compute calibration values from two picked points and a known real distance.
 * Returns the world_distance_pt and scale_factor.
 */
export function computeCalibration(
  point1: WorldPoint,
  point2: WorldPoint,
  realDistance: number
): { worldDistancePt: number; scaleFactor: number } {
  const dx = point2.x - point1.x;
  const dy = point2.y - point1.y;
  const worldDistancePt = Math.sqrt(dx * dx + dy * dy);

  return {
    worldDistancePt,
    scaleFactor: worldDistancePt > 0 ? realDistance / worldDistancePt : 0,
  };
}

// ============================================================
// Rounding (Spec §10)
// ============================================================

/**
 * Round a quantity to the precision defined for its unit of measure.
 *
 * Rule (§10): The number a user sees in-app must match the number in exports.
 * Store rounded values; display rounding is separate from stored rounding.
 */
export function roundQuantity(value: number, uom: string): number {
  const precision = (
    { ft: 2, in: 2, sf: 2, sy: 2, cy: 2, ea: 0, ton: 2, lb: 0,
      gal: 0, hr: 2, day: 2, ls: 2, m: 3, mm: 0, sm: 2 } as Record<string, number>
  )[uom.toLowerCase()];

  if (precision === undefined) {
    // Unknown UOM: default to 2 decimal places
    return Math.round(value * 100) / 100;
  }

  const factor = Math.pow(10, precision);
  return Math.round(value * factor) / factor;
}

// ============================================================
// Segment utilities (used by snapping/hit-testing)
// ============================================================

/** Distance between two WORLD points. */
export function distanceBetween(a: WorldPoint, b: WorldPoint): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  return Math.sqrt(dx * dx + dy * dy);
}

/** Midpoint of a segment in WORLD. */
export function midpoint(a: WorldPoint, b: WorldPoint): WorldPoint {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

/**
 * Closest point on segment (a→b) to point p, in WORLD.
 * Returns the projected point and the parametric t value (0..1).
 */
export function closestPointOnSegment(
  p: WorldPoint,
  a: WorldPoint,
  b: WorldPoint
): { point: WorldPoint; t: number; distance: number } {
  const abx = b.x - a.x;
  const aby = b.y - a.y;
  const apx = p.x - a.x;
  const apy = p.y - a.y;

  const ab2 = abx * abx + aby * aby;
  if (ab2 === 0) {
    // Degenerate segment (a == b)
    return { point: { x: a.x, y: a.y }, t: 0, distance: distanceBetween(p, a) };
  }

  const t = Math.max(0, Math.min(1, (apx * abx + apy * aby) / ab2));
  const projected: WorldPoint = { x: a.x + t * abx, y: a.y + t * aby };
  return { point: projected, t, distance: distanceBetween(p, projected) };
}
