/** Status badge for a schema revision row. */

export default function SchemaStatusPill({ status }: { status: string }) {
  const s = status.toLowerCase();
  const cls =
    s === "active" ? "pill pill-pass" : s === "archived" ? "pill pill-muted" : "pill pill-muted";
  return <span className={cls}>{status}</span>;
}
