/**
 * Snapping System (Spec §7)
 *
 * Snap targets:
 *   - Existing measurement vertices (same sheet revision)
 *   - Segment midpoints
 *   - Segment intersections (optional v0.2)
 *   - Grid (optional)
 *
 * Snap tolerance is defined in CSS_PX (because user "feel" is pixel-based).
 * Implementation: find nearest WORLD candidate by projecting candidates
 * to CSS_PX each frame.
 *
 * Rule: Snapping must be stable under zoom changes.
 */

import type {
  WorldPoint,
  ScreenPoint,
  TransformState,
  Measurement,
  SnapConfig,
  SnapTarget,
  SnapTargetType,
} from "@openbuild/types";
import { screenToWorld, worldToScreen } from "./transforms";
import { midpoint, distanceBetween } from "./measurement";

/**
 * A candidate snap point with its screen projection.
 * Built once per frame from visible measurements.
 */
export interface SnapCandidate {
  target: SnapTarget;
  screenPoint: ScreenPoint;
}

/**
 * Build snap candidates from all visible measurements on the current sheet revision.
 *
 * Call this once per frame (or when measurements change) to avoid
 * recomputing every pointer-move.
 */
export function buildSnapCandidates(
  measurements: Measurement[],
  sheetRevisionId: string,
  config: SnapConfig,
  transform: TransformState
): SnapCandidate[] {
  if (!config.enabled) return [];

  const candidates: SnapCandidate[] = [];

  // Only snap to measurements on the same sheet revision
  const sheetMeasurements = measurements.filter(
    (m) => m.sheetRevisionId === sheetRevisionId && m.deletedAt === null
  );

  for (const m of sheetMeasurements) {
    const points = m.geometryWorld;
    if (!points || points.length === 0) continue;

    // Vertex snapping
    if (config.snapToVertices) {
      for (const p of points) {
        candidates.push({
          target: { type: "vertex", worldPoint: p, sourceId: m.id },
          screenPoint: worldToScreen(p, transform),
        });
      }
    }

    // Midpoint snapping (for linear and area types with segments)
    if (config.snapToMidpoints && points.length >= 2) {
      const segCount = m.type === "area" ? points.length : points.length - 1;
      for (let i = 0; i < segCount; i++) {
        const j = (i + 1) % points.length;
        const mid = midpoint(points[i], points[j]);
        candidates.push({
          target: { type: "midpoint", worldPoint: mid, sourceId: m.id },
          screenPoint: worldToScreen(mid, transform),
        });
      }
    }
  }

  // Grid snapping (if enabled)
  // Note: grid candidates are computed on-demand around the cursor
  // position to avoid generating thousands of candidates. See findSnapTarget.

  return candidates;
}

/**
 * Find the nearest snap target to a screen point, within tolerance.
 *
 * Returns null if no candidate is within tolerancePx.
 * The result is the snapped WORLD point (not screen point).
 *
 * Rule (§7): Snap tolerance is in CSS_PX because user "feel" is pixel-based.
 */
export function findSnapTarget(
  cursorScreen: ScreenPoint,
  candidates: SnapCandidate[],
  config: SnapConfig,
  transform: TransformState
): SnapTarget | null {
  if (!config.enabled) return null;

  let bestCandidate: SnapCandidate | null = null;
  let bestDistPx = Infinity;

  for (const c of candidates) {
    const dx = c.screenPoint.x - cursorScreen.x;
    const dy = c.screenPoint.y - cursorScreen.y;
    const distPx = Math.sqrt(dx * dx + dy * dy);

    if (distPx < config.tolerancePx && distPx < bestDistPx) {
      bestDistPx = distPx;
      bestCandidate = c;
    }
  }

  // Grid snapping: if no vertex/midpoint found, try grid.
  // Use the shared rotation-aware inverse — an inline unrotated inverse
  // would compute the wrong world point on rotated pages.
  if (!bestCandidate && config.snapToGrid && config.gridSpacingWorld > 0) {
    const cursorWorld = screenToWorld(cursorScreen, transform);
    const spacing = config.gridSpacingWorld;

    const snappedWorld: WorldPoint = {
      x: Math.round(cursorWorld.x / spacing) * spacing,
      y: Math.round(cursorWorld.y / spacing) * spacing,
    };

    const snappedScreen = worldToScreen(snappedWorld, transform);
    const dx = snappedScreen.x - cursorScreen.x;
    const dy = snappedScreen.y - cursorScreen.y;
    const distPx = Math.sqrt(dx * dx + dy * dy);

    if (distPx < config.tolerancePx) {
      return { type: "grid", worldPoint: snappedWorld };
    }
  }

  return bestCandidate?.target ?? null;
}

/**
 * Default snap configuration.
 */
export function defaultSnapConfig(): SnapConfig {
  return {
    enabled: true,
    tolerancePx: 10,
    snapToVertices: true,
    snapToMidpoints: true,
    snapToIntersections: false, // v0.2
    snapToGrid: false,
    gridSpacingWorld: 72, // 1 inch in PDF_PT
  };
}
