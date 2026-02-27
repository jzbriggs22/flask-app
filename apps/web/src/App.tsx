import { Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { ProjectsPage } from "./modules/projects/ProjectsPage";
import { ProjectDetailPage } from "./modules/projects/ProjectDetailPage";
import { TakeoffPage } from "./modules/takeoff/TakeoffPage";
import { EstimatePage } from "./modules/estimating/EstimatePage";
import { AdminPage } from "./modules/admin/AdminPage";

export function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        <Route
          path="/projects/:projectId/takeoff/:drawingSetId"
          element={<TakeoffPage />}
        />
        <Route
          path="/projects/:projectId/estimate/:estimateId"
          element={<EstimatePage />}
        />
        <Route path="/admin" element={<AdminPage />} />
      </Route>
    </Routes>
  );
}
