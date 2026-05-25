/**
 * Configure PDF.js worker before any route or ``react-pdf`` component loads.
 *
 * Imported first from ``main.tsx``. ``PdfEvidenceViewer`` sets the same URL again
 * (react-pdf recommends configuring in the component module).
 */

import { pdfjs } from "react-pdf";

/** Keep in sync with ``package.json`` ``pdfjs-dist`` pin. */
export const PDFJS_VERSION = "5.4.296";

const base = import.meta.env.BASE_URL ?? "/";
const workerPath = `${base}pdf.worker.min.mjs?v=${PDFJS_VERSION}`.replace(/\/{2,}/g, "/");

pdfjs.GlobalWorkerOptions.workerSrc = workerPath;
