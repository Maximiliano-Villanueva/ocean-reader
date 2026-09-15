/**
 * Compact row actions for validation history — primary View link plus overflow menu.
 */

import { Link } from "react-router-dom";

import type { ValidationRunSummary } from "../../api";

type Props = {
  projectId: string;
  row: ValidationRunSummary;
  hidden: boolean;
  isBusy: boolean;
  canReRun: boolean;
  onReRun: () => void;
  onArchive: () => void;
  onRemove: () => void;
  onRestore: () => void;
};

/** History table actions: View always visible; secondary actions in a menu. */
export default function ValidationRunRowActions({
  projectId,
  row,
  hidden,
  isBusy,
  canReRun,
  onReRun,
  onArchive,
  onRemove,
  onRestore,
}: Props) {
  return (
    <div className="validation-run-actions">
      <Link className="table-action-link" to={`/projects/${projectId}/validation/runs/${row.id}`}>
        View
      </Link>
      <details className="run-row-menu">
        <summary className="run-row-menu-trigger" aria-label={`More actions for ${row.document_filename}`}>
          More
        </summary>
        <div className="run-row-menu-panel" role="menu">
          <button
            type="button"
            className="run-row-menu-item"
            role="menuitem"
            disabled={isBusy || !canReRun}
            onClick={onReRun}
          >
            Re-run
          </button>
          {hidden ? (
            <button
              type="button"
              className="run-row-menu-item"
              role="menuitem"
              disabled={isBusy}
              onClick={onRestore}
            >
              Restore
            </button>
          ) : (
            <>
              <button
                type="button"
                className="run-row-menu-item"
                role="menuitem"
                disabled={isBusy}
                onClick={onArchive}
              >
                Archive
              </button>
              <button
                type="button"
                className="run-row-menu-item run-row-menu-item--danger"
                role="menuitem"
                disabled={isBusy}
                onClick={onRemove}
              >
                Remove
              </button>
            </>
          )}
        </div>
      </details>
    </div>
  );
}
