/** API base — empty string uses same origin (Traefik in Docker, Vite proxy locally). */
export const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "";

const EDGE_TOKEN = (import.meta.env.VITE_EDGE_API_TOKEN as string | undefined)?.trim() ?? "";

const LOG_VIEWER_TOKEN = (import.meta.env.VITE_LOG_VIEWER_TOKEN as string | undefined)?.trim() ?? "";

function withEdgeHeaders(headersInit?: HeadersInit): Headers {
  const h = new Headers(headersInit ?? undefined);
  if (EDGE_TOKEN && !h.has("Authorization")) {
    h.set("Authorization", `Bearer ${EDGE_TOKEN}`);
  }
  if (LOG_VIEWER_TOKEN && !h.has("X-Log-Viewer-Token")) {
    h.set("X-Log-Viewer-Token", LOG_VIEWER_TOKEN);
  }
  return h;
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const body = init?.body;
  const headers = withEdgeHeaders(init?.headers ?? undefined);
  if (body !== undefined && body !== null && typeof body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const resp = await fetch(url, { ...init, headers });
  if (!resp.ok) {
    const t = await resp.text();
    throw new Error(`${resp.status} ${t}`);
  }
  return resp.json() as Promise<T>;
}

export type Project = {
  id: string;
  name: string;
  settings: Record<string, unknown>;
  organization_id: string;
};

export type ValidationSchemaVersionSummary = {
  id: string;
  version_label: string;
  status: string;
  archived_at?: string | null;
  created_at?: string | null;
};

export type ValidationSchemaGroupOut = {
  schema_key: string;
  versions: ValidationSchemaVersionSummary[];
};

/** POST omit ``version_label`` → server assigns next revision (e.g. 1.0 → 1.1). Omit ``body`` → wine-quality default. */
export type ValidationSchemaVersionCreateInput = {
  schema_key: string;
  version_label?: string | null;
  body?: Record<string, unknown> | null;
  archive_previous_active?: boolean;
};

/** Response from POST suggest-cross-field-rule (M3 LLM assist). */
export type SuggestCrossFieldRuleOut = {
  id: string;
  expression: string;
  error_message: string;
};

export type ValidationSchemaVersionDetailOut = {
  id: string;
  schema_key: string;
  version_label: string;
  status: string;
  body: Record<string, unknown>;
  created_at?: string | null;
};

export type ValidationEvidenceOut = {
  text: string;
  block_id: string;
  page: number;
  bbox?: number[] | null;
  section_label?: string | null;
  /** Cross-field rules: highlight each involved field on the PDF. */
  by_field?: Record<string, ValidationEvidenceOut> | null;
};

export type ValidationFieldErrorOut = {
  field: string;
  value: unknown;
  expected: unknown;
  rule: string;
  evidence: ValidationEvidenceOut | null;
};

export type AmbiguousFieldOut = {
  field: string;
  candidate_count: number;
};

/** One global rule executed against one schema field (includes passes). */
export type FieldRuleOutcomeOut = {
  field: string;
  rule: string;
  passed: boolean;
  value?: unknown;
  expected?: unknown;
  evidence: ValidationEvidenceOut | null;
};

export type OpenEndedEvidenceOut = {
  text: string;
  block_id: string;
  page: number;
  bbox: number[] | null;
};

export type OpenEndedFieldResultOut = {
  field: string;
  extracted_value: string | null;
  evaluation: "pass" | "fail" | "ambiguous" | null;
  informative_only: boolean;
  evidence: OpenEndedEvidenceOut[];
};

export type ValidateDocumentResponse = {
  status: "PASS" | "FAIL" | "AMBIGUOUS";
  schema_id: string;
  schema_version: string;
  results: ValidationFieldErrorOut[];
  ambiguous_fields: AmbiguousFieldOut[];
  open_ended_results?: OpenEndedFieldResultOut[];
  /** Full schema JSON applied for this run (may be absent on older persisted runs). */
  schema_snapshot?: Record<string, unknown> | null;
  /** Resolved extraction values per field (PASS/FAIL; absent when ambiguous or legacy). */
  resolved_values?: Record<string, unknown> | null;
  field_rule_outcomes?: FieldRuleOutcomeOut[];
  run_id?: string | null;
  /** e.g. { vision_fallback_used: true } when scanned pages were read via multimodal LLM */
  extraction_meta?: Record<string, unknown> | null;
};

export type ValidationRunSummary = {
  id: string;
  schema_key: string;
  version_label: string;
  document_filename: string;
  outcome: string;
  created_at?: string | null;
  /** Set when the run was archived (hidden from default history). */
  archived_at?: string | null;
  /** Set when the run was soft-deleted from default history. */
  deleted_at?: string | null;
  attributes?: Record<string, string | null>;
};

export type CohortAttributeFilter = { key: string; value: string | null };

export type CohortFilters = {
  schema_key?: string | null;
  version_label?: string | null;
  outcomes: string[];
  attributes: CohortAttributeFilter[];
};

export type ValidationCohortOut = {
  id: string;
  name: string;
  description?: string | null;
  filters: CohortFilters;
  pass_threshold_pct: number;
  created_at?: string | null;
  updated_at?: string | null;
};

export type CohortEvaluationOut = {
  total: number;
  pass_count: number;
  fail_count: number;
  ambiguous_count: number;
  pass_rate_pct: number;
  pass_threshold_pct: number;
  meets_threshold: boolean;
  items: ValidationRunSummary[];
};

export type ValidationAttributeVocabularyOut = {
  keys: string[];
  values_by_key: Record<string, string[]>;
};

export type ValidationCohortCreateInput = {
  name: string;
  description?: string | null;
  filters: CohortFilters;
  pass_threshold_pct: number;
};

export type ValidationRunsPageResponse = {
  items: ValidationRunSummary[];
  total: number;
  page: number;
  page_size: number;
};

export type ValidationRunDetailOut = {
  id: string;
  schema_key: string;
  version_label: string;
  document_filename: string;
  outcome: string;
  created_at: string | null;
  report: ValidateDocumentResponse;
  has_pdf: boolean;
  /** SHA-256 fingerprint of uploaded PDF (empty on legacy rows). */
  pdf_hash?: string;
  archived_at?: string | null;
  deleted_at?: string | null;
  parent_run_id?: string | null;
  revision_number?: number;
  attributes?: Record<string, string | null>;
};

export type ValidationRunCorrectionCreate = {
  corrections: Record<string, unknown>;
  note?: string | null;
};

export type LogContainer = {
  id: string;
  name: string;
  service: string;
  status: string;
  state: string;
};

export const api = {
  health: () => jsonFetch<{ ok: boolean }>("/api/health"),

  validation: {
    listSchemas: (projectId: string) =>
      jsonFetch<ValidationSchemaGroupOut[]>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-schemas`,
      ),

    createSchemaVersion: (projectId: string, payload: ValidationSchemaVersionCreateInput) =>
      jsonFetch<ValidationSchemaVersionSummary>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-schemas`,
        { method: "POST", body: JSON.stringify(payload) },
      ),

    getSchemaVersion: (projectId: string, schemaRowId: string) =>
      jsonFetch<ValidationSchemaVersionDetailOut>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-schemas/${encodeURIComponent(schemaRowId)}`,
      ),

    suggestCrossFieldRule: (
      projectId: string,
      body: { natural_language: string; allowed_field_names: string[] },
    ) =>
      jsonFetch<SuggestCrossFieldRuleOut>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-schemas/suggest-cross-field-rule`,
        { method: "POST", body: JSON.stringify(body) },
      ),

    validateSchemaBody: (projectId: string, body: Record<string, unknown>) =>
      jsonFetch<{ ok: boolean; errors: string[]; normalized_body: Record<string, unknown> }>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-schemas/validate-body`,
        { method: "POST", body: JSON.stringify({ body }) },
      ),

    schemaJudgeAnalyze: (
      projectId: string,
      body: {
        schema_body: Record<string, unknown>;
        dsl_errors?: string[];
        validation?: ValidateDocumentResponse | null;
      },
    ) =>
      jsonFetch<{ summary: string; recommendations: string[]; priority: string }>(
        `/api/projects/${encodeURIComponent(projectId)}/schema-judge/analyze`,
        { method: "POST", body: JSON.stringify(body) },
      ),

    previewSchema: async (projectId: string, schemaJsonText: string, file: File) => {
      const fd = new FormData();
      fd.append("schema_body", schemaJsonText);
      fd.append("document", file);
      const resp = await fetch(
        `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/validation-schemas/preview`,
        { method: "POST", headers: withEdgeHeaders(), body: fd },
      );
      if (!resp.ok) throw new Error(await resp.text());
      return resp.json() as Promise<{
        dsl_ok: boolean;
        dsl_errors: string[];
        validation: ValidateDocumentResponse | null;
      }>;
    },

    schemaAgentChat: (
      projectId: string,
      body: {
        messages: { role: string; content: string }[];
        schema_body: Record<string, unknown>;
        sample_pdf_note?: string | null;
        validation_feedback?: {
          dsl_ok: boolean;
          dsl_errors: string[];
          preview_status?: string | null;
          preview_summary?: string | null;
          judge_summary?: string | null;
          judge_recommendations?: string[];
        };
      },
    ) =>
      jsonFetch<{ reply: string; schema_body: Record<string, unknown> }>(
        `/api/projects/${encodeURIComponent(projectId)}/schema-agent/chat`,
        { method: "POST", body: JSON.stringify(body) },
      ),

    schemaAgentSamplePdf: async (projectId: string, file: File) => {
      const fd = new FormData();
      fd.append("document", file);
      const resp = await fetch(
        `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/schema-agent/sample-pdf-text`,
        { method: "POST", headers: withEdgeHeaders(), body: fd },
      );
      if (!resp.ok) throw new Error(await resp.text());
      return resp.json() as Promise<{ text_preview: string; page_count: number; block_count: number }>;
    },

    validateDocument: async (
      projectId: string,
      schemaId: string,
      schemaVersion: string,
      file: File,
      attributes?: Record<string, string | null>,
    ): Promise<ValidateDocumentResponse> => {
      const fd = new FormData();
      fd.append("project_id", projectId);
      fd.append("schema_id", schemaId);
      fd.append("schema_version", schemaVersion);
      fd.append("document", file);
      if (attributes && Object.keys(attributes).length > 0) {
        fd.append("attributes", JSON.stringify(attributes));
      }
      const resp = await fetch(`${API_BASE}/api/validate-document`, {
        method: "POST",
        headers: withEdgeHeaders(),
        body: fd,
      });
      if (!resp.ok) throw new Error(await resp.text());
      return resp.json() as Promise<ValidateDocumentResponse>;
    },

    listRuns: (
      projectId: string,
      page = 1,
      pageSize = 25,
      filters?: {
        schemaKey?: string;
        versionLabel?: string;
        documentContains?: string;
        status?: string;
        includeHidden?: boolean;
      },
    ) => {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });
      if (filters?.schemaKey) params.set("schema_key", filters.schemaKey);
      if (filters?.versionLabel) params.set("version_label", filters.versionLabel);
      if (filters?.documentContains) params.set("document_contains", filters.documentContains);
      if (filters?.status) params.set("status", filters.status);
      if (filters?.includeHidden) params.set("include_hidden", "true");
      return jsonFetch<ValidationRunsPageResponse>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-runs?${params.toString()}`,
      );
    },

    getRun: (projectId: string, runId: string) =>
      jsonFetch<ValidationRunDetailOut>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-runs/${encodeURIComponent(runId)}`,
      ),

    createRunRevision: (projectId: string, runId: string, body: ValidationRunCorrectionCreate) =>
      jsonFetch<ValidationRunDetailOut>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-runs/${encodeURIComponent(runId)}/revisions`,
        { method: "POST", body: JSON.stringify(body) },
      ),

    /** Archive a run (hidden from default list; recover with restore or include_hidden list). */
    patchRunLifecycle: (
      projectId: string,
      runId: string,
      body: { archived?: boolean; restore?: boolean },
    ) =>
      jsonFetch<{ id: string; archived_at?: string | null; deleted_at?: string | null }>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-runs/${encodeURIComponent(runId)}`,
        { method: "PATCH", body: JSON.stringify(body) },
      ),

    /** Soft-delete from default history (row kept for audit; use restore to show again). */
    softDeleteRun: (projectId: string, runId: string) =>
      jsonFetch<{ status: string }>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-runs/${encodeURIComponent(runId)}`,
        { method: "DELETE" },
      ),

    deleteSchemaVersion: (projectId: string, schemaRowId: string) =>
      jsonFetch<{ status: string }>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-schemas/${encodeURIComponent(schemaRowId)}`,
        { method: "DELETE" },
      ),

    fetchRunBlocks: (projectId: string, runId: string) =>
      jsonFetch<
        Array<{
          id: string;
          page: number;
          bbox?: number[] | null;
          text?: string;
        }>
      >(`/api/projects/${encodeURIComponent(projectId)}/validation-runs/${encodeURIComponent(runId)}/blocks`),

    fetchRunCandidates: (projectId: string, runId: string) =>
      jsonFetch<
        Array<{
          field: string;
          value?: unknown;
          source?: string;
          confidence?: number;
          block_id?: string;
          page?: number;
          bbox?: number[] | null;
        }>
      >(`/api/projects/${encodeURIComponent(projectId)}/validation-runs/${encodeURIComponent(runId)}/candidates`),

    /** Blob URL for PDF preview — caller must ``URL.revokeObjectURL`` when unmounting. */
    fetchRunPdfObjectUrl: async (projectId: string, runId: string): Promise<string | null> => {
      const url = `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/validation-runs/${encodeURIComponent(runId)}/document`;
      const resp = await fetch(url, { headers: withEdgeHeaders() });
      if (!resp.ok) return null;
      const blob = await resp.blob();
      return URL.createObjectURL(blob);
    },

    /** Stored PDF as ``File`` for re-validation (new run). */
    fetchRunPdfAsFile: async (
      projectId: string,
      runId: string,
      filename: string,
    ): Promise<File | null> => {
      const url = `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/validation-runs/${encodeURIComponent(runId)}/document`;
      const resp = await fetch(url, { headers: withEdgeHeaders() });
      if (!resp.ok) return null;
      const blob = await resp.blob();
      const name = filename.trim() || "document.pdf";
      return new File([blob], name, { type: blob.type || "application/pdf" });
    },

    attributeVocabulary: (projectId: string) =>
      jsonFetch<ValidationAttributeVocabularyOut>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-attributes`,
      ),

    listCohorts: (projectId: string) =>
      jsonFetch<ValidationCohortOut[]>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-cohorts`,
      ),

    createCohort: (projectId: string, body: ValidationCohortCreateInput) =>
      jsonFetch<ValidationCohortOut>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-cohorts`,
        { method: "POST", body: JSON.stringify(body) },
      ),

    deleteCohort: (projectId: string, cohortId: string) =>
      jsonFetch<{ status: string }>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-cohorts/${encodeURIComponent(cohortId)}`,
        { method: "DELETE" },
      ),

    evaluateCohort: (projectId: string, body: ValidationCohortCreateInput) =>
      jsonFetch<CohortEvaluationOut>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-cohorts/evaluate`,
        { method: "POST", body: JSON.stringify(body) },
      ),

    evaluateSavedCohort: (projectId: string, cohortId: string) =>
      jsonFetch<CohortEvaluationOut>(
        `/api/projects/${encodeURIComponent(projectId)}/validation-cohorts/${encodeURIComponent(cohortId)}/evaluate`,
      ),
  },

  logs: {
    listContainers: () => jsonFetch<LogContainer[]>("/api/logs/containers"),
    tail: (containerId: string, tail = 400) =>
      jsonFetch<{ container_id: string; tail: number; text: string }>(
        `/api/logs/containers/${encodeURIComponent(containerId)}/tail?tail=${tail}`,
      ),
  },

  projects: {
    list: () => jsonFetch<Project[]>("/api/projects"),
    create: (name: string) =>
      jsonFetch<Project>("/api/projects", { method: "POST", body: JSON.stringify({ name }) }),
    delete: (id: string) =>
      jsonFetch<{ status: string }>(`/api/projects/${id}`, { method: "DELETE" }),
  },
};
