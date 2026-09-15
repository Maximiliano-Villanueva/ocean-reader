/**
 * Navigate core Ocean Read flows and capture screenshots for UX review.
 */
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");
const BASE = process.env.GATEWAY_HTTP_PORT
  ? `http://127.0.0.1:${process.env.GATEWAY_HTTP_PORT}`
  : "http://127.0.0.1:8080";
const OUT = join(ROOT, "docs/personas/captures/ux-review");

async function snap(page, name, opts = {}) {
  const path = join(OUT, `${name}.png`);
  await page.screenshot({ path, fullPage: opts.fullPage ?? true });
  return path;
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const notes = [];

  const projects = await fetch(`${BASE}/api/projects`).then((r) => r.json());
  const maria = projects.find((p) => p.name.includes("Maria"));
  const david = projects.find((p) => p.name.includes("David"));
  const projectId = maria?.id ?? projects[0]?.id;

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // 1 Workspaces
  await page.goto(`${BASE}/projects`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await snap(page, "01-workspaces");
  notes.push({ screen: "01-workspaces", url: "/projects" });

  if (!projectId) {
    await browser.close();
    writeFileSync(join(OUT, "index.json"), JSON.stringify({ notes, error: "no project" }, null, 2));
    return;
  }

  const base = `${BASE}/projects/${projectId}`;

  // 2 Overview
  await page.goto(base, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await snap(page, "02-overview");
  await page.screenshot({ path: join(OUT, "02-overview-viewport.png"), fullPage: false });

  // 3 Checklists
  await page.goto(`${base}/schemas`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await snap(page, "03-checklists");

  // 3b New checklist wizard
  await page.goto(`${base}/schemas/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await snap(page, "10-checklist-wizard");
  await page.screenshot({ path: join(OUT, "10-checklist-wizard-viewport.png"), fullPage: false });

  // 3c Edit checklist workspace
  const schemaGroups = await fetch(`${BASE}/api/projects/${projectId}/validation-schemas`).then((r) => r.json());
  const firstKey = schemaGroups?.[0]?.schema_key;
  if (firstKey) {
    await page.goto(`${base}/schemas/${encodeURIComponent(firstKey)}/edit`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    await snap(page, "11-checklist-editor");
    await page.screenshot({ path: join(OUT, "11-checklist-editor-viewport.png"), fullPage: false });
  }

  // 4 Validate
  await page.goto(`${base}/validation/run`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await snap(page, "04-validate");

  // 5 History
  await page.goto(`${base}/validation`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  await snap(page, "05-history-full");
  await page.screenshot({
    path: join(OUT, "05-history-viewport.png"),
    fullPage: false,
  });

  // 6 PASS run detail
  const runsData = await fetch(
    `${BASE}/api/projects/${projectId}/validation-runs?limit=30`,
  ).then((r) => r.json());
  const runs = runsData.items ?? runsData;
  const passRun = runs.find((r) => r.outcome === "PASS");
  const failRun = runs.find((r) => r.outcome === "FAIL");
  const ambRun = runs.find((r) => r.outcome === "AMBIGUOUS");

  if (passRun) {
    await page.goto(`${base}/validation/runs/${passRun.id}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    await snap(page, "06-run-pass");
    await page.screenshot({ path: join(OUT, "06-run-pass-viewport.png"), fullPage: false });
  }

  if (ambRun) {
    await page.goto(`${base}/validation/runs/${ambRun.id}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    await snap(page, "07-run-ambiguous");
    await page.screenshot({ path: join(OUT, "07-run-ambiguous-viewport.png"), fullPage: false });
  }

  if (failRun) {
    await page.goto(`${base}/validation/runs/${failRun.id}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    await snap(page, "08-run-fail");
  }

  // David workspace if exists
  if (david?.id) {
    await page.goto(`${BASE}/projects/${david.id}/validation`, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    await snap(page, "09-david-history");
  }

  await browser.close();
  writeFileSync(join(OUT, "index.json"), JSON.stringify({ notes, projectId, maria: maria?.name }, null, 2));
  console.log("UX review captures:", OUT);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
