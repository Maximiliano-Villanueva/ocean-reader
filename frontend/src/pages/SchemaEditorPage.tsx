/**
 * Dedicated schema authoring route — new schema (wizard) or fork revision from an existing key.
 */

import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import SchemaRevisionEditor from "../components/schemas/SchemaRevisionEditor";
import { EMPTY_SCHEMA_TEMPLATE } from "../lib/schemaTemplates";
import { api } from "../api";

export default function SchemaEditorPage() {
  const { projectId = "", schemaKey: routeSchemaKey } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const fromVersionId = searchParams.get("from");

  const isCreate = routeSchemaKey === undefined || routeSchemaKey === "new";

  const [schemaKey, setSchemaKey] = useState(isCreate ? "" : routeSchemaKey ?? "");
  const [jsonText, setJsonText] = useState(isCreate ? EMPTY_SCHEMA_TEMPLATE : "// Loading definition…");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!isCreate);

  const schemasHref = `/projects/${projectId}/schemas`;

  const loadRevisionSource = useCallback(async () => {
    if (!projectId || isCreate) return;
    setLoading(true);
    setError(null);
    try {
      const groups = await api.validation.listSchemas(projectId);
      const group = groups.find((g) => g.schema_key === routeSchemaKey);
      if (!group || group.versions.length === 0) {
        setError(`Schema "${routeSchemaKey}" was not found.`);
        return;
      }
      const version =
        (fromVersionId ? group.versions.find((v) => v.id === fromVersionId) : null) ??
        group.versions.find((v) => v.status === "active") ??
        group.versions[0];
      if (!version) {
        setError("No revision available to fork.");
        return;
      }
      const detail = await api.validation.getSchemaVersion(projectId, version.id);
      setSchemaKey(routeSchemaKey ?? "");
      setJsonText(JSON.stringify(detail.body, null, 2));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [projectId, isCreate, routeSchemaKey, fromVersionId]);

  useEffect(() => {
    void loadRevisionSource();
  }, [loadRevisionSource]);

  function goBack() {
    navigate(schemasHref);
  }

  async function publish(e: FormEvent) {
    e.preventDefault();
    if (!projectId) return;
    const sk = schemaKey.trim();
    if (!sk) {
        setError("Checklist ID is required.");
      return;
    }
    let body: Record<string, unknown>;
    try {
      body = JSON.parse(jsonText) as Record<string, unknown>;
    } catch {
      setError("Invalid JSON — fix the editor before publishing.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.validation.createSchemaVersion(projectId, { schema_key: sk, body });
      navigate(schemasHref);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="page project-route-page schemas-page schemas-page--editing">
        <p className="muted" style={{ padding: "1.5rem" }}>
          Loading checklist…
        </p>
      </div>
    );
  }

  if (!isCreate && error && jsonText.startsWith("//")) {
    return (
      <div className="page project-route-page schemas-page schemas-page--editing">
        <p className="alert-error" role="alert">
          {error}
        </p>
        <button type="button" className="btn-secondary" onClick={goBack}>
          Back to checklists
        </button>
      </div>
    );
  }

  return (
    <div className="page project-route-page schemas-page schemas-page--editing">
      {error ? (
        <p className="alert-error" role="alert" style={{ marginBottom: "0.75rem" }}>
          {error}
        </p>
      ) : null}
      <div className="schemas-workspace">
        <SchemaRevisionEditor
          mode={isCreate ? "create" : "revision"}
          projectId={projectId}
          schemaKey={schemaKey}
          jsonText={jsonText}
          busy={busy}
          onSchemaKeyChange={setSchemaKey}
          onJsonTextChange={setJsonText}
          onPublish={publish}
          onCancel={goBack}
          onError={setError}
        />
      </div>
    </div>
  );
}
