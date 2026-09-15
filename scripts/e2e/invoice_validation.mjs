/**
 * Browser E2E: upload inv_cursor_formatted.pdf via UI and assert PASS + key fields.
 *
 * Usage (from repo root, stack running on :8080):
 *   cd scripts/e2e && npm install && npx playwright install chromium
 *   node invoice_validation.mjs
 */
import { chromium } from "playwright";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");
const BASE = process.env.GATEWAY_HTTP_PORT
  ? `http://127.0.0.1:${process.env.GATEWAY_HTTP_PORT}`
  : "http://127.0.0.1:8080";
const PDF = join(ROOT, "backend/tests/fixtures/invoice/inv_cursor_formatted.pdf");
const SCHEMA_KEY = "inv_cursor_agent";
const SCHEMA_VERSION = "1.0";

async function ensureSchema(projectId) {
  const schemaBody = JSON.parse(
    readFileSync(
      join(ROOT, "backend/tests/fixtures/invoice/schema_inv_cursor_agent_prompt.json"),
      "utf8",
    ),
  );
  const res = await fetch(`${BASE}/api/projects/${projectId}/validation-schemas`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      schema_key: SCHEMA_KEY,
      version_label: SCHEMA_VERSION,
      body: schemaBody,
    }),
  });
  if (!res.ok && res.status !== 409) {
    const text = await res.text();
    throw new Error(`schema create failed ${res.status}: ${text}`);
  }
}

async function main() {
  const health = await fetch(`${BASE}/api/health`);
  if (!health.ok) throw new Error(`API unhealthy: ${health.status}`);

  const projects = await (await fetch(`${BASE}/api/projects`)).json();
  const project = projects.find((p) => p.name === "Default workspace") ?? projects[0];
  if (!project?.id) throw new Error("No project found");
  const projectId = project.id;
  console.log(`project_id=${projectId}`);

  await ensureSchema(projectId);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(120_000);

  try {
    await page.goto(`${BASE}/projects`);
    await page.getByRole("link", { name: /Default workspace/i }).click();

    await page.goto(`${BASE}/projects/${projectId}/validation/run`);
    await page.getByRole("heading", { name: "Run validation" }).waitFor();

    await page.locator("select").nth(0).selectOption(SCHEMA_KEY);
    await page.locator("select").nth(1).selectOption(SCHEMA_VERSION);

    const fileInput = page.locator('input[type="file"][accept*="pdf"]');
    await fileInput.setInputFiles(PDF);
    await page.getByText("inv_cursor_formatted.pdf").waitFor();

    const [validateResponse] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/api/validate-document") && r.status() === 200,
        { timeout: 180_000 },
      ),
      page.getByRole("button", { name: /^Run validation/ }).click(),
    ]);
    await page.locator(".validation-status-pass").waitFor({ timeout: 180_000 });
    const statusText = await page.locator(".validation-status").innerText();
    console.log(`UI status=${statusText}`);
    if (statusText !== "PASS") {
      throw new Error(`Expected PASS in UI, got ${statusText}`);
    }

    const runPayload = await validateResponse.json();
    const runId = runPayload.run_id;
    console.log(`run_id=${runId} parser=${runPayload.extraction_meta?.parser}`);

    await page.goto(`${BASE}/projects/${projectId}/validation/runs/${runId}`);
    await page.getByText("DOEA864B-0011").waitFor({ timeout: 60_000 });
    await page.getByText("mvillanueva.tolcachier@gmail.com").waitFor();
    console.log("Run detail field table OK");

    const pdfPane = page.locator(".pdf-evidence-viewer, .validation-pdf-pane, canvas").first();
    await pdfPane.waitFor({ timeout: 30_000 });
    console.log("PDF evidence viewer OK");

    console.log("UI_INVOICE_VALIDATION_OK");
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
