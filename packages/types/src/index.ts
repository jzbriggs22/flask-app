// ============================================================
// OpenBuild Core Types
// Aligned with Takeoff Engine Spec v0.1 ("Trust the Pixels")
// ============================================================

/** UUID identifier */
export type Id = string;

/** ISO 8601 timestamp */
export type Timestamp = string;

/** Monetary value in cents (integer). Never use floating point for money. */
export type Cents = number;

// ============================================================
// Coordinate Systems (Spec §2)
// ============================================================

/**
 * WORLD space point — canonical storage coordinate.
 * Units: PDF points (1/72 inch), as defined by PDF.js viewport.
 * Origin: top-left of the rendered page viewport.
 * Axes: +x right, +y down.
 *
 * Rule: ALL geometry is persisted in WORLD. Never in pixels.
 */
export interface WorldPoint {
  x: number;
  y: number;
}

/**
 * Screen/Canvas space point.
 * Units: CSS pixels.
 * Origin: overlay canvas top-left.
 * Used for user input only — never persisted.
 */
export interface ScreenPoint {
  x: number;
  y: number;
}

// ============================================================
// Transform Pipeline (Spec §4)
// ============================================================

/**
 * Per-page transform state for converting between WORLD and Screen.
 * Maintained by the PDF viewer for every rendered page.
 */
export interface TransformState {
  pageId: Id;
  sheetRevisionId: Id;
  /** PDF.js viewport scale (not user zoom) */
  pdfViewportScale: number;
  /** PDF.js viewport rotation (0, 90, 180, 270) */
  pdfViewportRotation: number;
  /** User pan offset in CSS pixels */
  panX: number;
  panY: number;
  /** User zoom multiplier (1 = 100%) */
  zoom: number;
  /** Device pixel ratio for HiDPI rendering */
  devicePixelRatio: number;
  /** PDF page dimensions in PDF_PT */
  pageWidthPt: number;
  pageHeightPt: number;
}

// ============================================================
// Organization & Auth
// ============================================================

export type UserRole =
  | "admin"
  | "pm"
  | "estimator"
  | "super"
  | "sub"
  | "owner"
  | "architect";

export interface User {
  id: Id;
  email: string;
  name: string;
  role: UserRole;
  organizationId: Id;
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

export interface Organization {
  id: Id;
  name: string;
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

// ============================================================
// Projects
// ============================================================

export type ProjectStatus = "active" | "archived" | "bid" | "closed";

export interface Project {
  id: Id;
  organizationId: Id;
  name: string;
  number: string;
  status: ProjectStatus;
  address?: string;
  createdBy: Id;
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

// ============================================================
// Drawings & Revisions (Spec §12)
// ============================================================

export interface DrawingSet {
  id: Id;
  projectId: Id;
  name: string;
  revision: number;
  fileUrl: string;
  fileSize: number;
  sheetCount: number;
  createdBy: Id;
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

export interface DrawingSheet {
  id: Id;
  drawingSetId: Id;
  sheetNumber: string;
  title: string;
  pageIndex: number;
  thumbnailUrl?: string;
}

/**
 * A specific version of a sheet. Measurements bind to revisions, not sheets.
 * When a new revision is uploaded, old measurements stay on the old revision.
 * Rule (§12): Never silently move measurements across revisions.
 */
export interface DrawingSheetRevision {
  id: Id;
  sheetId: Id;
  drawingSetId: Id;
  revisionNumber: number;
  fileUrl: string;
  pageIndex: number;
  uploadedAt: Timestamp;
  uploadedBy: Id;
  /** PDF page width in points (1/72 inch) */
  pageWidthPt: number | null;
  /** PDF page height in points */
  pageHeightPt: number | null;
  rotation: number;
}

// ============================================================
// Scale Calibration (Spec §5)
// ============================================================

export type UnitSystem = "imperial" | "metric";
export type DisplayUnit = "in" | "ft" | "mm" | "m";
export type CalibrationMethod = "two-point" | "known-scale-text" | "pdf-embedded";
export type CalibrationConfidence = "exact" | "estimated";

/**
 * Maps WORLD (PDF_PT) → Real-world units.
 * Bound to a specific sheet revision.
 *
 * Rule (§5): A measurement is "calibrated" if it references a calibration_id
 * tied to the same sheet revision. If revision changes, calibration is not
 * automatically reused.
 */
export interface Calibration {
  id: Id;
  sheetRevisionId: Id;
  unitSystem: UnitSystem;
  displayUnit: DisplayUnit;
  /** Two calibration points in WORLD (PDF_PT) */
  point1: WorldPoint;
  point2: WorldPoint;
  /** Distance between points in WORLD (PDF_PT) */
  worldDistancePt: number;
  /** Known real-world distance */
  realDistance: number;
  /** scale_factor = realDistance / worldDistancePt (real units per PDF_PT) */
  scaleFactor: number;
  method: CalibrationMethod;
  confidence: CalibrationConfidence;
  createdBy: Id;
  createdAt: Timestamp;
}

/**
 * Calibration status shown in the UI.
 * Rule (§5, §15): UI must always show calibration status prominently.
 */
export type CalibrationStatus =
  | { status: "calibrated"; calibration: Calibration }
  | { status: "uncalibrated" }
  | { status: "invalidated"; reason: string };

// ============================================================
// Takeoff (Spec §6, §8)
// ============================================================

export type MeasurementType = "linear" | "area" | "count" | "volume";

/**
 * Geometry formats per spec §6.
 * All coordinates in WORLD (PDF_PT).
 */
export type MeasurementGeometry =
  | { type: "linear"; polyline: WorldPoint[] }
  | { type: "area"; polygon: WorldPoint[] }
  | { type: "count"; points: WorldPoint[] }
  | { type: "volume"; polygon: WorldPoint[]; thickness: number };

/**
 * Layer is organizational; styling is a view concern (§8).
 */
export interface TakeoffLayer {
  id: Id;
  drawingSetId: Id;
  name: string;
  color: string;
  costCode: string;
  visible: boolean;
  sortOrder: number;
  createdAt: Timestamp;
}

/**
 * Core measurement entity (materialized current state).
 * Per spec §6: every measurement has a calibration reference or is uncalibrated.
 */
export interface Measurement {
  id: Id;
  layerId: Id;
  sheetRevisionId: Id;
  type: MeasurementType;
  /** Geometry stored in WORLD (PDF_PT). Rule §2: never in pixels. */
  geometryWorld: WorldPoint[];
  /** Reference to calibration used. Null = uncalibrated (§5). */
  calibrationId: Id | null;
  /** Raw quantity derived from WORLD geometry (PDF_PT units) */
  quantityRaw: number;
  /** Real-world quantity after calibration. Null if uncalibrated. */
  quantityReal: number | null;
  /** Unit of measure for real quantity (ft, sf, ea, etc.) */
  uom: string;
  version: number;
  costCode: string;
  label?: string;
  createdBy: Id;
  createdAt: Timestamp;
  deletedAt: Timestamp | null;
}

// ============================================================
// Measurement Versioning (Spec §9)
// ============================================================

/**
 * Immutable version record.
 * Rule (§9): "Edit measurement" creates a new version; prior versions remain immutable.
 */
export interface MeasurementVersion {
  id: Id;
  measurementId: Id;
  versionNumber: number;
  geometryWorld: WorldPoint[];
  calibrationId: Id | null;
  quantityRaw: number;
  quantityReal: number | null;
  uom: string;
  metadata: MeasurementMetadata;
  createdAt: Timestamp;
  createdBy: Id;
  supersedesVersionId: Id | null;
}

export interface MeasurementMetadata {
  label?: string;
  notes?: string;
  tags?: string[];
  costCode?: string;
}

// ============================================================
// Takeoff Events (Spec §9)
// ============================================================

export type TakeoffEventType =
  | "MEASUREMENT_CREATED"
  | "MEASUREMENT_UPDATED"
  | "MEASUREMENT_DELETED"
  | "CALIBRATION_SET"
  | "CALIBRATION_INVALIDATED"
  | "LAYER_CREATED"
  | "LAYER_UPDATED"
  | "LAYER_DELETED"
  | "REVISION_UPLOADED";

export interface TakeoffEvent {
  id: Id;
  projectId: Id;
  sheetRevisionId: Id | null;
  eventType: TakeoffEventType;
  measurementId: Id | null;
  measurementVersionId: Id | null;
  calibrationId: Id | null;
  layerId: Id | null;
  payload: Record<string, unknown>;
  createdAt: Timestamp;
  createdBy: Id;
}

// ============================================================
// Snapping (Spec §7)
// ============================================================

export type SnapTargetType = "vertex" | "midpoint" | "intersection" | "grid";

export interface SnapTarget {
  type: SnapTargetType;
  worldPoint: WorldPoint;
  /** Source measurement id (for vertex/midpoint snaps) */
  sourceId?: Id;
}

export interface SnapConfig {
  enabled: boolean;
  /** Tolerance in CSS pixels (user "feel" is pixel-based). Default 8-12px. */
  tolerancePx: number;
  snapToVertices: boolean;
  snapToMidpoints: boolean;
  snapToIntersections: boolean;
  snapToGrid: boolean;
  gridSpacingWorld: number;
}

// ============================================================
// Estimating (Spec §11)
// ============================================================

export interface Estimate {
  id: Id;
  projectId: Id;
  name: string;
  status: "draft" | "submitted" | "approved";
  createdBy: Id;
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

export type LineItemSourceType = "manual" | "driven";

/**
 * Estimate line item with traceability (§11).
 * Line Item → Quantity → Measurement(s) → Sheet Revision → Pixel location.
 */
export interface EstimateLineItem {
  id: Id;
  estimateId: Id;
  costCode: string;
  description: string;
  quantity: number;
  unit: string;
  /** Unit cost in cents. Invariant §3: Money uses integers only. */
  unitCostCents: Cents;
  sourceType: LineItemSourceType;
  /** For driven items: quantity snapshot at time of pricing (§11) */
  quantitySnapshot: number | null;
  snapshotAt: Timestamp | null;
  /** True if source measurements changed since snapshot (§11) */
  isStale: boolean;
  sortOrder: number;
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

/**
 * Link between a line item and its source measurements (§11).
 * A driven line item can reference one or more measurements.
 */
export interface EstimateLineItemSource {
  id: Id;
  lineItemId: Id;
  measurementId: Id;
  measurementVersionId: Id;
  /** Snapshot of the measurement quantity when linked */
  quantitySnapshot: number;
  uomSnapshot: string;
  linkedAt: Timestamp;
  linkedBy: Id;
}

// ============================================================
// Quantity & Rounding (Spec §10)
// ============================================================

/**
 * Precision rules per unit of measure.
 * Rule (§10): the number a user sees in-app must match exports.
 */
export const UOM_PRECISION: Record<string, number> = {
  ft: 2,
  in: 2,
  sf: 2,
  sy: 2,
  cy: 2,
  ea: 0,
  ton: 2,
  lb: 0,
  gal: 0,
  hr: 2,
  day: 2,
  ls: 2,
  m: 3,
  mm: 0,
  sm: 2,
};

// ============================================================
// Error States (Spec §15)
// ============================================================

export type TakeoffErrorState =
  | { type: "uncalibrated_page"; sheetRevisionId: Id }
  | { type: "calibration_invalidated"; calibrationId: Id; reason: string }
  | { type: "quantity_stale"; lineItemId: Id; currentQuantity: number; snapshotQuantity: number }
  | { type: "missing_revision"; measurementId: Id };

// ============================================================
// Cost Codes (CSI MasterFormat)
// ============================================================

export interface CostCodeDivision {
  code: string;
  title: string;
}

export interface CostCodeSection {
  code: string;
  title: string;
  divisionCode: string;
}

// ============================================================
// API Pagination
// ============================================================

export interface CursorPage<T> {
  data: T[];
  nextCursor: string | null;
  hasMore: boolean;
}

// ============================================================
// API Errors
// ============================================================

export interface ApiErrorResponse {
  code: string;
  message: string;
  details?: Record<string, string>;
}
