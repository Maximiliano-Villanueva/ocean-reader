/**
 * Per-project onboarding dismissal flags (localStorage).
 */

const STORAGE_KEY = "ocean_read_onboarding_dismissed";

/** Whether the user closed the welcome tour for this project. */
export function isOnboardingDismissed(projectId: string): boolean {
  if (!projectId) return true;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return false;
    const ids = JSON.parse(raw) as string[];
    return Array.isArray(ids) && ids.includes(projectId);
  } catch {
    return false;
  }
}

/** Remember that the user no longer needs the welcome tour on this project. */
export function dismissOnboarding(projectId: string): void {
  if (!projectId) return;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const ids = raw ? (JSON.parse(raw) as string[]) : [];
    if (!ids.includes(projectId)) {
      ids.push(projectId);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
    }
  } catch {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([projectId]));
  }
}
