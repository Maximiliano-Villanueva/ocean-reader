/**
 * Dismissible welcome tour on the project overview — three-step mental model.
 */

import { useState } from "react";
import { Link } from "react-router-dom";

import { dismissOnboarding, isOnboardingDismissed } from "../../lib/onboardingStorage";

type Props = {
  projectId: string;
  base: string;
  hasChecklists: boolean;
  hasRuns: boolean;
};

const STEPS = [
  {
    n: 1,
    title: "Define your checklist",
    body: "Pick a template (lab report, invoice) and publish acceptance rules.",
    to: "schemas/new",
    cta: "Create checklist",
    done: (p: Props) => p.hasChecklists,
  },
  {
    n: 2,
    title: "Validate PDFs",
    body: "Upload documents, run batch checks, and see PASS / FAIL / AMBIGUOUS instantly.",
    to: "validation/run",
    cta: "Upload PDFs",
    done: (p: Props) => p.hasRuns,
  },
  {
    n: 3,
    title: "Audit with evidence",
    body: "Open any run to see extracted fields and highlights on the source PDF.",
    to: "validation",
    cta: "View history",
    done: () => false,
  },
] as const;

/** Top-of-dashboard tour; hidden after the user dismisses it for this project. */
export default function ProjectWelcomeTour({ projectId, base, hasChecklists, hasRuns }: Props) {
  const [visible, setVisible] = useState(() => !isOnboardingDismissed(projectId));

  if (!visible) return null;

  const props = { projectId, base, hasChecklists, hasRuns };

  function onDismiss() {
    dismissOnboarding(projectId);
    setVisible(false);
  }

  return (
    <section className="project-welcome-tour" aria-label="Quick start guide">
      <header className="project-welcome-tour-head">
        <div>
          <p className="project-welcome-tour-kicker">Quick start</p>
          <h2 className="project-welcome-tour-title">How Ocean Read works</h2>
          <p className="muted small project-welcome-tour-lede">
            Three steps from supplier PDF to audit-ready evidence — no training manual required.
          </p>
        </div>
        <button type="button" className="btn-secondary btn-sm project-welcome-tour-dismiss" onClick={onDismiss}>
          Got it — hide this
        </button>
      </header>
      <ol className="project-welcome-tour-steps">
        {STEPS.map((step) => {
          const done = step.done(props);
          return (
            <li
              key={step.n}
              className={`project-welcome-tour-step${done ? " project-welcome-tour-step--done" : ""}`}
            >
              <span className="project-welcome-tour-step-num" aria-hidden>
                {done ? "✓" : step.n}
              </span>
              <div className="project-welcome-tour-step-body">
                <h3>{step.title}</h3>
                <p className="muted small">{step.body}</p>
                <Link className="project-welcome-tour-link" to={`${base}/${step.to}`}>
                  {step.cta} →
                </Link>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
