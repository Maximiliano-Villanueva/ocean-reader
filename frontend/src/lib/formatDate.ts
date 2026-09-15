/**
 * Human-friendly timestamps for validation runs and audit tables.
 */

/** Format an ISO timestamp for display in tables and run headers. */
export function formatRunTimestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso.replace("T", " ").replace(/\.\d+Z?$/, "").replace("Z", " UTC");
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
