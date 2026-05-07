import { Navigate, useParams } from "react-router-dom";

/** Legacy `/projects/:projectId/validate/:docId` → validation hub (schema-driven pipeline). */
export default function ValidationPage() {
  const { projectId = "" } = useParams();
  return <Navigate to={`/projects/${projectId}/validation/run`} replace />;
}
