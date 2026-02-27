import { create } from "zustand";
import { v4 as uuid } from "uuid";

export type MeasurementTool = "select" | "linear" | "area" | "count";
export type MeasurementType = "linear" | "area" | "count";

export interface Point {
  x: number;
  y: number;
}

export interface Measurement {
  id: string;
  layerId: string;
  type: MeasurementType;
  /** For linear: length in drawing units; for area: area; for count: count */
  value: number;
  /** Display unit (ft, sf, ea, etc.) */
  unit: string;
  /** Points defining the measurement geometry */
  points: Point[];
  /** Associated cost code */
  costCode: string;
  sheetIndex: number;
  createdAt: string;
}

export interface TakeoffLayer {
  id: string;
  name: string;
  color: string;
  visible: boolean;
  costCode: string;
}

export interface ScaleCalibration {
  /** Two points on the drawing */
  point1: Point;
  point2: Point;
  /** Real-world distance in the specified unit */
  realDistance: number;
  unit: "ft" | "in" | "m" | "mm";
}

interface TakeoffStore {
  // Tool state
  activeTool: MeasurementTool;
  setActiveTool: (tool: MeasurementTool) => void;

  // Viewport
  zoom: number;
  setZoom: (zoom: number) => void;
  pan: Point;
  setPan: (pan: Point) => void;

  // Active sheet
  activeSheetIndex: number;
  setActiveSheet: (index: number) => void;

  // Scale calibration
  scale: ScaleCalibration | null;
  setScale: (scale: ScaleCalibration) => void;

  // Layers
  layers: TakeoffLayer[];
  activeLayerId: string | null;
  setActiveLayer: (id: string) => void;
  addLayer: (data: { name: string; color: string }) => void;
  toggleLayerVisibility: (id: string) => void;

  // Measurements
  measurements: Measurement[];
  addMeasurement: (data: Omit<Measurement, "id" | "createdAt">) => void;
  removeMeasurement: (id: string) => void;

  // In-progress measurement points
  activePoints: Point[];
  addPoint: (point: Point) => void;
  clearPoints: () => void;
}

export const useTakeoffStore = create<TakeoffStore>((set) => ({
  activeTool: "select",
  setActiveTool: (tool) => set({ activeTool: tool, activePoints: [] }),

  zoom: 1,
  setZoom: (zoom) => set({ zoom }),

  pan: { x: 0, y: 0 },
  setPan: (pan) => set({ pan }),

  activeSheetIndex: 0,
  setActiveSheet: (index) => set({ activeSheetIndex: index }),

  scale: null,
  setScale: (scale) => set({ scale }),

  layers: [],
  activeLayerId: null,
  setActiveLayer: (id) => set({ activeLayerId: id }),
  addLayer: (data) => {
    const id = uuid();
    set((state) => ({
      layers: [
        ...state.layers,
        { id, name: data.name, color: data.color, visible: true, costCode: "" },
      ],
      activeLayerId: id,
    }));
  },
  toggleLayerVisibility: (id) =>
    set((state) => ({
      layers: state.layers.map((l) =>
        l.id === id ? { ...l, visible: !l.visible } : l
      ),
    })),

  measurements: [],
  addMeasurement: (data) =>
    set((state) => ({
      measurements: [
        ...state.measurements,
        { ...data, id: uuid(), createdAt: new Date().toISOString() },
      ],
    })),
  removeMeasurement: (id) =>
    set((state) => ({
      measurements: state.measurements.filter((m) => m.id !== id),
    })),

  activePoints: [],
  addPoint: (point) =>
    set((state) => ({ activePoints: [...state.activePoints, point] })),
  clearPoints: () => set({ activePoints: [] }),
}));
