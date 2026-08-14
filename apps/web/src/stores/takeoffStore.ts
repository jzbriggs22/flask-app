/**
 * Takeoff Store — aligned with Takeoff Engine Spec v0.1.
 *
 * Key invariants enforced:
 *   §1.1: Stored measurements re-render identically given same PDF revision.
 *   §1.2: Every quantity is traceable (measurement → sheet revision → geometry).
 *   §1.4: Measurements are append-only; changes produce new versions.
 *   §1.5: Every measurement has a calibration reference or is flagged uncalibrated.
 *   §2:   All geometry stored in WORLD (PDF_PT), never in CSS pixels.
 *   §9:   Edit = new version; prior versions are immutable.
 *   §12:  Measurements belong to a specific sheet revision.
 */

import { create } from "zustand";
import { v4 as uuid } from "uuid";
import type {
  WorldPoint,
  TransformState,
  Measurement,
  MeasurementType,
  MeasurementVersion,
  TakeoffLayer,
  Calibration,
  CalibrationStatus,
  TakeoffEvent,
  TakeoffEventType,
  SnapConfig,
  SnapTarget,
  TakeoffErrorState,
} from "@openbuild/types";
import {
  computeQuantityRaw,
  computeQuantityReal,
  roundQuantity,
} from "@openbuild/pdf-engine";

export type MeasurementTool = "select" | "linear" | "area" | "count" | "calibrate";

interface TakeoffStore {
  // ============================================================
  // Tool state
  // ============================================================
  activeTool: MeasurementTool;
  setActiveTool: (tool: MeasurementTool) => void;

  // ============================================================
  // Transform (Spec §4) — per-page state
  // ============================================================
  transform: TransformState;
  setTransform: (transform: TransformState) => void;
  setZoom: (zoom: number) => void;
  setPan: (x: number, y: number) => void;

  // ============================================================
  // Active sheet revision (Spec §12)
  // ============================================================
  activeSheetRevisionId: string | null;
  setActiveSheetRevision: (id: string) => void;

  // ============================================================
  // Calibration (Spec §5)
  // ============================================================
  /** Per-sheet-revision calibrations. Key = sheetRevisionId. */
  calibrations: Record<string, Calibration>;
  calibrationStatus: CalibrationStatus;
  setCalibration: (sheetRevisionId: string, calibration: Calibration) => void;
  getCalibration: (sheetRevisionId: string) => Calibration | null;

  // Calibration in-progress state (two-point picking)
  calibrationPoint1: WorldPoint | null;
  setCalibrationPoint1: (point: WorldPoint) => void;
  clearCalibrationPoints: () => void;

  // ============================================================
  // Layers (Spec §8)
  // ============================================================
  layers: TakeoffLayer[];
  activeLayerId: string | null;
  setActiveLayer: (id: string) => void;
  addLayer: (data: { name: string; color: string }) => void;
  toggleLayerVisibility: (id: string) => void;

  // ============================================================
  // Measurements — materialized current state (Spec §6, §9)
  // ============================================================
  measurements: Measurement[];

  /**
   * Create a new measurement (Spec §9: append-only).
   * Automatically computes quantityRaw and quantityReal from geometry.
   * Also creates the initial MeasurementVersion and MEASUREMENT_CREATED event.
   */
  addMeasurement: (data: {
    type: MeasurementType;
    geometryWorld: WorldPoint[];
    costCode: string;
    label?: string;
    uom: string;
  }) => void;

  /**
   * "Edit" a measurement by creating a new version (Spec §9).
   * The old version remains immutable. Updates the materialized state.
   */
  updateMeasurement: (
    measurementId: string,
    update: {
      geometryWorld?: WorldPoint[];
      costCode?: string;
      label?: string;
      uom?: string;
    }
  ) => void;

  /**
   * Soft-delete a measurement (Spec §9).
   * Sets deletedAt; history remains.
   */
  softDeleteMeasurement: (measurementId: string) => void;

  // ============================================================
  // Measurement Versions (Spec §9) — append-only
  // ============================================================
  measurementVersions: MeasurementVersion[];

  // ============================================================
  // Events (Spec §9) — append-only audit log
  // ============================================================
  events: TakeoffEvent[];

  // ============================================================
  // Snapping (Spec §7)
  // ============================================================
  snapConfig: SnapConfig;
  setSnapConfig: (config: Partial<SnapConfig>) => void;
  /** Current snap target (set each pointer-move) */
  activeSnapTarget: SnapTarget | null;
  setActiveSnapTarget: (target: SnapTarget | null) => void;

  // ============================================================
  // In-progress measurement (WORLD points)
  // ============================================================
  activePoints: WorldPoint[];
  addPoint: (point: WorldPoint) => void;
  clearPoints: () => void;

  // ============================================================
  // Error states (Spec §15)
  // ============================================================
  errors: TakeoffErrorState[];
}

export const useTakeoffStore = create<TakeoffStore>((set, get) => ({
  // -- Tool state --
  activeTool: "select",
  setActiveTool: (tool) => set({ activeTool: tool, activePoints: [], calibrationPoint1: null }),

  // -- Transform (§4) --
  transform: {
    pageId: "",
    sheetRevisionId: "",
    pdfViewportScale: 1,
    pdfViewportRotation: 0,
    panX: 0,
    panY: 0,
    zoom: 1,
    devicePixelRatio: typeof window !== "undefined" ? window.devicePixelRatio : 1,
    pageWidthPt: 612,
    pageHeightPt: 792,
  },
  setTransform: (transform) => set({ transform }),
  setZoom: (zoom) =>
    set((state) => ({ transform: { ...state.transform, zoom } })),
  setPan: (x, y) =>
    set((state) => ({ transform: { ...state.transform, panX: x, panY: y } })),

  // -- Sheet revision (§12) --
  activeSheetRevisionId: null,
  setActiveSheetRevision: (id) => {
    set({ activeSheetRevisionId: id });
    // Update calibration status for new revision
    const cal = get().calibrations[id];
    set({
      calibrationStatus: cal
        ? { status: "calibrated", calibration: cal }
        : { status: "uncalibrated" },
    });
  },

  // -- Calibration (§5) --
  calibrations: {},
  calibrationStatus: { status: "uncalibrated" },
  setCalibration: (sheetRevisionId, calibration) => {
    set((state) => {
      const newCals = { ...state.calibrations, [sheetRevisionId]: calibration };
      const isActive = state.activeSheetRevisionId === sheetRevisionId;
      return {
        calibrations: newCals,
        calibrationStatus: isActive
          ? { status: "calibrated", calibration }
          : state.calibrationStatus,
        // Emit CALIBRATION_SET event
        events: [
          ...state.events,
          {
            id: uuid(),
            projectId: "",
            sheetRevisionId,
            eventType: "CALIBRATION_SET" as TakeoffEventType,
            measurementId: null,
            measurementVersionId: null,
            calibrationId: calibration.id,
            layerId: null,
            payload: { scaleFactor: calibration.scaleFactor, displayUnit: calibration.displayUnit },
            createdAt: new Date().toISOString(),
            createdBy: "",
          },
        ],
      };
    });
  },
  getCalibration: (sheetRevisionId) => get().calibrations[sheetRevisionId] ?? null,
  calibrationPoint1: null,
  setCalibrationPoint1: (point) => set({ calibrationPoint1: point }),
  clearCalibrationPoints: () => set({ calibrationPoint1: null }),

  // -- Layers (§8) --
  layers: [],
  activeLayerId: null,
  setActiveLayer: (id) => set({ activeLayerId: id }),
  addLayer: (data) => {
    const id = uuid();
    set((state) => ({
      layers: [
        ...state.layers,
        {
          id,
          drawingSetId: "",
          name: data.name,
          color: data.color,
          visible: true,
          costCode: "",
          sortOrder: state.layers.length,
          createdAt: new Date().toISOString(),
        },
      ],
      activeLayerId: id,
      events: [
        ...state.events,
        {
          id: uuid(),
          projectId: "",
          sheetRevisionId: null,
          eventType: "LAYER_CREATED" as TakeoffEventType,
          measurementId: null,
          measurementVersionId: null,
          calibrationId: null,
          layerId: id,
          payload: { name: data.name, color: data.color },
          createdAt: new Date().toISOString(),
          createdBy: "",
        },
      ],
    }));
  },
  toggleLayerVisibility: (id) =>
    set((state) => ({
      layers: state.layers.map((l) =>
        l.id === id ? { ...l, visible: !l.visible } : l
      ),
    })),

  // -- Measurements (§6, §9) --
  measurements: [],

  addMeasurement: (data) => {
    const state = get();
    const sheetRevisionId = state.activeSheetRevisionId;
    if (!sheetRevisionId || !state.activeLayerId) return;

    const calibration = state.calibrations[sheetRevisionId] ?? null;
    const quantityRaw = computeQuantityRaw(data.type, data.geometryWorld);
    const quantityReal = computeQuantityReal(data.type, quantityRaw, calibration);
    const roundedReal = quantityReal !== null ? roundQuantity(quantityReal, data.uom) : null;

    const measurementId = uuid();
    const versionId = uuid();
    const now = new Date().toISOString();

    const measurement: Measurement = {
      id: measurementId,
      layerId: state.activeLayerId,
      sheetRevisionId,
      type: data.type,
      geometryWorld: data.geometryWorld,
      calibrationId: calibration?.id ?? null,
      quantityRaw,
      quantityReal: roundedReal,
      uom: data.uom,
      version: 1,
      costCode: data.costCode,
      label: data.label,
      createdBy: "",
      createdAt: now,
      deletedAt: null,
    };

    const version: MeasurementVersion = {
      id: versionId,
      measurementId,
      versionNumber: 1,
      geometryWorld: data.geometryWorld,
      calibrationId: calibration?.id ?? null,
      quantityRaw,
      quantityReal: roundedReal,
      uom: data.uom,
      metadata: { label: data.label, costCode: data.costCode },
      createdAt: now,
      createdBy: "",
      supersedesVersionId: null,
    };

    const event: TakeoffEvent = {
      id: uuid(),
      projectId: "",
      sheetRevisionId,
      eventType: "MEASUREMENT_CREATED",
      measurementId,
      measurementVersionId: versionId,
      calibrationId: calibration?.id ?? null,
      layerId: state.activeLayerId,
      payload: { type: data.type, quantityRaw, quantityReal: roundedReal, uom: data.uom },
      createdAt: now,
      createdBy: "",
    };

    set((s) => ({
      measurements: [...s.measurements, measurement],
      measurementVersions: [...s.measurementVersions, version],
      events: [...s.events, event],
      activePoints: [],
    }));
  },

  updateMeasurement: (measurementId, update) => {
    const state = get();
    const existing = state.measurements.find((m) => m.id === measurementId);
    if (!existing || existing.deletedAt !== null) return;

    const geom = update.geometryWorld ?? existing.geometryWorld;
    const uom = update.uom ?? existing.uom;
    const calibration = state.calibrations[existing.sheetRevisionId] ?? null;
    const quantityRaw = computeQuantityRaw(existing.type, geom);
    const quantityReal = computeQuantityReal(existing.type, quantityRaw, calibration);
    const roundedReal = quantityReal !== null ? roundQuantity(quantityReal, uom) : null;

    const newVersion = existing.version + 1;
    const versionId = uuid();
    const now = new Date().toISOString();

    // Find previous version for supersedes link
    const prevVersions = state.measurementVersions
      .filter((v) => v.measurementId === measurementId)
      .sort((a, b) => b.versionNumber - a.versionNumber);
    const prevVersionId = prevVersions[0]?.id ?? null;

    const version: MeasurementVersion = {
      id: versionId,
      measurementId,
      versionNumber: newVersion,
      geometryWorld: geom,
      calibrationId: calibration?.id ?? null,
      quantityRaw,
      quantityReal: roundedReal,
      uom,
      metadata: {
        label: update.label ?? existing.label,
        costCode: update.costCode ?? existing.costCode,
      },
      createdAt: now,
      createdBy: "",
      supersedesVersionId: prevVersionId,
    };

    const event: TakeoffEvent = {
      id: uuid(),
      projectId: "",
      sheetRevisionId: existing.sheetRevisionId,
      eventType: "MEASUREMENT_UPDATED",
      measurementId,
      measurementVersionId: versionId,
      calibrationId: calibration?.id ?? null,
      layerId: existing.layerId,
      payload: { version: newVersion, changes: update },
      createdAt: now,
      createdBy: "",
    };

    set((s) => ({
      measurements: s.measurements.map((m) =>
        m.id === measurementId
          ? {
              ...m,
              geometryWorld: geom,
              calibrationId: calibration?.id ?? null,
              quantityRaw,
              quantityReal: roundedReal,
              uom,
              costCode: update.costCode ?? m.costCode,
              label: update.label ?? m.label,
              version: newVersion,
            }
          : m
      ),
      measurementVersions: [...s.measurementVersions, version],
      events: [...s.events, event],
    }));
  },

  softDeleteMeasurement: (measurementId) => {
    const now = new Date().toISOString();
    set((s) => ({
      measurements: s.measurements.map((m) =>
        m.id === measurementId ? { ...m, deletedAt: now } : m
      ),
      events: [
        ...s.events,
        {
          id: uuid(),
          projectId: "",
          sheetRevisionId: null,
          eventType: "MEASUREMENT_DELETED" as TakeoffEventType,
          measurementId,
          measurementVersionId: null,
          calibrationId: null,
          layerId: null,
          payload: {},
          createdAt: now,
          createdBy: "",
        },
      ],
    }));
  },

  // -- Versions (§9) --
  measurementVersions: [],

  // -- Events (§9) --
  events: [],

  // -- Snapping (§7) --
  snapConfig: {
    enabled: true,
    tolerancePx: 10,
    snapToVertices: true,
    snapToMidpoints: true,
    snapToIntersections: false,
    snapToGrid: false,
    gridSpacingWorld: 72,
  },
  setSnapConfig: (config) =>
    set((s) => ({ snapConfig: { ...s.snapConfig, ...config } })),
  activeSnapTarget: null,
  setActiveSnapTarget: (target) => set({ activeSnapTarget: target }),

  // -- In-progress measurement (WORLD points) --
  activePoints: [],
  addPoint: (point) =>
    set((s) => ({ activePoints: [...s.activePoints, point] })),
  clearPoints: () => set({ activePoints: [] }),

  // -- Errors (§15) --
  errors: [],
}));
