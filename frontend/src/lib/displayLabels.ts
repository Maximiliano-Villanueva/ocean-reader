/**
 * Persona-friendly labels for technical keys (schema_key, etc.).
 */

const ACRONYMS = new Set(["coa", "ap", "qc", "qa", "erp", "pdf", "po", "id"]);

/** Turn `supplier_coa` into `Supplier COA` for UI copy. */
export function formatSchemaKey(key: string): string {
  return key
    .split(/[_-]+/)
    .filter(Boolean)
    .map((word) => {
      const lower = word.toLowerCase();
      if (ACRONYMS.has(lower)) return lower.toUpperCase();
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(" ");
}

/** Human label for a single extracted field key (e.g. `ph` → `pH`). */
export function formatFieldLabel(field: string): string {
  const lower = field.toLowerCase();
  if (lower === "ph") return "pH";
  if (ACRONYMS.has(lower)) return lower.toUpperCase();
  return field
    .split(/[_-]+/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}
