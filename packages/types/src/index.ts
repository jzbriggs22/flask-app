// ============================================================
// OpenBuild Core Types
// ============================================================

/** UUID identifier */
export type Id = string;

/** ISO 8601 timestamp */
export type Timestamp = string;

/** Monetary value in cents (integer). Never use floating point for money. */
export type Cents = number;

// --- Organization & Auth ---

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

// --- Projects ---

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

// --- Drawings ---

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

// --- Takeoff ---

export type MeasurementType = "linear" | "area" | "count" | "volume";

export interface Point2D {
  x: number;
  y: number;
}

export interface ScaleCalibration {
  point1: Point2D;
  point2: Point2D;
  realDistance: number;
  unit: "ft" | "in" | "m" | "mm";
}

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

export interface Measurement {
  id: Id;
  layerId: Id;
  sheetId: Id;
  type: MeasurementType;
  points: Point2D[];
  value: number;
  unit: string;
  costCode: string;
  label?: string;
  createdBy: Id;
  createdAt: Timestamp;
}

// --- Estimating ---

export interface Estimate {
  id: Id;
  projectId: Id;
  name: string;
  status: "draft" | "submitted" | "approved";
  createdBy: Id;
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

export interface EstimateLineItem {
  id: Id;
  estimateId: Id;
  costCode: string;
  description: string;
  quantity: number;
  unit: string;
  /** Unit cost in cents */
  unitCostCents: Cents;
  /** Link back to the takeoff measurement that generated this quantity */
  measurementId?: Id;
  sortOrder: number;
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

// --- Cost Codes (CSI MasterFormat) ---

export interface CostCodeDivision {
  code: string;
  title: string;
}

export interface CostCodeSection {
  code: string;
  title: string;
  divisionCode: string;
}

// --- API Pagination ---

export interface CursorPage<T> {
  data: T[];
  nextCursor: string | null;
  hasMore: boolean;
}

// --- API Errors ---

export interface ApiErrorResponse {
  code: string;
  message: string;
  details?: Record<string, string>;
}
