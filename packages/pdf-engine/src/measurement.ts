/**
 * Measurement calculation engine for construction takeoff.
 *
 * All calculations are performed in drawing coordinates, then scaled
 * to real-world units using the calibration data.
 *
 * Accuracy note: Construction tolerances matter. A 1% error on a $10M
 * project is $100K. Use precise math, never approximate.
 */

export interface Point {
  x: number;
  y: number;
}

export interface ScaleConfig {
  /** Pixels per real-world unit */
  pixelsPerUnit: number;
  /** Real-world unit (ft, in, m, mm) */
  unit: "ft" | "in" | "m" | "mm";
}

/**
 * Calculate the linear distance between a series of points (polyline).
 * Returns distance in drawing pixels — apply scale to convert to real units.
 */
export function calculateLinearDistance(points: Point[]): number {
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
 * Calculate the area of a polygon defined by a series of points.
 * Uses the Shoelace formula (Gauss's area formula).
 * Returns area in drawing pixels squared — apply scale^2 for real units.
 */
export function calculatePolygonArea(points: Point[]): number {
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
 * Convert a drawing-coordinate measurement to real-world units.
 */
export function applyScale(
  drawingValue: number,
  scale: ScaleConfig,
  type: "linear" | "area"
): number {
  if (scale.pixelsPerUnit === 0) return 0;

  if (type === "linear") {
    return drawingValue / scale.pixelsPerUnit;
  }
  // For area, divide by scale squared
  return drawingValue / (scale.pixelsPerUnit * scale.pixelsPerUnit);
}

/**
 * Calculate scale config from two calibration points and a known real distance.
 */
export function calibrateScale(
  point1: Point,
  point2: Point,
  realDistance: number,
  unit: ScaleConfig["unit"]
): ScaleConfig {
  const dx = point2.x - point1.x;
  const dy = point2.y - point1.y;
  const pixelDistance = Math.sqrt(dx * dx + dy * dy);

  return {
    pixelsPerUnit: pixelDistance / realDistance,
    unit,
  };
}
