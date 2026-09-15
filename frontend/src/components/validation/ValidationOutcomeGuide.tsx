/**
 * Plain-language guide to validation outcomes (for AP / QC users).
 * Collapsed by default so repeat visitors reach the run table faster.
 */

export default function ValidationOutcomeGuide() {
  return (
    <details className="outcome-guide outcome-guide--collapsible">
      <summary className="outcome-guide-summary">Understanding outcomes</summary>
      <div className="outcome-guide-grid">
        <article className="outcome-guide-card outcome-guide-card--pass">
          <h3>PASS</h3>
          <p>
            All <strong>required</strong> fields were found and satisfied their rules. Optional or
            informative fields may be empty — that does not change PASS.
          </p>
        </article>
        <article className="outcome-guide-card outcome-guide-card--fail">
          <h3>FAIL</h3>
          <p>
            A required field is missing, out of range, or breaks a rule (e.g. total ≠ subtotal + tax).
            Open the run to see which rule failed and jump to evidence on the PDF.
          </p>
        </article>
        <article className="outcome-guide-card outcome-guide-card--ambiguous">
          <h3>AMBIGUOUS</h3>
          <p>
            The document has <strong>conflicting readings</strong> for the same field. A human must
            pick the correct value before approval.
          </p>
        </article>
      </div>
    </details>
  );
}
