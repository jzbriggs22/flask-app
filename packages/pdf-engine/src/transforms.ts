/**
 * Coordinate Transform Pipeline (Spec §4)
 *
 * Three coordinate spaces:
 *   A) PDF Page Space (PDF_PT / WORLD) — canonical storage
 *   B) Screen/Canvas Space (CSS_PX) — user input
 *   C) (Device pixels are an internal rendering concern only)
 *
 * Rule: All tools operate in WORLD; only projection and input
 * conversion touch CSS_PX.
 *
 * Rule: Use PDF.js conversion helpers whenever possible; only use
 * custom matrices if we can prove equivalence.
 */

import type { WorldPoint, ScreenPoint, TransformState } from "@openbuild/types";

/**
 * Helper functions derived from a TransformState.
 * Create once per render frame; reuse for all conversions.
 */
export interface TransformHelpers {
  /** Convert user pointer (CSS_PX) → WORLD (PDF_PT) */
  screenToWorld: (screen: ScreenPoint) => WorldPoint;
  /** Convert WORLD (PDF_PT) → screen (CSS_PX) for drawing */
  worldToScreen: (world: WorldPoint) => ScreenPoint;
  /** Convert a CSS_PX distance to WORLD distance at current zoom */
  screenDistanceToWorld: (pxDistance: number) => number;
  /** Convert a WORLD distance to CSS_PX distance at current zoom */
  worldDistanceToScreen: (worldDistance: number) => number;
}

/**
 * Create a default TransformState for a page.
 */
export function createTransformState(
  pageId: string,
  sheetRevisionId: string,
  pageWidthPt: number,
  pageHeightPt: number,
  pdfViewportScale: number
): TransformState {
  return {
    pageId,
    sheetRevisionId,
    pdfViewportScale,
    pdfViewportRotation: 0,
    panX: 0,
    panY: 0,
    zoom: 1,
    devicePixelRatio: typeof window !== "undefined" ? window.devicePixelRatio : 1,
    pageWidthPt,
    pageHeightPt,
  };
}

/**
 * Convert Screen (CSS_PX) → WORLD (PDF_PT).
 *
 * Pipeline (§4):
 *   1. Remove pan offset in CSS_PX
 *   2. Divide by (zoom * pdfViewportScale)
 *   → Result is in PDF_PT (WORLD)
 */
export function screenToWorld(
  screen: ScreenPoint,
  state: TransformState
): WorldPoint {
  const effectiveScale = state.zoom * state.pdfViewportScale;
  const x = (screen.x - state.panX) / effectiveScale;
  const y = (screen.y - state.panY) / effectiveScale;

  // Handle rotation: rotate the inverse direction
  switch (state.pdfViewportRotation) {
    case 90:
      return { x: y, y: state.pageWidthPt - x };
    case 180:
      return { x: state.pageWidthPt - x, y: state.pageHeightPt - y };
    case 270:
      return { x: state.pageHeightPt - y, y: x };
    default: // 0
      return { x, y };
  }
}

/**
 * Convert WORLD (PDF_PT) → Screen (CSS_PX).
 *
 * Pipeline (§4):
 *   1. Convert WORLD to viewport coords (apply pdfViewportScale)
 *   2. Multiply by zoom
 *   3. Add pan offset
 */
export function worldToScreen(
  world: WorldPoint,
  state: TransformState
): ScreenPoint {
  let x: number;
  let y: number;

  // Handle rotation
  switch (state.pdfViewportRotation) {
    case 90:
      x = state.pageWidthPt - world.y;
      y = world.x;
      break;
    case 180:
      x = state.pageWidthPt - world.x;
      y = state.pageHeightPt - world.y;
      break;
    case 270:
      x = world.y;
      y = state.pageHeightPt - world.x;
      break;
    default: // 0
      x = world.x;
      y = world.y;
      break;
  }

  const effectiveScale = state.zoom * state.pdfViewportScale;
  return {
    x: x * effectiveScale + state.panX,
    y: y * effectiveScale + state.panY,
  };
}

/**
 * Build a helpers object from a TransformState.
 * Efficiently reuse for multiple conversions in one frame.
 */
export function buildTransformHelpers(state: TransformState): TransformHelpers {
  const effectiveScale = state.zoom * state.pdfViewportScale;

  return {
    screenToWorld: (screen) => screenToWorld(screen, state),
    worldToScreen: (world) => worldToScreen(world, state),
    screenDistanceToWorld: (pxDistance) => pxDistance / effectiveScale,
    worldDistanceToScreen: (worldDistance) => worldDistance * effectiveScale,
  };
}
