import { useParams } from "react-router-dom";
import { useState } from "react";
import {
  Minus,
  Square,
  MousePointer,
  Hash,
  ZoomIn,
  ZoomOut,
  RotateCw,
  Layers,
  Palette,
} from "lucide-react";
import { PageHeader } from "@/components/AppLayout";
import { useProjectStore } from "@/stores/projectStore";
import { useTakeoffStore, MeasurementTool } from "@/stores/takeoffStore";

const tools: { id: MeasurementTool; label: string; icon: typeof Minus }[] = [
  { id: "select", label: "Select", icon: MousePointer },
  { id: "linear", label: "Linear", icon: Minus },
  { id: "area", label: "Area", icon: Square },
  { id: "count", label: "Count", icon: Hash },
];

const layerColors = [
  "#3b82f6",
  "#ef4444",
  "#22c55e",
  "#f59e0b",
  "#8b5cf6",
  "#ec4899",
  "#06b6d4",
  "#f97316",
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
    zoom,
    setZoom,
    layers,
    activeLayerId,
    setActiveLayer,
    addLayer,
    measurements,
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

  return (
    <>
      <PageHeader title={`${project.name} — ${drawingSet.name}`}>
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
                Use the measurement tools on the left to begin takeoff
              </p>
            </div>
          </div>

          {/* Measurement overlay canvas */}
          <canvas
            className={`measurement-overlay ${activeTool !== "select" ? "active" : ""}`}
          />
        </div>

        {/* Layers Panel */}
        {showLayers && (
          <div className="w-64 overflow-auto border-l border-gray-200 bg-white">
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
                  (m) => m.layerId === layer.id
                );
                return (
                  <button
                    key={layer.id}
                    onClick={() => setActiveLayer(layer.id)}
                    className={`flex w-full items-center gap-3 px-4 py-3 text-left transition-colors ${
                      activeLayerId === layer.id
                        ? "bg-brand-50"
                        : "hover:bg-gray-50"
                    }`}
                  >
                    <div
                      className="h-3 w-3 rounded-full"
                      style={{ backgroundColor: layer.color }}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="truncate text-sm font-medium">
                        {layer.name}
                      </p>
                      <p className="text-xs text-gray-500">
                        {layerMeasurements.length} measurements
                      </p>
                    </div>
                  </button>
                );
              })}
              {layers.length === 0 && (
                <p className="px-4 py-6 text-center text-xs text-gray-400">
                  Add a layer to organize your takeoff measurements.
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
