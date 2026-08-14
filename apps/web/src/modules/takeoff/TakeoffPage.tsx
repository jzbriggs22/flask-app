/**
 * Takeoff Page — PDF viewer with measurement tools.
 * Aligned with Takeoff Engine Spec v0.1.
 *
 * Key spec sections implemented in UI:
 *   §5  — Calibration status banner + calibration tool
 *   §7  — Snap indicator
 *   §8  — Layers panel
 *   §15 — Error states displayed prominently
 */

import { useParams } from "react-router-dom";
import { useState } from "react";
import {
  Minus,
  Square,
  MousePointer,
  Hash,
  ZoomIn,
  ZoomOut,
  Layers,
  Ruler,
  AlertTriangle,
  CheckCircle2,
  Crosshair,
  Eye,
  EyeOff,
  Magnet,
} from "lucide-react";
import { PageHeader } from "@/components/AppLayout";
import { useProjectStore } from "@/stores/projectStore";
import { useTakeoffStore, type MeasurementTool } from "@/stores/takeoffStore";
import { roundQuantity } from "@openbuild/pdf-engine";

const tools: { id: MeasurementTool; label: string; icon: typeof Minus; shortcut: string }[] = [
  { id: "select", label: "Select (V)", icon: MousePointer, shortcut: "V" },
  { id: "linear", label: "Linear (L)", icon: Minus, shortcut: "L" },
  { id: "area", label: "Area (A)", icon: Square, shortcut: "A" },
  { id: "count", label: "Count (C)", icon: Hash, shortcut: "C" },
  { id: "calibrate", label: "Calibrate Scale (S)", icon: Ruler, shortcut: "S" },
];

const layerColors = [
  "#3b82f6", "#ef4444", "#22c55e", "#f59e0b",
  "#8b5cf6", "#ec4899", "#06b6d4", "#f97316",
];

export function TakeoffPage() {
  const { projectId, drawingSetId } = useParams<{
    projectId: string;
    drawingSetId: string;
  }>();
  const { projects } = useProjectStore();
  const {
    activeTool,
    setActiveTool,
    transform,
    setZoom,
    layers,
    activeLayerId,
    setActiveLayer,
    addLayer,
    toggleLayerVisibility,
    measurements,
    softDeleteMeasurement,
    calibrationStatus,
    activeSnapTarget,
    snapConfig,
    setSnapConfig,
    activePoints,
  } = useTakeoffStore();

  const project = projects.find((p) => p.id === projectId);
  const drawingSet = project?.drawingSets.find((ds) => ds.id === drawingSetId);
  const [showLayers, setShowLayers] = useState(true);

  if (!project || !drawingSet) {
    return (
      <div className="flex flex-1 items-center justify-center text-gray-500">
        Drawing set not found.
      </div>
    );
  }

  const zoom = transform.zoom;
  const visibleMeasurements = measurements.filter(
    (m) =>
      m.deletedAt === null &&
      layers.find((l) => l.id === m.layerId)?.visible !== false
  );

  return (
    <>
      <PageHeader title={`${project.name} — ${drawingSet.name}`}>
        {/* Calibration status (Spec §5, §15) */}
        <CalibrationBadge
          status={calibrationStatus}
          onCalibrateClick={() => setActiveTool("calibrate")}
        />

        {/* Snap toggle */}
        <button
          onClick={() => setSnapConfig({ enabled: !snapConfig.enabled })}
          className={`flex items-center gap-1 rounded-lg border px-2 py-1.5 text-xs font-medium transition-colors ${
            snapConfig.enabled
              ? "border-brand-200 bg-brand-50 text-brand-700"
              : "border-gray-200 text-gray-500"
          }`}
          title="Toggle snapping (Spec §7)"
        >
          <Magnet className="h-3.5 w-3.5" />
          Snap
        </button>

        {/* Zoom controls */}
        <div className="flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-1">
          <button
            onClick={() => setZoom(Math.max(0.25, zoom - 0.25))}
            className="rounded p-1.5 hover:bg-gray-100"
            title="Zoom Out"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          <span className="min-w-[3rem] text-center text-xs font-medium">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={() => setZoom(Math.min(4, zoom + 0.25))}
            className="rounded p-1.5 hover:bg-gray-100"
            title="Zoom In"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
        </div>
      </PageHeader>

      <div className="flex flex-1 overflow-hidden">
        {/* Toolbar */}
        <div className="flex w-12 flex-col items-center gap-1 border-r border-gray-200 bg-white py-3">
          {tools.map((tool) => {
            const Icon = tool.icon;
            return (
              <button
                key={tool.id}
                onClick={() => setActiveTool(tool.id)}
                className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors ${
                  activeTool === tool.id
                    ? "bg-brand-100 text-brand-700"
                    : "text-gray-500 hover:bg-gray-100"
                }`}
                title={tool.label}
              >
                <Icon className="h-4 w-4" />
              </button>
            );
          })}
          <div className="my-2 h-px w-6 bg-gray-200" />
          <button
            onClick={() => setShowLayers(!showLayers)}
            className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors ${
              showLayers
                ? "bg-brand-100 text-brand-700"
                : "text-gray-500 hover:bg-gray-100"
            }`}
            title="Layers"
          >
            <Layers className="h-4 w-4" />
          </button>
        </div>

        {/* PDF Viewer Area */}
        <div className="relative flex-1 overflow-auto bg-gray-100">
          <div className="flex h-full items-center justify-center">
            <div className="text-center text-gray-400">
              <Square className="mx-auto mb-3 h-16 w-16" />
              <p className="text-sm font-medium">PDF Viewer</p>
              <p className="mt-1 text-xs">
                Drawing will render here using PDF.js
              </p>
              <p className="mt-1 text-xs">
                {activeTool === "calibrate"
                  ? "Click two points with a known distance to calibrate scale"
                  : "Use the measurement tools on the left to begin takeoff"}
              </p>
            </div>
          </div>

          {/* Measurement overlay canvas */}
          <canvas
            className={`measurement-overlay ${activeTool !== "select" ? "active" : ""}`}
          />

          {/* Snap indicator (Spec §7) */}
          {activeSnapTarget && (
            <div className="pointer-events-none absolute left-2 bottom-2 flex items-center gap-1 rounded bg-black/70 px-2 py-1 text-xs text-white">
              <Crosshair className="h-3 w-3" />
              Snapped to {activeSnapTarget.type}
            </div>
          )}

          {/* Active points indicator (in-progress measurement) */}
          {activePoints.length > 0 && (
            <div className="absolute right-2 bottom-2 rounded bg-black/70 px-2 py-1 text-xs text-white">
              {activePoints.length} point{activePoints.length > 1 ? "s" : ""} placed
              {activeTool === "linear" && " — double-click or Enter to finish"}
              {activeTool === "area" && " — close polygon or Enter to finish"}
              {activeTool === "calibrate" && activePoints.length === 1 && " — click second point"}
            </div>
          )}

          {/* Measurement count */}
          <div className="absolute left-2 top-2 rounded bg-white/90 px-2 py-1 text-xs text-gray-600 shadow-sm">
            {visibleMeasurements.length} measurement{visibleMeasurements.length !== 1 ? "s" : ""}
          </div>
        </div>

        {/* Layers Panel */}
        {showLayers && (
          <div className="w-72 overflow-auto border-l border-gray-200 bg-white">
            <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                Layers
              </h3>
              <button
                onClick={() =>
                  addLayer({
                    name: `Layer ${layers.length + 1}`,
                    color: layerColors[layers.length % layerColors.length],
                  })
                }
                className="text-xs font-medium text-brand-600 hover:text-brand-700"
              >
                + Add
              </button>
            </div>
            <div className="divide-y divide-gray-100">
              {layers.map((layer) => {
                const layerMeasurements = measurements.filter(
                  (m) => m.layerId === layer.id && m.deletedAt === null
                );
                const uncalibrated = layerMeasurements.filter(
                  (m) => m.calibrationId === null
                );
                return (
                  <div
                    key={layer.id}
                    className={`flex items-center gap-3 px-4 py-3 transition-colors ${
                      activeLayerId === layer.id ? "bg-brand-50" : "hover:bg-gray-50"
                    }`}
                  >
                    <button
                      onClick={() => toggleLayerVisibility(layer.id)}
                      className="text-gray-400 hover:text-gray-600"
                      title={layer.visible ? "Hide layer" : "Show layer"}
                    >
                      {layer.visible ? (
                        <Eye className="h-4 w-4" />
                      ) : (
                        <EyeOff className="h-4 w-4" />
                      )}
                    </button>
                    <button
                      onClick={() => setActiveLayer(layer.id)}
                      className="flex flex-1 items-center gap-2 text-left min-w-0"
                    >
                      <div
                        className="h-3 w-3 flex-shrink-0 rounded-full"
                        style={{ backgroundColor: layer.color }}
                      />
                      <div className="flex-1 min-w-0">
                        <p className="truncate text-sm font-medium">
                          {layer.name}
                        </p>
                        <p className="text-xs text-gray-500">
                          {layerMeasurements.length} measurement{layerMeasurements.length !== 1 ? "s" : ""}
                          {uncalibrated.length > 0 && (
                            <span className="ml-1 text-amber-600">
                              ({uncalibrated.length} uncalibrated)
                            </span>
                          )}
                        </p>
                      </div>
                    </button>
                  </div>
                );
              })}
              {layers.length === 0 && (
                <p className="px-4 py-6 text-center text-xs text-gray-400">
                  Add a layer to organize your takeoff measurements.
                </p>
              )}
            </div>

            {/* Measurements list for active layer */}
            {activeLayerId && (
              <div className="border-t border-gray-200">
                <div className="px-4 py-2">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Measurements
                  </h4>
                </div>
                <div className="max-h-64 overflow-auto">
                  {measurements
                    .filter((m) => m.layerId === activeLayerId && m.deletedAt === null)
                    .map((m) => (
                      <div
                        key={m.id}
                        className="flex items-center justify-between px-4 py-2 text-xs hover:bg-gray-50"
                      >
                        <div>
                          <span className="font-medium capitalize">{m.type}</span>
                          {m.label && (
                            <span className="ml-1 text-gray-500">— {m.label}</span>
                          )}
                          <div className="text-gray-500">
                            {m.quantityReal !== null ? (
                              <span>
                                {roundQuantity(m.quantityReal, m.uom)} {m.uom}
                              </span>
                            ) : (
                              <span className="text-amber-600">
                                {m.quantityRaw.toFixed(1)} PDF_PT (uncalibrated)
                              </span>
                            )}
                            <span className="ml-1 text-gray-400">v{m.version}</span>
                          </div>
                        </div>
                        <button
                          onClick={() => softDeleteMeasurement(m.id)}
                          className="text-gray-400 hover:text-red-500"
                          title="Delete measurement"
                        >
                          &times;
                        </button>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}

// ============================================================
// Calibration Status Badge (Spec §5, §15)
// ============================================================

function CalibrationBadge({
  status,
  onCalibrateClick,
}: {
  status: { status: string; calibration?: { scaleFactor: number; displayUnit: string; realDistance: number }; reason?: string };
  onCalibrateClick: () => void;
}) {
  if (status.status === "calibrated" && status.calibration) {
    return (
      <div className="flex items-center gap-1.5 rounded-lg border border-green-200 bg-green-50 px-2.5 py-1.5 text-xs font-medium text-green-700">
        <CheckCircle2 className="h-3.5 w-3.5" />
        Calibrated ({status.calibration.realDistance} {status.calibration.displayUnit})
      </div>
    );
  }

  if (status.status === "invalidated") {
    return (
      <button
        onClick={onCalibrateClick}
        className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-2.5 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100"
      >
        <AlertTriangle className="h-3.5 w-3.5" />
        Calibration invalidated — recalibrate
      </button>
    );
  }

  // Uncalibrated
  return (
    <button
      onClick={onCalibrateClick}
      className="flex items-center gap-1.5 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-100"
    >
      <AlertTriangle className="h-3.5 w-3.5" />
      Uncalibrated — set scale
    </button>
  );
}
