/**
 * PDF.js viewer with bbox overlays for validation evidence (replaces plain iframe).
 * Page width follows the container so the viewer never overflows a sidebar column.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import type { PDFPageProxy } from "pdfjs-dist";
import type { PageViewport } from "pdfjs-dist";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// Worker must be configured in this module (same file as <Document>) — see react-pdf docs.
import { PDFJS_VERSION } from "../../setupPdfWorker";
const pdfWorkerBase = import.meta.env.BASE_URL ?? "/";
pdfjs.GlobalWorkerOptions.workerSrc =
  `${pdfWorkerBase}pdf.worker.min.mjs?v=${PDFJS_VERSION}`.replace(/\/{2,}/g, "/");
import type { PdfHighlight } from "../../lib/evidenceHighlights";
import { pageNumbersFromHighlights } from "../../lib/evidenceHighlights";
import { pymupdfBboxToViewportRect, viewportRectToCss } from "../../lib/pdfViewport";

export type PdfEvidenceViewerProps = {
  /** Blob URL or path accepted by ``react-pdf`` ``Document``. */
  file: string | File | null;
  highlights: PdfHighlight[];
  activeHighlightId?: string | null;
  onHighlightClick?: (highlight: PdfHighlight) => void;
  className?: string;
};

export default function PdfEvidenceViewer({
  file,
  highlights,
  activeHighlightId = null,
  onHighlightClick,
  className = "",
}: PdfEvidenceViewerProps) {
  const [numPages, setNumPages] = useState(0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [viewports, setViewports] = useState<Record<number, PageViewport>>({});
  const [pageWidth, setPageWidth] = useState<number | undefined>(undefined);
  const scrollRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Record<number, HTMLDivElement | null>>({});

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const sync = () => {
      const w = Math.floor(el.clientWidth - 4);
      if (w > 120) setPageWidth(w);
    };
    sync();
    const ro = new ResizeObserver(sync);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!activeHighlightId) return;
    const h = highlights.find((x) => x.id === activeHighlightId);
    if (!h) return;
    pageRefs.current[h.page]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [activeHighlightId, highlights]);

  const onDocumentLoadSuccess = useCallback(({ numPages: n }: { numPages: number }) => {
    setNumPages(n);
    setLoadError(null);
    setViewports({});
  }, []);

  const registerViewport = useCallback(
    (pageNumber: number, pdfPage: { getViewport: PDFPageProxy["getViewport"] }) => {
      if (!pageWidth) return;
      const base = pdfPage.getViewport({ scale: 1 });
      const scale = pageWidth / base.width;
      const vp = pdfPage.getViewport({ scale });
      setViewports((prev) => ({ ...prev, [pageNumber]: vp }));
    },
    [pageWidth],
  );

  const pagesToShow = useMemo(() => {
    if (numPages > 0) {
      return Array.from({ length: numPages }, (_, i) => i + 1);
    }
    return pageNumbersFromHighlights(highlights);
  }, [highlights, numPages]);

  const highlightsOnPage = (pageNumber: number) => highlights.filter((h) => h.page === pageNumber);

  if (!file) {
    return <p className="muted pdf-evidence-empty">No PDF to display.</p>;
  }

  return (
    <div className={`pdf-evidence-viewer ${className}`.trim()} aria-label="PDF with evidence highlights">
      <p className="pdf-evidence-legend muted small">
        {highlights.length > 0 ? (
          <>
            <strong>{highlights.length}</strong> region{highlights.length === 1 ? "" : "s"} on PDF
            <span className="pdf-legend-swatch pdf-highlight--field" /> field
            <span className="pdf-legend-swatch pdf-highlight--error" /> fail
            <span className="pdf-legend-swatch pdf-highlight--candidate" /> ambiguous
          </>
        ) : (
          <>No bounding boxes — run validation again; evidence highlights need a recent pipeline run.</>
        )}
      </p>
      {loadError ? <p className="alert-error">{loadError}</p> : null}
      <div className="pdf-evidence-scroll" ref={scrollRef}>
        <Document
          file={file}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={(e) => setLoadError(e.message)}
          loading={<p className="muted">Loading PDF…</p>}
          error={<p className="alert-error">Could not load PDF.</p>}
        >
          {pagesToShow.map((pageNumber) => {
            const vp = viewports[pageNumber];
            const pageHighlights = highlightsOnPage(pageNumber);
            return (
              <div
                key={pageNumber}
                className="pdf-evidence-page"
                data-page={pageNumber}
                ref={(el) => {
                  pageRefs.current[pageNumber] = el;
                }}
              >
                <p className="pdf-evidence-page-label muted small">Page {pageNumber}</p>
                <div className="pdf-evidence-page-inner">
                  {pageWidth ? (
                    <Page
                      key={`${pageNumber}-${pageWidth}`}
                      pageNumber={pageNumber}
                      width={pageWidth}
                      renderTextLayer={false}
                      renderAnnotationLayer={false}
                      onLoadSuccess={(pdfPage) => registerViewport(pageNumber, pdfPage)}
                    />
                  ) : (
                    <p className="muted small">Preparing viewer…</p>
                  )}
                  {vp && pageHighlights.length > 0 ? (
                    <div
                      className="pdf-highlight-layer"
                      style={{ width: vp.width, height: vp.height }}
                    >
                      {pageHighlights.map((h) => {
                        let css: ReturnType<typeof viewportRectToCss>;
                        try {
                          css = viewportRectToCss(pymupdfBboxToViewportRect(h.bbox, vp));
                        } catch {
                          return null;
                        }
                        return (
                          <button
                            key={h.id}
                            type="button"
                            className={`pdf-highlight pdf-highlight--${h.kind} ${
                              activeHighlightId === h.id ? "pdf-highlight--active" : ""
                            }`}
                            style={css}
                            title={h.label}
                            aria-label={h.label}
                            onClick={() => onHighlightClick?.(h)}
                          />
                        );
                      })}
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </Document>
      </div>
    </div>
  );
}
