import { create } from "zustand";
import { v4 as uuid } from "uuid";

export interface LineItem {
  id: string;
  description: string;
  costCode: string;
  quantity: number;
  unit: string;
  /** Unit cost in cents — never use floating point for money */
  unitCostCents: number;
  createdAt: string;
}

export interface Estimate {
  id: string;
  name: string;
  lineItems: LineItem[];
  createdAt: string;
}

export interface DrawingSet {
  id: string;
  name: string;
  fileName: string;
  fileSize: number;
  sheetCount: number;
  createdAt: string;
}

export interface Project {
  id: string;
  name: string;
  number: string;
  status: "active" | "archived" | "bid";
  drawingSets: DrawingSet[];
  estimates: Estimate[];
  createdAt: string;
}

interface ProjectStore {
  projects: Project[];
  createProject: (data: { name: string; number: string }) => void;
  addDrawingSet: (
    projectId: string,
    data: { name: string; fileName: string; fileSize: number }
  ) => void;
  addEstimate: (projectId: string, data: { name: string }) => void;
  addLineItem: (
    projectId: string,
    estimateId: string,
    data: Omit<LineItem, "id" | "createdAt">
  ) => void;
  updateLineItem: (
    projectId: string,
    estimateId: string,
    itemId: string,
    data: Partial<Omit<LineItem, "id" | "createdAt">>
  ) => void;
  removeLineItem: (
    projectId: string,
    estimateId: string,
    itemId: string
  ) => void;
}

export const useProjectStore = create<ProjectStore>((set) => ({
  projects: [],

  createProject: (data) =>
    set((state) => ({
      projects: [
        ...state.projects,
        {
          id: uuid(),
          name: data.name,
          number: data.number,
          status: "active",
          drawingSets: [],
          estimates: [],
          createdAt: new Date().toISOString(),
        },
      ],
    })),

  addDrawingSet: (projectId, data) =>
    set((state) => ({
      projects: state.projects.map((p) =>
        p.id === projectId
          ? {
              ...p,
              drawingSets: [
                ...p.drawingSets,
                {
                  id: uuid(),
                  name: data.name,
                  fileName: data.fileName,
                  fileSize: data.fileSize,
                  sheetCount: 0,
                  createdAt: new Date().toISOString(),
                },
              ],
            }
          : p
      ),
    })),

  addEstimate: (projectId, data) =>
    set((state) => ({
      projects: state.projects.map((p) =>
        p.id === projectId
          ? {
              ...p,
              estimates: [
                ...p.estimates,
                {
                  id: uuid(),
                  name: data.name,
                  lineItems: [],
                  createdAt: new Date().toISOString(),
                },
              ],
            }
          : p
      ),
    })),

  addLineItem: (projectId, estimateId, data) =>
    set((state) => ({
      projects: state.projects.map((p) =>
        p.id === projectId
          ? {
              ...p,
              estimates: p.estimates.map((e) =>
                e.id === estimateId
                  ? {
                      ...e,
                      lineItems: [
                        ...e.lineItems,
                        {
                          ...data,
                          id: uuid(),
                          createdAt: new Date().toISOString(),
                        },
                      ],
                    }
                  : e
              ),
            }
          : p
      ),
    })),

  updateLineItem: (projectId, estimateId, itemId, data) =>
    set((state) => ({
      projects: state.projects.map((p) =>
        p.id === projectId
          ? {
              ...p,
              estimates: p.estimates.map((e) =>
                e.id === estimateId
                  ? {
                      ...e,
                      lineItems: e.lineItems.map((item) =>
                        item.id === itemId ? { ...item, ...data } : item
                      ),
                    }
                  : e
              ),
            }
          : p
      ),
    })),

  removeLineItem: (projectId, estimateId, itemId) =>
    set((state) => ({
      projects: state.projects.map((p) =>
        p.id === projectId
          ? {
              ...p,
              estimates: p.estimates.map((e) =>
                e.id === estimateId
                  ? {
                      ...e,
                      lineItems: e.lineItems.filter(
                        (item) => item.id !== itemId
                      ),
                    }
                  : e
              ),
            }
          : p
      ),
    })),
}));
