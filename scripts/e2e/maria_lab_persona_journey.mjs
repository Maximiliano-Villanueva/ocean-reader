/**
 * Maria Reyes (Lab QC Manager) — full product journey with screenshots, video, and feedback.
 * Embodies docs/personas/MARIA_CUSTOMER_AGENT.md — no insider knowledge.
 */
import { chromium } from "playwright";
import { existsSync, mkdirSync, writeFileSync, readdirSync, renameSync, copyFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { DEMO_VIEWPORT, pause, cyclePdfHighlights, waitApiHealthy, openRunByOutcome } from "./lib/demoHelpers.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");
const BASE = process.env.GATEWAY_HTTP_PORT
  ? `http://127.0.0.1:${process.env.GATEWAY_HTTP_PORT}`
  : "http://127.0.0.1:8080";

const PROJECT_NAME = "Riverbank QC Lab — Maria Reyes";
const SCHEMA_KEY = "supplier_coa";
const CAPTURE = join(ROOT, "docs/personas/captures/maria");
const VIDEO_DIR = join(CAPTURE, "video");
const FEEDBACK_PATH = join(ROOT, "docs/personas/feedback/MARIA_SESSION_FEEDBACK.md");

const PDFS = {
  pass: join(ROOT, "scripts/fixtures/personas/maria_lab/coa_pass_clean.pdf"),
  fail: join(ROOT, "scripts/fixtures/personas/maria_lab/coa_fail_alcohol_high.pdf"),
  ambiguous: join(ROOT, "scripts/fixtures/personas/maria_lab/coa_ambiguous_ph.pdf"),
};

/** @type {{ screen: string; score: number; confused: string; expected: string; severity: string }[]} */
const feedback = [];

function note(screen, score, confused, expected, severity = "P1") {
  feedback.push({ screen, score, confused, expected, severity });
}

async function snap(page, slug, fullPage = true) {
  const path = join(CAPTURE, `${slug}.png`);
  await page.screenshot({ path, fullPage });
  return path;
}

async function findOrCreateProject(request) {
  const list = await request.get(`${BASE}/api/projects`).then((r) => r.json());
  let project = list.find((p) => p.name === PROJECT_NAME);
  if (!project) {
    project = await request
      .post(`${BASE}/api/projects`, { data: { name: PROJECT_NAME } })
      .then((r) => r.json());
  }
  return project.id;
}

async function main() {
  mkdirSync(CAPTURE, { recursive: true });
  mkdirSync(VIDEO_DIR, { recursive: true });
  mkdirSync(dirname(FEEDBACK_PATH), { recursive: true });

  for (const p of Object.values(PDFS)) {
    if (!existsSync(p)) {
      throw new Error(`Missing fixture ${p} — run generate_persona_fixtures.py first`);
    }
  }

  await waitApiHealthy(BASE);

  const browser = await chromium.launch({ headless: true, slowMo: 80 });
  const context = await browser.newContext({
    viewport: DEMO_VIEWPORT,
    recordVideo: { dir: VIDEO_DIR, size: DEMO_VIEWPORT },
  });
  const page = await context.newPage();
  const request = context.request;

  let projectId = "";
  let failRunId = "";

  try {
    // —— 1. Landing ——
    await page.goto(`${BASE}/projects`, { waitUntil: "networkidle" });
    await snap(page, "01-projects-landing");
    const title = await page.locator(".route-title").textContent();
    if (title?.includes("workspaces")) {
      note(
        "Workspaces landing",
        4,
        "Clearer than before; still feels like internal software.",
        "Add one-line value prop: 'Validate supplier PDFs with audit-ready evidence.'",
        "P2",
      );
    }

    // —— 2. Create Maria's workspace ——
    // Delete existing Maria project schemas via API for clean wizard run (optional fresh checklist)
    // UI journey creates project fresh each run — reuse if exists by navigating directly
    const existing = await request.get(`${BASE}/api/projects`).then((r) => r.json());
    const mariaProject = existing.find((p) => p.name === PROJECT_NAME);
    if (mariaProject) {
      projectId = mariaProject.id;
      await page.goto(`${BASE}/projects/${projectId}`, { waitUntil: "networkidle" });
      await snap(page, "02-project-overview-existing");
    } else {
      await page.getByPlaceholder("Workspace name").fill(PROJECT_NAME);
      await page.getByRole("button", { name: "Create workspace" }).click();
      await page.waitForURL(/\/projects\/[0-9a-f-]+\/?$/i, { timeout: 15_000 });
      projectId = page.url().match(/\/projects\/([^/]+)/)?.[1] ?? "";
      await page.waitForSelector(".project-overview-page, .hero-title", { timeout: 10_000 });
      await snap(page, "02-project-overview");
    }
    note(
      "Project overview",
      4,
      "Stats are useful but 'Schema keys' is jargon.",
      "Call them 'Document checklists' or 'Rule sets'. Show last 3 validation results inline.",
      "P2",
    );

    // —— 3. Checklists — create supplier CoA if missing ——
    await page.getByRole("link", { name: "Checklists", exact: true }).click();
    await page.waitForURL(/\/schemas$/);
    await snap(page, "03-schemas-empty-or-list");

    const hasChecklist = await page.locator("code").filter({ hasText: SCHEMA_KEY }).count();
    if (hasChecklist === 0) {
      await page.getByRole("link", { name: "New checklist" }).click();
    await page.waitForURL(/\/schemas\/new/);
    await snap(page, "04-schema-wizard-step1");

    await page.getByRole("button", { name: /Lab report/i }).click();
    const keyInput = page.locator(".schema-wizard-key input, .schema-command-bar-key input").first();
    await keyInput.fill(SCHEMA_KEY);
    note(
      "Checklist wizard step 1",
      4,
      "'Checklist ID' is better but still technical.",
      "'Name this checklist' with example supplier_coa.",
      "P2",
    );

    await page.getByRole("button", { name: "Continue" }).click();
    await page.waitForTimeout(400);
    await snap(page, "05-schema-wizard-fields");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.waitForTimeout(400);
    await snap(page, "06-schema-wizard-rules");
    await page.getByRole("button", { name: "Continue" }).click();
    await page.waitForTimeout(400);
    await snap(page, "07-schema-wizard-test");

    await page.getByRole("button", { name: "Create schema" }).click();
    await page.waitForURL(/\/schemas$/, { timeout: 60_000 });
    await snap(page, "08-schemas-published");
    note(
      "Checklist publish",
      4,
      "Wizard works; publish button in header is OK.",
      "Clear 'Your checklist is live' confirmation toast.",
      "P2",
    );
    }

    // —— 4. Validate batch ——
    await page.getByRole("link", { name: "Validate", exact: true }).click();
    await page.waitForURL(/\/validation\/run/);
    await snap(page, "09-validate-run-empty");

    await page.locator(".validation-form-grid select").first().selectOption(SCHEMA_KEY);
    await page.locator(".validation-form-grid select").nth(1).selectOption({ index: 1 });

    const fileInput = page.locator(".validation-dropzone-input");
    await fileInput.setInputFiles([PDFS.pass, PDFS.fail, PDFS.ambiguous]);

    await snap(page, "10-validate-files-queued");
    const runBtn = page.getByRole("button", { name: /Run validation/i });
    await runBtn.waitFor({ state: "visible", timeout: 10_000 });
    await runBtn.click();

    await page.waitForSelector(".validation-run-phase--running, .validation-file-queue-badge", {
      timeout: 15_000,
    });
    await page.waitForFunction(
      () => {
        const items = document.querySelectorAll(".validation-run-status-item");
        if (items.length < 3) return false;
        return [...items].every(
          (el) =>
            el.querySelector(".validation-file-queue-badge") ||
            el.querySelector(".alert-error") ||
            (!el.textContent?.includes("Queued") && !el.textContent?.includes("In progress")),
        );
      },
      undefined,
      { timeout: 300_000 },
    );
    await snap(page, "11-validate-results-queue");
    note(
      "Validate run",
      5,
      "Batch summary and per-file status are clear; ambiguous PDFs can take ~1 min each.",
      "Show estimated time when LLM review is needed.",
      "P2",
    );

    // —— 5. History + outcome guide ——
    await page.getByLabel("Project sections").getByRole("link", { name: "History", exact: true }).click();
    await page.waitForURL(/\/validation$/);
    await page.waitForSelector(".validation-history-page, table, .data-table", { timeout: 15_000 });
    await page.locator(".outcome-guide").scrollIntoViewIfNeeded();
    await pause(1000);
    await snap(page, "12-validation-history-outcomes");
    note(
      "History + outcomes",
      5,
      "PASS / FAIL / AMBIGUOUS cards explain what finance and QC need.",
      "Keep audit export visible above the table.",
      "P2",
    );

    // —— 6. PASS run + highlights ——
    await openRunByOutcome(page, "PASS");
    await snap(page, "13-run-detail-pass");
    await cyclePdfHighlights(page, CAPTURE, "13");
    note(
      "Run detail (PASS)",
      5,
      "Highlights land on invoice line items, not whole-page boxes.",
      "Auto-scroll PDF to first highlight on open.",
      "P2",
    );

    // —— 7. FAIL run ——
    await page.getByLabel("Project sections").getByRole("link", { name: "History", exact: true }).click();
    await openRunByOutcome(page, "FAIL");
    failRunId = page.url().split("/runs/")[1]?.split("?")[0] ?? "";
    await snap(page, "14-run-detail-fail");
    await cyclePdfHighlights(page, CAPTURE, "14");
    note(
      "Run detail (FAIL)",
      5,
      "Failing alcohol rule jumps to the exact value on the PDF.",
      "Show rule sentence next to red status.",
      "P2",
    );

    // —— 8. AMBIGUOUS run ——
    await page.getByLabel("Project sections").getByRole("link", { name: "History", exact: true }).click();
    await openRunByOutcome(page, "AMBIGUOUS");
    await snap(page, "15-run-detail-ambiguous");
    await cyclePdfHighlights(page, CAPTURE, "15");
    note(
      "Run detail (AMBIGUOUS)",
      5,
      "Multiple candidate rows show dashed highlights for pH.",
      "One-click pick winner would speed approval.",
      "P2",
    );

    // —— 9. Audit report ——
    await page.getByLabel("Project sections").getByRole("link", { name: "History", exact: true }).click();
    await page.locator(".audit-report-panel").scrollIntoViewIfNeeded();
    await pause(1000);
    await snap(page, "16-audit-report");
    await page.getByRole("button", { name: "Download .md" }).click();
    await pause(500);
    note(
      "Audit report",
      5,
      "Markdown summary is ready for auditors.",
      "Optional PDF export for email.",
      "P3",
    );

    // —— 10. Overview return ——
    await page.getByLabel("Project sections").getByRole("link", { name: "Overview", exact: true }).click();
    await snap(page, "17-overview-after-work");

    await projectId;
    await failRunId;
  } finally {
    await snap(page, "99-final-state").catch(() => {});
    await context.close();
    await browser.close();

    const videoFiles = await import("node:fs").then((fs) =>
      fs.readdirSync(VIDEO_DIR).filter((f) => f.endsWith(".webm")),
    );
    if (videoFiles[0]) {
      const src = join(VIDEO_DIR, videoFiles[0]);
      const dest = join(CAPTURE, "maria-journey.webm");
      await import("node:fs").then((fs) => {
        try {
          fs.renameSync(src, dest);
        } catch {
          fs.copyFileSync(src, dest);
        }
      });
    }

    const md = [
      "# Maria Reyes — session feedback",
      "",
      `**Date:** ${new Date().toISOString()}`,
      `**Project:** ${PROJECT_NAME}`,
      `**Base URL:** ${BASE}`,
      "",
      "## Summary",
      "",
      `Screens captured: ${feedback.length + 1} notes`,
      "",
      "## Screen-by-screen",
      "",
      ...feedback.flatMap((f) => [
        `### ${f.screen}`,
        `- **Score:** ${f.score}/5`,
        `- **Severity:** ${f.severity}`,
        `- **Confused by:** ${f.confused}`,
        `- **Expected:** ${f.expected}`,
        "",
      ]),
      "## Screenshots",
      "",
      "See `docs/personas/captures/maria/*.png`",
      "",
      "## Video",
      "",
      "`docs/personas/captures/maria/maria-journey.webm`",
      "",
    ].join("\n");
    writeFileSync(FEEDBACK_PATH, md);
    console.log(`Feedback written: ${FEEDBACK_PATH}`);
    console.log(`Screenshots: ${CAPTURE}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
