/**
 * Estimate Page — cost estimation with traceability.
 * Aligned with Takeoff Engine Spec v0.1 §11.
 *
 * Key features:
 *   - Manual and driven line items
 *   - Quantity snapshots at time of pricing
 *   - Stale quantity detection ("out of date" warning)
 *   - Full traceability: Line Item → Quantity → Measurement(s)
 *   - Money in cents (integer arithmetic only, §3)
 */

import { useParams } from "react-router-dom";
import { useState } from "react";
import { Plus, Download, Trash2, AlertTriangle, Link2, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/AppLayout";
import { useProjectStore } from "@/stores/projectStore";
import { CSI_DIVISIONS } from "@openbuild/cost-codes";

export function EstimatePage() {
  const { projectId, estimateId } = useParams<{
    projectId: string;
    estimateId: string;
  }>();
  const { projects, addLineItem, removeLineItem } = useProjectStore();

  const project = projects.find((p) => p.id === projectId);
  const estimate = project?.estimates.find((e) => e.id === estimateId);

  const [newItem, setNewItem] = useState({
    description: "",
    costCode: "",
    quantity: "",
    unit: "",
    unitCost: "",
  });

  if (!project || !estimate) {
    return (
      <div className="flex flex-1 items-center justify-center text-gray-500">
        Estimate not found.
      </div>
    );
  }

  const handleAddItem = () => {
    if (!newItem.description || !estimateId || !projectId) return;
    addLineItem(projectId, estimateId, {
      description: newItem.description,
      costCode: newItem.costCode,
      quantity: parseFloat(newItem.quantity) || 0,
      unit: newItem.unit,
      unitCostCents: Math.round((parseFloat(newItem.unitCost) || 0) * 100),
    });
    setNewItem({
      description: "",
      costCode: "",
      quantity: "",
      unit: "",
      unitCost: "",
    });
  };

  // Calculate totals — integer arithmetic for money (Spec §3)
  const totalCents = estimate.lineItems.reduce(
    (sum, item) => sum + Math.round(item.quantity * item.unitCostCents),
    0
  );

  // Count stale items (Spec §11)
  const staleCount = estimate.lineItems.filter((item) => item.isStale).length;

  const formatCurrency = (cents: number) =>
    `$${(cents / 100).toLocaleString("en-US", { minimumFractionDigits: 2 })}`;

  return (
    <>
      <PageHeader title={`${project.name} — ${estimate.name}`}>
        {staleCount > 0 && (
          <div className="flex items-center gap-1.5 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-xs font-medium text-amber-700">
            <AlertTriangle className="h-3.5 w-3.5" />
            {staleCount} item{staleCount > 1 ? "s" : ""} out of date
          </div>
        )}
        <button
          className="flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
          title="Export to Excel"
        >
          <Download className="h-4 w-4" />
          Export
        </button>
      </PageHeader>

      <div className="flex-1 overflow-auto p-6">
        {/* Summary cards */}
        <div className="mb-6 grid grid-cols-4 gap-4">
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <p className="text-xs font-medium text-gray-500">Total Estimate</p>
            <p className="mt-1 text-2xl font-bold text-gray-900">
              {formatCurrency(totalCents)}
            </p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <p className="text-xs font-medium text-gray-500">Line Items</p>
            <p className="mt-1 text-2xl font-bold text-gray-900">
              {estimate.lineItems.length}
            </p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <p className="text-xs font-medium text-gray-500">Cost Codes</p>
            <p className="mt-1 text-2xl font-bold text-gray-900">
              {new Set(estimate.lineItems.map((i) => i.costCode)).size}
            </p>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <p className="text-xs font-medium text-gray-500">Source</p>
            <div className="mt-1 flex gap-2 text-xs">
              <span className="rounded bg-gray-100 px-1.5 py-0.5 font-medium text-gray-600">
                {estimate.lineItems.filter((i) => (i.sourceType ?? "manual") === "manual").length} manual
              </span>
              <span className="rounded bg-blue-100 px-1.5 py-0.5 font-medium text-blue-600">
                {estimate.lineItems.filter((i) => i.sourceType === "driven").length} driven
              </span>
            </div>
          </div>
        </div>

        {/* Line items table */}
        <div className="rounded-lg border border-gray-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                <th className="w-8 px-2 py-3"></th>
                <th className="px-4 py-3">Cost Code</th>
                <th className="px-4 py-3">Description</th>
                <th className="px-4 py-3 text-right">Quantity</th>
                <th className="px-4 py-3">Unit</th>
                <th className="px-4 py-3 text-right">Unit Cost</th>
                <th className="px-4 py-3 text-right">Total</th>
                <th className="px-4 py-3 w-10"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {estimate.lineItems.map((item) => {
                const isStale = item.isStale ?? false;
                const sourceType = item.sourceType ?? "manual";
                return (
                  <tr
                    key={item.id}
                    className={`hover:bg-gray-50 ${isStale ? "bg-amber-50/50" : ""}`}
                  >
                    {/* Source indicator */}
                    <td className="px-2 py-3 text-center">
                      {sourceType === "driven" ? (
                        <span title="Driven from takeoff measurements">
                          <Link2 className="inline h-3.5 w-3.5 text-blue-500" />
                        </span>
                      ) : null}
                      {isStale && (
                        <span title="Quantity out of date — source measurements have changed (Spec §11)">
                          <AlertTriangle className="inline h-3.5 w-3.5 text-amber-500" />
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">
                      {item.costCode || "—"}
                    </td>
                    <td className="px-4 py-3">
                      {item.description}
                      {isStale && (
                        <button
                          className="ml-2 inline-flex items-center gap-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-700 hover:bg-amber-200"
                          title="Recompute quantity from source measurements"
                        >
                          <RefreshCw className="h-3 w-3" />
                          Update
                        </button>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {item.quantity.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-gray-500">{item.unit}</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {formatCurrency(item.unitCostCents)}
                    </td>
                    <td className="px-4 py-3 text-right font-medium tabular-nums">
                      {formatCurrency(Math.round(item.quantity * item.unitCostCents))}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() =>
                          removeLineItem(projectId!, estimateId!, item.id)
                        }
                        className="text-gray-400 hover:text-red-500"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}

              {/* Add new item row */}
              <tr className="bg-gray-50">
                <td></td>
                <td className="px-4 py-3">
                  <select
                    value={newItem.costCode}
                    onChange={(e) =>
                      setNewItem({ ...newItem, costCode: e.target.value })
                    }
                    className="w-full rounded border border-gray-300 px-2 py-1 text-xs"
                  >
                    <option value="">Code...</option>
                    {CSI_DIVISIONS.map((div) => (
                      <option key={div.code} value={div.code}>
                        {div.code} - {div.title}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-4 py-3">
                  <input
                    type="text"
                    placeholder="Description"
                    value={newItem.description}
                    onChange={(e) =>
                      setNewItem({ ...newItem, description: e.target.value })
                    }
                    className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
                  />
                </td>
                <td className="px-4 py-3">
                  <input
                    type="number"
                    placeholder="Qty"
                    value={newItem.quantity}
                    onChange={(e) =>
                      setNewItem({ ...newItem, quantity: e.target.value })
                    }
                    className="w-full rounded border border-gray-300 px-2 py-1 text-right text-sm"
                  />
                </td>
                <td className="px-4 py-3">
                  <input
                    type="text"
                    placeholder="Unit"
                    value={newItem.unit}
                    onChange={(e) =>
                      setNewItem({ ...newItem, unit: e.target.value })
                    }
                    className="w-20 rounded border border-gray-300 px-2 py-1 text-sm"
                  />
                </td>
                <td className="px-4 py-3">
                  <input
                    type="number"
                    placeholder="$/unit"
                    value={newItem.unitCost}
                    onChange={(e) =>
                      setNewItem({ ...newItem, unitCost: e.target.value })
                    }
                    className="w-full rounded border border-gray-300 px-2 py-1 text-right text-sm"
                    step="0.01"
                  />
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={handleAddItem}
                    className="flex items-center gap-1 rounded bg-brand-600 px-3 py-1 text-xs font-medium text-white hover:bg-brand-700"
                  >
                    <Plus className="h-3 w-3" />
                    Add
                  </button>
                </td>
                <td></td>
              </tr>
            </tbody>
          </table>

          {/* Totals footer */}
          <div className="flex items-center justify-between border-t border-gray-200 bg-gray-50 px-4 py-3">
            <span className="text-sm font-semibold">Total</span>
            <span className="text-lg font-bold tabular-nums">
              {formatCurrency(totalCents)}
            </span>
          </div>
        </div>
      </div>
    </>
  );
}
