/** Ocean Read — validation-first shell. UI lives under `pages/`. */
import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";

import LogsPage from "./pages/LogsPage";
import ProjectLayout from "./layouts/ProjectLayout";
import ProjectOverviewPage from "./pages/ProjectOverviewPage";
import ProjectSchemasPage from "./pages/ProjectSchemasPage";
import ProjectSchemaVersionsPage from "./pages/ProjectSchemaVersionsPage";
import ProjectValidationPage from "./pages/ProjectValidationPage";
import ProjectsPage from "./pages/ProjectsPage";
import ValidationHistoryPage from "./pages/ValidationHistoryPage";
import ValidationRunDetailPage from "./pages/ValidationRunDetailPage";
import ValidationPage from "./pages/ValidationPage";

import "./App.css";

export default function App() {
  return (
    <BrowserRouter>
      <div className="shell">
        <header className="header">
          <div className="header-inner">
            <Link to="/">Ocean Read</Link>
            <nav className="header-nav">
              <Link to="/projects">Projects</Link>
              <Link to="/logs">Logs</Link>
            </nav>
          </div>
        </header>
        <main className="main">
          <Routes>
            <Route path="/" element={<Navigate to="/projects" replace />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/projects/:projectId" element={<ProjectLayout />}>
              <Route index element={<ProjectOverviewPage />} />
              <Route path="validation" element={<ValidationHistoryPage />} />
              <Route path="validation/run" element={<ProjectValidationPage />} />
              <Route path="validation/runs/:runId" element={<ValidationRunDetailPage />} />
              <Route path="schemas" element={<ProjectSchemasPage />} />
              <Route path="schema-versions" element={<ProjectSchemaVersionsPage />} />
            </Route>
            <Route path="/projects/:projectId/validate/:docId" element={<ValidationPage />} />
            <Route path="/logs" element={<LogsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
