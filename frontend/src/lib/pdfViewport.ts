/**
 * Map PyMuPDF layout bboxes to ``react-pdf`` / PDF.js viewport pixels.
 *
 * PyMuPDF uses origin **top-left** (y down). PDF.js ``convertToViewportRectangle`` expects
 * PDF user space (origin **bottom-left**). We flip Y using the page ``viewBox`` height.
 */

import type { PageViewport } from "pdfjs-dist";

export type ViewportRect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

/** Convert ``[x0,y0,x1,y1]`` (PyMuPDF) to pixel rect over a rendered page viewport. */
export function pymupdfBboxToViewportRect(
  bbox: [number, number, number, number],
  viewport: PageViewport,
): ViewportRect {
  const [x0, y0, x1, y1] = bbox;
  const viewBox = viewport.viewBox;
  const pageH = viewBox[3] - viewBox[1];
  const pdfY0 = pageH - y1;
  const pdfY1 = pageH - y0;
  const r = viewport.convertToViewportRectangle([x0, pdfY0, x1, pdfY1]);
  const left = Math.min(r[0], r[2]);
  const top = Math.min(r[1], r[3]);
  const width = Math.max(Math.abs(r[2] - r[0]), 2);
  const height = Math.max(Math.abs(r[3] - r[1]), 2);
  return { left, top, width, height };
}

export function viewportRectToCss(rect: ViewportRect): {
  left: string;
  top: string;
  width: string;
  height: string;
} {
  return {
    left: `${rect.left}px`,
    top: `${rect.top}px`,
    width: `${rect.width}px`,
    height: `${rect.height}px`,
  };
}
