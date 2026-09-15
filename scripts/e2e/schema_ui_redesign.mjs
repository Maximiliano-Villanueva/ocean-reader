/**
 * Browser E2E: schema UI redesign — wizard, workspace, simple, assistant, publish.
 *
 * Usage (stack on :8080):
 *   cd scripts/e2e && node schema_ui_redesign.mjs
 */
import { chromium } from "playwright";

const BASE = process.env.GATEWAY_HTTP_PORT
  ? `http://127.0.0.1:${process.env.GATEWAY_HTTP_PORT}`
  : "http://127.0.0.1:8080";
const SCHEMA_KEY = `e2e_ui_schema_${Date.now()}`;

async function waitForDslValid(page) {
  await page.locator(".schema-dsl-badge--ok", { hasText: "Valid" }).waitFor({ timeout: 30_000 });
}

async function main() {
  const health = await fetch(`${BASE}/api/health`);
  if (!health.ok) throw new Error(`API unhealthy: ${health.status}`);

  const projects = await (await fetch(`${BASE}/api/projects`)).json();
  const project = projects.find((p) => p.name === "Default workspace") ?? projects[0];
  if (!project?.id) throw new Error("No project found");
  const projectId = project.id;
  console.log(`project_id=${projectId} schema_key=${SCHEMA_KEY}`);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.setDefaultTimeout(60_000);

  try {
    await page.goto(`${BASE}/projects`);
    await page.getByRole("link", { name: /Default workspace/i }).click();
    await page.getByRole("link", { name: "Schemas" }).click();
    await page.getByRole("heading", { name: "Schemas" }).waitFor();
    console.log("OK library page");

    await page.getByRole("link", { name: "New schema" }).click();
    await page.getByRole("heading", { name: "New schema" }).waitFor();
    await page.getByText("What kind of document are you validating?").waitFor();
    console.log("OK wizard step 1");

    await page.getByRole("button", { name: "Invoice" }).click();
    const keyInput = page.locator(".schema-command-bar-key input");
    await keyInput.waitFor();
    await keyInput.fill(SCHEMA_KEY);
    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByText("Values the pipeline must find").waitFor();
    console.log("OK wizard step 2 fields");

    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByText("How to read the PDF").waitFor();
    console.log("OK wizard step 3 PDF settings");

    await page.getByRole("button", { name: "Continue" }).click();
    await page.getByText("Test your schema").waitFor();
    console.log("OK wizard step 4 test");

    await page.getByRole("button", { name: "Open workspace" }).click();
    await page.getByRole("tab", { name: "Workspace" }).waitFor();
    await page.getByRole("heading", { name: "Schema assistant" }).waitFor();
    console.log("OK workspace + assistant");

    await page.getByRole("tab", { name: "Simple" }).click();
    await page.getByText("Fields to extract").first().waitFor();
    console.log("OK simple cards mode");

    await page.getByRole("tab", { name: "Workspace" }).click();
    await page.getByRole("button", { name: /invoice_number/ }).waitFor();
    console.log("OK outline nav");

    await page.getByRole("tab", { name: "JSON" }).click();
    await page.locator(".schema-json-editor").waitFor();
    const jsonText = await page.locator(".schema-json-editor").inputValue();
    if (!jsonText.includes("invoice_number")) {
      throw new Error("JSON editor missing invoice_number field");
    }
    console.log("OK JSON mode");

    await page.getByRole("tab", { name: "Workspace" }).click();
    await waitForDslValid(page);

    const publishBtn = page.getByRole("button", { name: "Create schema" });
    await publishBtn.waitFor();
    if (await publishBtn.isDisabled()) {
      const dsl = await page.locator(".schema-studio-dsl-status").innerText();
      throw new Error(`Create schema disabled. DSL status: ${dsl}`);
    }

    await publishBtn.click();
    await page.waitForURL(`**/projects/${projectId}/schemas`, { timeout: 30_000 });

    await page.getByRole("heading", { name: "Schemas" }).waitFor();
    await page.getByText(SCHEMA_KEY).waitFor();
    console.log("OK back on library with new schema card");

    await page
      .locator(".schema-library-card")
      .filter({ hasText: SCHEMA_KEY })
      .getByRole("link", { name: "Edit schema" })
      .click();
    await page.getByRole("heading", { name: "New revision" }).waitFor();
    await page.getByRole("tab", { name: "Workspace" }).waitFor();
    await waitForDslValid(page);
    console.log("OK edit revision workspace");

    console.log("UI_SCHEMA_REDESIGN_OK");
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
