import { useParams, Link } from "react-router-dom";
import { Upload, FileText, Ruler, Calculator, Plus } from "lucide-react";
import { PageHeader } from "@/components/AppLayout";
import { useProjectStore } from "@/stores/projectStore";
import { useState, useRef } from "react";

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { projects, addDrawingSet, addEstimate } = useProjectStore();
  const project = projects.find((p) => p.id === projectId);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  if (!project) {
    return (
      <div className="flex flex-1 items-center justify-center text-gray-500">
        Project not found.
      </div>
    );
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0 || !projectId) return;

    setUploading(true);
    // In MVP, we store a reference to the file. Full upload goes to S3/MinIO in production.
    const file = files[0];
    addDrawingSet(projectId, {
      name: file.name.replace(/\.pdf$/i, ""),
      fileName: file.name,
      fileSize: file.size,
    });
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleNewEstimate = () => {
    if (!projectId) return;
    addEstimate(projectId, { name: `Estimate ${project.estimates.length + 1}` });
  };

  return (
    <>
      <PageHeader title={project.name}>
        <span className="text-sm text-gray-500">{project.number}</span>
      </PageHeader>

      <div className="flex-1 overflow-auto p-6">
        {/* Drawing Sets */}
        <section className="mb-8">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700">
              Drawing Sets
            </h2>
            <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50">
              <Upload className="h-4 w-4" />
              {uploading ? "Uploading..." : "Upload PDF"}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={handleFileUpload}
              />
            </label>
          </div>

          {project.drawingSets.length === 0 ? (
            <div className="rounded-lg border-2 border-dashed border-gray-200 p-8 text-center">
              <FileText className="mx-auto mb-3 h-10 w-10 text-gray-300" />
              <p className="text-sm text-gray-500">
                Upload a PDF drawing set to start your takeoff.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {project.drawingSets.map((ds) => (
                <Link
                  key={ds.id}
                  to={`/projects/${projectId}/takeoff/${ds.id}`}
                  className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4 hover:bg-gray-50"
                >
                  <div className="flex items-center gap-3">
                    <Ruler className="h-5 w-5 text-brand-600" />
                    <div>
                      <p className="text-sm font-medium">{ds.name}</p>
                      <p className="text-xs text-gray-500">
                        {(ds.fileSize / 1024 / 1024).toFixed(1)} MB &middot;{" "}
                        {new Date(ds.createdAt).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <span className="text-xs text-gray-400">Open Takeoff →</span>
                </Link>
              ))}
            </div>
          )}
        </section>

        {/* Estimates */}
        <section>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-700">Estimates</h2>
            <button
              onClick={handleNewEstimate}
              className="flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              <Plus className="h-4 w-4" />
              New Estimate
            </button>
          </div>

          {project.estimates.length === 0 ? (
            <div className="rounded-lg border-2 border-dashed border-gray-200 p-8 text-center">
              <Calculator className="mx-auto mb-3 h-10 w-10 text-gray-300" />
              <p className="text-sm text-gray-500">
                Create an estimate to start costing your takeoff quantities.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {project.estimates.map((est) => (
                <Link
                  key={est.id}
                  to={`/projects/${projectId}/estimate/${est.id}`}
                  className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4 hover:bg-gray-50"
                >
                  <div className="flex items-center gap-3">
                    <Calculator className="h-5 w-5 text-green-600" />
                    <div>
                      <p className="text-sm font-medium">{est.name}</p>
                      <p className="text-xs text-gray-500">
                        {est.lineItems.length} line items &middot;{" "}
                        {new Date(est.createdAt).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <span className="text-xs text-gray-400">
                    Open Estimate →
                  </span>
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </>
  );
}
