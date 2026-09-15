/**
 * Browser E2E: create invoice schema via AI assistant prompt, dry-run + full validation.
 */
import { chromium } from "playwright";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..", "..");
const BASE = process.env.GATEWAY_HTTP_PORT
  ? `http://127.0.0.1:${process.env.GATEWAY_HTTP_PORT}`
  : "http://127.0.0.1:8080";
const PDF = join(ROOT, "backend/tests/fixtures/invoice/inv_cursor_formatted.pdf");
const SCHEMA_KEY = `inv_cursor_prompt_${Date.now()}`;

const USER_PROMPT =
  "Extract the name of the recipient of the invoice without validation, " +
  "extract the address of the recipient without validation, " +
  "extract the email of the recipient and valite it against mvillanueva.tolcachier@gmail.com. " +
  "EXtract the invoice number using llm not regex. " +
  'Extract "fecha de emisión" and "fecha de vencimiento", ' +
  "last but not least extract the Total due and validate that is 20.0 USD";

const TRUTH_STRICT = {
  invoice_number: "DOEA864B-0011",
  recipient_email: "mvillanueva.tolcachier@gmail.com",
  total_due: "20",
  issue_date: "9 de agosto de 2025",
  due_date: "9 de agosto de 2025",
};
const TRUTH_OPEN = {
  recipient_name: "Maximiliano Villanueva",
};

async function waitForDslValid(page) {
  await page.locator(".schema-dsl-badge--ok", { hasText: "Valid" }).waitFor({ timeout: 60_000 });
}

function hasSchemaField(body, name) {
  return Boolean(body.fields?.[name] ?? body.open_ended?.[name]);
}

function assertCanonicalAgentSchema(body) {
  const required = ["invoice_number", "issue_date", "due_date", "total_due", "recipient_email"];
  for (const name of required) {
    if (!hasSchemaField(body, name)) {
      throw new Error(`Agent schema missing canonical field: ${name}`);
    }
  }
  for (const name of ["recipient_name", "recipient_address"]) {
    if (!hasSchemaField(body, name)) {
      throw new Error(`Agent schema missing open-ended field: ${name}`);
    }
  }
  const inv = body.fields?.invoice_number ?? {};
  if (inv.regex_hint) {
    throw new Error(`invoice_number must not have regex_hint (LLM-only): ${inv.regex_hint}`);
  }
  if (!inv.llm_fallback) {
    throw new Error("invoice_number must set llm_fallback: true for LLM extraction");
  }
  if (body.fields?.document_total || body.fields?.total_amount) {
    throw new Error("Use canonical field name total_due, not document_total/total_amount");
  }
}

async function schemaFromAgent(page, assistantPane, prompt, maxAttempts = 5) {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const compose = assistantPane.locator(".schema-agent-compose textarea");
    await compose.fill(prompt);
    const agentMsgsBefore = await assistantPane.locator(".schema-agent-msg--assistant").count();
    const [agentResponse] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/schema-agent/chat") && r.request().method() === "POST",
        { timeout: 300_000 },
      ),
      assistantPane.getByRole("button", { name: "Send" }).click(),
    ]);
    await page
      .locator(".schema-agent-msg--assistant")
      .nth(agentMsgsBefore)
      .waitFor({ timeout: 300_000 });
    const agentPayload = await agentResponse.json();
    const body = agentPayload.schema_body;
    try {
      assertCanonicalAgentSchema(body);
      console.log(`OK agent replied (attempt ${attempt})`);
      return body;
    } catch (err) {
      const fields = Object.keys(body.fields ?? {});
      const openEnded = Object.keys(body.open_ended ?? {});
      console.warn(
        `WARN agent attempt ${attempt}: ${err instanceof Error ? err.message : err} fields=${fields.join(",")} open=${openEnded.join(",")}`,
      );
    }
    if (attempt === maxAttempts) {
      throw new Error(`Agent schema incomplete after ${maxAttempts} attempts`);
    }
  }
  throw new Error("unreachable");
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
  page.setDefaultTimeout(180_000);

  try {
    await page.goto(`${BASE}/projects/${projectId}/schemas/new`);
    await page.getByRole("heading", { name: "New schema" }).waitFor();
    await page.getByRole("button", { name: "Skip wizard → workspace" }).click();
    await page.getByRole("heading", { name: "Schema assistant" }).waitFor();
    console.log("OK workspace with assistant");

    const assistantPane = page.locator(".schema-studio-assistant-pane");
    const body = await schemaFromAgent(page, assistantPane, USER_PROMPT);
    const fields = Object.keys(body.fields ?? {});
    const openEnded = Object.keys(body.open_ended ?? {});
    console.log(`OK schema fields strict=${fields.join(",")} open_ended=${openEnded.join(",")}`);

    await page.locator(".schema-command-bar-key input").fill(SCHEMA_KEY);
    await page.getByRole("tab", { name: "Workspace" }).click();
    await waitForDslValid(page);

    const rail = page.locator(".schema-studio-rail-pane");

    async function runDryRun() {
      await rail.getByRole("button", { name: "Choose PDF" }).click();
      await rail.locator('input[type="file"][accept*="pdf"]').setInputFiles(PDF);
      await rail.getByText("inv_cursor_formatted.pdf").waitFor();
      const [previewResponse] = await Promise.all([
        page.waitForResponse(
          (r) =>
            r.url().includes("/validation-schemas/preview") &&
            r.request().method() === "POST" &&
            r.status() === 200,
          { timeout: 300_000 },
        ),
        rail.getByRole("button", { name: "Run validation" }).click(),
      ]);
      const previewPayload = await previewResponse.json();
      const preview = previewPayload.validation;
      if (!preview) throw new Error(`Preview missing validation: ${JSON.stringify(previewPayload)}`);
      return preview;
    }

    let preview = await runDryRun();
    console.log(`dry_run status=${preview.status} parser=${preview.extraction_meta?.parser}`);

    if (preview.status !== "PASS") {
      const amb = JSON.stringify(preview.ambiguous_fields ?? []);
      const fails = JSON.stringify(preview.results ?? []);
      const refinePrompt =
        `The invoice PDF preview returned ${preview.status}. ` +
        `Ambiguous: ${amb}. Failures: ${fails}. ` +
        "Fix the schema for inv_cursor_formatted.pdf: Spanish labels fecha de emisión / fecha de vencimiento with anchored regex and llm_fallback; " +
        "total_due min and max 20; recipient_email equals mvillanueva.tolcachier@gmail.com; " +
        "invoice_number without regex_hint — set llm_fallback and llm_only on invoice_number; " +
        "use canonical keys issue_date, due_date, total_due; on_ambiguity best_match for dates.";
      await schemaFromAgent(page, assistantPane, refinePrompt);
      await waitForDslValid(page);
      preview = await runDryRun();
      console.log(`dry_run_retry status=${preview.status}`);
    }

    if (preview.status !== "PASS") {
      console.error("dry_run failures", preview.results);
      console.error("ambiguous", preview.ambiguous_fields);
      throw new Error(`Dry run expected PASS, got ${preview.status}`);
    }

    await rail.locator(".schema-preview-result").getByText("PASS").waitFor();
    const previewText = await rail.locator(".schema-preview-result").innerText();
    for (const [key, val] of Object.entries(TRUTH_STRICT)) {
      if (!previewText.includes(val)) {
        throw new Error(`Dry run missing expected ${key}=${val} in preview:\n${previewText}`);
      }
    }
    for (const [key, val] of Object.entries(TRUTH_OPEN)) {
      if (!previewText.includes(val)) {
        throw new Error(`Dry run missing open-ended ${key}=${val} in preview:\n${previewText}`);
      }
    }
    if (!previewText.includes("recipient_address")) {
      throw new Error(`Dry run missing recipient_address informative field in preview`);
    }
    console.log("OK dry-run preview values");

    await page.getByRole("button", { name: "Create schema" }).click();
    await page.waitForURL(`**/projects/${projectId}/schemas`, { timeout: 30_000 });
    await page.getByText(SCHEMA_KEY).waitFor();
    console.log("OK schema published");

    await page.goto(`${BASE}/projects/${projectId}/validation/run`);
    await page.getByRole("heading", { name: "Run validation" }).waitFor();
    await page.locator("select").nth(0).selectOption(SCHEMA_KEY);
    const versionSelect = page.locator("select").nth(1);
    await versionSelect.waitFor();
    const versionValue = await versionSelect.locator("option").nth(1).getAttribute("value");
    if (versionValue) await versionSelect.selectOption(versionValue);

    await page.locator('input[type="file"][accept*="pdf"]').setInputFiles(PDF);
    await page.getByText("inv_cursor_formatted.pdf").waitFor();

    const [runResponse] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/api/validate-document") && r.status() === 200,
        { timeout: 300_000 },
      ),
      page.getByRole("button", { name: /^Run validation/ }).click(),
    ]);
    await page.locator(".validation-status-pass").waitFor({ timeout: 300_000 });
    const runPayload = await runResponse.json();
    console.log(`full_run status=${runPayload.status} run_id=${runPayload.run_id}`);

    await page.goto(`${BASE}/projects/${projectId}/validation/runs/${runPayload.run_id}`);
    for (const val of [...Object.values(TRUTH_STRICT), ...Object.values(TRUTH_OPEN)]) {
      await page.getByText(val, { exact: false }).first().waitFor({ timeout: 60_000 });
    }
    console.log("OK full validation run detail");

    console.log("UI_INVOICE_PROMPT_SCHEMA_OK");
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
