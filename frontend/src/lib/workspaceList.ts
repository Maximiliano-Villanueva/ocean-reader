/**
 * Workspace list helpers for the projects landing page.
 */

import type { Project } from "../api";

/** Collapse duplicate workspace names — keeps the last entry (typically the newest). */
export function dedupeWorkspacesByName(projects: Project[]): Project[] {
  const byName = new Map<string, Project>();
  for (const project of projects) {
    byName.set(project.name, project);
  }
  return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name));
}
