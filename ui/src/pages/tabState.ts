export type AppTab = "dashboard" | "run" | "results";

export const TAB_ORDER: AppTab[] = ["dashboard", "run", "results"];

export function parseTabHash(hash: string): AppTab {
  const normalized = hash.replace(/^#/, "").trim().toLowerCase();
  if (normalized === "run") return "run";
  if (normalized === "results") return "results";
  return "dashboard";
}

export function tabToHash(tab: AppTab): string {
  return `#${tab}`;
}

export function nextTab(current: AppTab, direction: 1 | -1): AppTab {
  const index = TAB_ORDER.indexOf(current);
  const nextIndex = (index + direction + TAB_ORDER.length) % TAB_ORDER.length;
  return TAB_ORDER[nextIndex];
}
