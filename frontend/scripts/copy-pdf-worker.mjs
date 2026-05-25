/**
 * Copy PDF.js worker next to the static app (``public/``) so production serves it
 * with a stable URL and the same version as ``react-pdf``'s bundled ``pdfjs-dist``.
 */

import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
/** Same version as ``react-pdf`` (see ``package.json`` pin). */
const workerSource = require.resolve("pdfjs-dist/build/pdf.worker.min.mjs", {
  paths: [join(dirname(fileURLToPath(import.meta.url)), "..")],
});
const publicDir = join(dirname(fileURLToPath(import.meta.url)), "..", "public");

mkdirSync(publicDir, { recursive: true });
copyFileSync(workerSource, join(publicDir, "pdf.worker.min.mjs"));
console.log(`Copied PDF.js worker from ${workerSource}`);
