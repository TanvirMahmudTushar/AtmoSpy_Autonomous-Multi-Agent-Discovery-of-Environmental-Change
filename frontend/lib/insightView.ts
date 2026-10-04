// Presentation constants for the cause / impact / action view. Kept in one
// place so the report, the cards and the export describe a finding the same way.

import type { Concern, Confidence } from "./types";

export const CONCERN_LEVELS: Concern[] = ["none", "watch", "concerning", "serious"];

export const CONCERN_LABEL: Record<Concern, string> = {
  none: "No clear change",
  watch: "Worth watching",
  concerning: "Concerning",
  serious: "High concern",
};

export const CONCERN_COLOR: Record<Concern, string> = {
  none: "var(--app-muted)",
  watch: "var(--chart-warning)",
  concerning: "var(--app-accent-clay)",
  serious: "var(--chart-critical)",
};

export const CONFIDENCE_LABEL: Record<Confidence, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

export const SECTOR_LABEL: Record<string, string> = {
  agriculture: "Farming & food",
  water: "Water",
  health: "Health",
  ecosystems: "Nature",
  infrastructure: "Buildings & infrastructure",
  energy: "Energy",
  cryosphere: "Ice & sea level",
};

/** Sector -> sprite in components/pixel/icons.ts. */
export const SECTOR_SPRITE: Record<string, string> = {
  agriculture: "crop",
  water: "droplet",
  health: "health",
  ecosystems: "tree",
  infrastructure: "house",
  energy: "bolt",
  cryosphere: "snow",
};

/** Only a clearly harmful change gets the "how to reduce it" framing. */
export function isHarmful(concern: Concern): boolean {
  return concern === "concerning" || concern === "serious";
}
