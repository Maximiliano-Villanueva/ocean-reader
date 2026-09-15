/**
 * David Park (AP) — sales demo: prompt-driven schema, versions, batch, PDF highlights, audit report.
 */
import { chromium } from "playwright";
import { readFileSync, existsSync, mkdirSync, renameSync, copyFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  DEMO_VIEWPORT,
  pause,
  snap,
  waitApiHealthy,
  cyclePdfHighlights,
  writeFeedback,
  openRunByOutcome,
} from "./lib/demoHelpers.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");
const BASE = process.env.GATEWAY_HTTP_PORT
  ? `http://127.0.0.1:${process.env.GATEWAY_HTTP_PORT}`
  : "http://127.0.0.1:8080";

const PROJECT_NAME = "Nordic Supplies — David Park";
const SCHEMA_KEY = "supplier_invoice";
const CAPTURE = join(ROOT, "docs/personas/captures/david");
const VIDEO_DIR = join(CAPTURE, "video");
const FEEDBACK = join(ROOT, "docs/personas/feedback/DAVID_SESSION_FEEDBACK.md");

const INVOICE_DIR = join(ROOT, "scripts/fixtures/personas/david_ap");
const PDFS = {
  us: join(INVOICE_DIR, "inv_us_acme.pdf"),
  uk: join(INVOICE_DIR, "inv_uk_vat.pdf"),
  minimal: join(INVOICE_DIR, "inv_minimal_saas.pdf"),
  es: join(INVOICE_DIR, "inv_es_formatted.pdf"),
  fail: join(INVOICE_DIR, "inv_us_fail_tax.pdf"),
  ambiguous: join(INVOICE_DIR, "inv_us_ambiguous_total.pdf"),
};

const AGENT_PROMPT = `Create a supplier invoice checklist for our AP team. We receive PDFs in many layouts (US, UK, Spain, minimal SaaS).

Strict fields (use llm_fallback where layout varies):
- invoice_number — use LLM only, no regex_hint
- issue_date and due_date as dates
- subtotal_before_tax, tax_amount, total_due as numbers (total_due required)

Open-ended informative only:
- vendor_name — who issued the invoice
- bill_to_name — our company being billed
- line_items_summary — products/services and quantities as one text field

Cross-field rule: total_due must equal subtotal_before_tax + tax_amount within 0.02

Enable document understanding for contextual extraction.`;

async function waitDsl(page) {
  await page.locator(".schema-dsl-badge--ok", { hasText: "Valid" }).waitFor({ timeout: 120_000 });
}

async function agentChat(page, assistantPane, prompt, attempt = 1) {
  const compose = assistantPane.locator(".schema-agent-compose textarea");
  await compose.fill(prompt);
  const before = await assistantPane.locator(".schema-agent-msg--assistant").count();
  try {
    await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/schema-agent/chat") && r.request().method() === "POST",
        { timeout: 600_000 },
      ),
      assistantPane.getByRole("button", { name: "Send" }).click(),
    ]);
  } catch (err) {
    if (attempt < 3) {
      console.warn(`Agent chat timeout, retry ${attempt + 1}/3`);
      return agentChat(page, assistantPane, prompt, attempt + 1);
    }
    throw err;
  }
  await page.locator(".schema-agent-msg--assistant").nth(before).waitFor({ timeout: 600_000 });
  await pause(2000);
}

async function ensureProject(request) {
  const list = await request.get(`${BASE}/api/projects`).then((r) => r.json());
  let p = list.find((x) => x.name === PROJECT_NAME);
  if (!p) {
    p = await request.post(`${BASE}/api/projects`, { data: { name: PROJECT_NAME } }).then((r) => r.json());
  }
  return p.id;
}

async function schemaExists(request, projectId) {
  const groups = await request
    .get(`${BASE}/api/projects/${projectId}/validation-schemas`)
    .then((r) => r.json());
  return groups.some((g) => g.schema_key === SCHEMA_KEY);
}

async function schemaVersionCount(request, projectId) {
  const groups = await request
    .get(`${BASE}/api/projects/${projectId}/validation-schemas`)
    .then((r) => r.json());
  const g = groups.find((x) => x.schema_key === SCHEMA_KEY);
  return g?.versions?.length ?? 0;
}

async function activeSchemaVersion(request, projectId) {
  const groups = await request
    .get(`${BASE}/api/projects/${projectId}/validation-schemas`)
    .then((r) => r.json());
  const g = groups.find((x) => x.schema_key === SCHEMA_KEY);
  const active = g?.versions?.find((v) => v.status === "active");
  return active?.version_label ?? "1.0";
}

async function validatePdfApi(request, projectId, pdfPath, label) {
  const version = await activeSchemaVersion(request, projectId);
  const buf = readFileSync(pdfPath);
  const name = pdfPath.split("/").pop() ?? "doc.pdf";
  const res = await request.post(`${BASE}/api/validate-document`, {
    multipart: {
      project_id: projectId,
      schema_id: SCHEMA_KEY,
      schema_version: version,
      document: { name, mimeType: "application/pdf", buffer: buf },
    },
    timeout: 600_000,
  });
  if (!res.ok()) {
    const text = await res.text();
    throw new Error(`API validate ${label} failed ${res.status()}: ${text.slice(0, 200)}`);
  }
  const body = await res.json();
  console.log(`API validate ${label}: ${body.status}`);
  return body;
}

async function preseedBackgroundRuns(request, projectId, { light = false } = {}) {
  const jobs = light
    ? [["ambiguous", PDFS.ambiguous]]
    : [
        ["uk", PDFS.uk],
        ["minimal", PDFS.minimal],
        ["es", PDFS.es],
        ["ambiguous", PDFS.ambiguous],
      ];
  for (const [label, path] of jobs) {
    await validatePdfApi(request, projectId, path, label);
  }
}

async function waitBatchComplete(page, expectedCount, timeoutMs = 420_000) {
  await page.waitForFunction(
    (n) => {
      const items = document.querySelectorAll(".validation-run-status-item");
      if (items.length < n) return false;
      return [...items].every((el) => el.querySelector(".validation-file-queue-badge"));
    },
    expectedCount,
    { timeout: timeoutMs },
  );
}

async function main() {
  mkdirSync(CAPTURE, { recursive: true });
  mkdirSync(VIDEO_DIR, { recursive: true });

  for (const p of Object.values(PDFS)) {
    if (!existsSync(p)) {
      throw new Error(`Missing ${p} — run: cd backend && uv run python ../scripts/fixtures/personas/generate_david_invoices.py`);
    }
  }
  await waitApiHealthy(BASE);

  const browser = await chromium.launch({ headless: true, slowMo: 90 });
  const context = await browser.newContext({
    viewport: DEMO_VIEWPORT,
    recordVideo: { dir: VIDEO_DIR, size: DEMO_VIEWPORT },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(180_000);
  const request = context.request;
  const projectId = await ensureProject(request);
  const hasSchema = await schemaExists(request, projectId);

  try {
    // 1 — Workspace
    await page.goto(`${BASE}/projects`, { waitUntil: "networkidle" });
    await snap(page, CAPTURE, "01-workspaces");
    const existing = await page.getByRole("link", { name: PROJECT_NAME }).count();
    if (!existing) {
      await page.getByPlaceholder("Workspace name").fill(PROJECT_NAME);
      await page.getByRole("button", { name: "Create workspace" }).click();
      await page.waitForURL(/\/projects\//);
    } else {
      await page.getByRole("link", { name: PROJECT_NAME }).click();
    }
    await pause();
    await snap(page, CAPTURE, "02-dashboard");

    // 2 — Schema via agent (first run only)
    await page.getByLabel("Project sections").getByRole("link", { name: "Checklists" }).click();
    await pause();
    const hasSchemaUi = (await page.locator("code").filter({ hasText: SCHEMA_KEY }).count()) > 0;
    if (!hasSchema && !hasSchemaUi) {
      await page.getByRole("link", { name: "New checklist" }).click();
      await page.getByRole("button", { name: "Skip wizard → workspace" }).click();
      await page.getByRole("heading", { name: "Schema assistant" }).waitFor();
      await snap(page, CAPTURE, "03-schema-assistant");
      const assistant = page.locator(".schema-studio-assistant-pane");
      await agentChat(page, assistant, AGENT_PROMPT);
      await snap(page, CAPTURE, "04-schema-agent-reply");
      await page.locator(".schema-command-bar-key input").fill(SCHEMA_KEY);
      await waitDsl(page);
      const rail = page.locator(".schema-studio-rail-pane");
      await rail.getByRole("button", { name: "Choose PDF" }).click();
      await rail.locator('input[type="file"]').setInputFiles(PDFS.us);
      await pause(1000);
      await snap(page, CAPTURE, "05-dry-run-setup");
      await Promise.all([
        page.waitForResponse((r) => r.url().includes("/validation-schemas/preview"), { timeout: 300_000 }),
        rail.getByRole("button", { name: "Run validation" }).click(),
      ]);
      await pause(2000);
      await snap(page, CAPTURE, "06-dry-run-result");
      await page.getByRole("button", { name: "Create schema" }).click();
      await page.waitForURL(/\/schemas$/);
      await snap(page, CAPTURE, "07-checklist-published");
    } else {
      await snap(page, CAPTURE, "07-checklist-existing");
    }

    // Pre-seed varied layouts via API (keeps UI batch short for video)
    if (await schemaExists(request, projectId)) {
      const light = process.env.DAVID_LIGHT_PRESEED === "1";
      console.log(light ? "Light pre-seed (ambiguous only)…" : "Pre-seeding UK / minimal / ES / ambiguous runs via API…");
      await preseedBackgroundRuns(request, projectId, { light });
    }

    // 3 — Batch validate (UI: US pass + intentional FAIL)
    await page.getByLabel("Project sections").getByRole("link", { name: "Validate" }).click();
    await page.locator(".validation-form-grid select").first().selectOption(SCHEMA_KEY);
    await page.locator(".validation-form-grid select").nth(1).selectOption({ index: 1 });
    await page.locator(".validation-dropzone-input").setInputFiles([PDFS.us, PDFS.fail]);
    await snap(page, CAPTURE, "08-batch-queued");
    await page.getByRole("button", { name: /Run validation/ }).click();
    await waitBatchComplete(page, 2);
    await snap(page, CAPTURE, "09-batch-complete");

    // 4 — History + outcome guide
    await page.getByLabel("Project sections").getByRole("link", { name: "History" }).click();
    await page.locator(".outcome-guide").scrollIntoViewIfNeeded();
    await pause(1000);
    await snap(page, CAPTURE, "09b-outcome-guide");

    // 5 — PASS run + PDF highlights
    await openRunByOutcome(page, "PASS");
    await snap(page, CAPTURE, "10-run-detail-pass");
    await cyclePdfHighlights(page, CAPTURE, "10");

    // 6 — FAIL run
    await page.getByLabel("Project sections").getByRole("link", { name: "History" }).click();
    await pause(1500);
    await openRunByOutcome(page, "FAIL");
    await snap(page, CAPTURE, "11-run-detail-fail");
    await cyclePdfHighlights(page, CAPTURE, "11");

    // 7 — AMBIGUOUS run
    await page.getByLabel("Project sections").getByRole("link", { name: "History" }).click();
    await pause(1500);
    await openRunByOutcome(page, "AMBIGUOUS");
    await snap(page, CAPTURE, "11b-run-detail-ambiguous");
    await cyclePdfHighlights(page, CAPTURE, "11b");

    // 8 — Audit report
    await page.getByLabel("Project sections").getByRole("link", { name: "History" }).click();
    await page.locator(".audit-report-panel").scrollIntoViewIfNeeded();
    await pause(1000);
    await snap(page, CAPTURE, "12-audit-report");
    await page.getByRole("button", { name: "Download .md" }).click();
    await pause(500);

    // 9 — Version v2.0 (stricter tax rule)
    const versionCount = await schemaVersionCount(request, projectId);
    if (versionCount < 2) {
      await page.getByLabel("Project sections").getByRole("link", { name: "Checklists" }).click();
      await page
        .locator(".schema-group-block")
        .filter({ hasText: SCHEMA_KEY })
        .getByRole("link", { name: "Edit schema" })
        .click();
      await page.waitForURL(/\/edit/);
      const assistant2 = page.locator(".schema-studio-assistant-pane");
      await agentChat(
        page,
        assistant2,
        "Publish v2: make tax_amount required and strengthen the cross-field rule so total_due must equal subtotal_before_tax + tax_amount within 0.01",
      );
      await waitDsl(page);
      await page.getByRole("button", { name: "Publish revision" }).click();
      await page.waitForURL(/\/schemas$/);
      await snap(page, CAPTURE, "14-checklist-v2");
    } else {
      await page.getByLabel("Project sections").getByRole("link", { name: "Checklists" }).click();
      await snap(page, CAPTURE, "14-checklist-v2-existing");
    }

    await snap(page, CAPTURE, "15-final");
    writeFeedback(FEEDBACK, [
      "# David Park — demo session",
      "",
      `**Date:** ${new Date().toISOString()}`,
      `**Project:** ${PROJECT_NAME}`,
      `**Checklist:** ${SCHEMA_KEY} (prompt-driven via schema agent)`,
      "",
      "## Showcased",
      "- Workspace organization",
      "- AI assistant → checklist (no JSON)",
      "- Dry-run on US invoice PDF",
      "- Batch validation + pre-seeded varied layouts",
      "- PASS / FAIL / AMBIGUOUS outcome guide",
      "- PDF field highlights (tight bbox)",
      "- Audit report export",
      "- Checklist v2 revision via assistant",
      "",
      "## Video",
      "`docs/personas/captures/david/david-journey.webm`",
    ]);
  } finally {
    await context.close();
    await browser.close();
    const vids = readdirSync(VIDEO_DIR).filter((f) => f.endsWith(".webm"));
    if (vids[0]) {
      const dest = join(CAPTURE, "david-journey.webm");
      try {
        renameSync(join(VIDEO_DIR, vids[0]), dest);
      } catch {
        copyFileSync(join(VIDEO_DIR, vids[0]), dest);
      }
    }
    console.log("David demo complete:", CAPTURE);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
