import { useState } from "react";
import { Link } from "react-router-dom";
import { Plus, FolderOpen, Search } from "lucide-react";
import { PageHeader } from "@/components/AppLayout";
import { useProjectStore } from "@/stores/projectStore";

export function ProjectsPage() {
  const { projects, createProject } = useProjectStore();
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newNumber, setNewNumber] = useState("");

  const filtered = projects.filter(
    (p) =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.number.toLowerCase().includes(search.toLowerCase())
  );

  const handleCreate = () => {
    if (!newName.trim()) return;
    createProject({ name: newName.trim(), number: newNumber.trim() });
    setNewName("");
    setNewNumber("");
    setShowCreate(false);
  };

  return (
    <>
      <PageHeader title="Projects">
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          <Plus className="h-4 w-4" />
          New Project
        </button>
      </PageHeader>

      <div className="flex-1 overflow-auto p-6">
        {/* Search */}
        <div className="relative mb-6 max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search projects..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-gray-300 py-2 pl-10 pr-4 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>

        {/* Create dialog */}
        {showCreate && (
          <div className="mb-6 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <h3 className="mb-4 text-sm font-semibold">Create New Project</h3>
            <div className="flex gap-4">
              <input
                type="text"
                placeholder="Project Name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                autoFocus
              />
              <input
                type="text"
                placeholder="Project Number"
                value={newNumber}
                onChange={(e) => setNewNumber(e.target.value)}
                className="w-40 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
              <button
                onClick={handleCreate}
                className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
              >
                Create
              </button>
              <button
                onClick={() => setShowCreate(false)}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Project grid */}
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-gray-500">
            <FolderOpen className="mb-4 h-12 w-12 text-gray-300" />
            <p className="text-sm">
              {projects.length === 0
                ? "No projects yet. Create your first project to get started."
                : "No projects match your search."}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((project) => (
              <Link
                key={project.id}
                to={`/projects/${project.id}`}
                className="group rounded-lg border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
              >
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-500">
                    {project.number || "No number"}
                  </span>
                  <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                    {project.status}
                  </span>
                </div>
                <h3 className="font-semibold text-gray-900 group-hover:text-brand-600">
                  {project.name}
                </h3>
                <p className="mt-1 text-xs text-gray-500">
                  Created {new Date(project.createdAt).toLocaleDateString()}
                </p>
              </Link>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
