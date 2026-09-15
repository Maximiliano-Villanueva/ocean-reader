/**
 * Shared helpers for sales-demo Playwright recordings (slow, deliberate, screenshots).
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

export const DEMO_VIEWPORT = { width: 1440, height: 900 };

export function pause(ms = 1200) {
  return new Promise((r) => setTimeout(r, ms));
}

export async function snap(page, captureDir, slug, { fullPage = true, delayMs = 800 } = {}) {
  mkdirSync(captureDir, { recursive: true });
  await pause(delayMs);
  const path = join(captureDir, `${slug}.png`);
  await page.screenshot({ path, fullPage });
  return path;
}

export async function waitApiHealthy(base) {
  const res = await fetch(`${base}/api/health`);
  if (!res.ok) throw new Error(`API unhealthy: ${res.status}`);
}

export function writeFeedback(path, lines) {
  mkdirSync(join(path, ".."), { recursive: true });
  writeFileSync(path, lines.join("\n") + "\n");
}

/** Open a validation run from history by outcome pill (PASS / FAIL / AMBIGUOUS). */
export async function openRunByOutcome(page, outcome) {
  const pill = outcome.toLowerCase();
  const row = page
    .locator("tr")
    .filter({ has: page.locator(`.pill-${pill}`, { hasText: outcome }) })
    .first();
  await row.waitFor({ timeout: 30_000 });
  await row.locator("a").first().click();
  await page.waitForURL(/\/validation\/runs\//);
  await pause(2000);
}

/** Click each field row linked to PDF evidence and capture the highlight. */
export async function cyclePdfHighlights(page, captureDir, prefix) {
  const links = page.locator(".run-field-pdf-link");
  const n = await links.count();
  const limit = Math.min(n, 8);
  for (let i = 0; i < limit; i++) {
    await links.nth(i).scrollIntoViewIfNeeded();
    await links.nth(i).click();
    await pause(1800);
    await snap(page, captureDir, `${prefix}-pdf-highlight-${i + 1}`, { delayMs: 600 });
  }
}
