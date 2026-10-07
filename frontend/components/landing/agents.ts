export type AgentId = "data" | "stats" | "trend" | "spatial" | "skeptic" | "report";

export interface AgentMeta {
  id: AgentId;
  /** Short tag drawn above the character in the scene. */
  tag: string;
  name: string;
  role: string;
  color: string;
}

/** The crew shown in the landing-page diorama. Each one mirrors a real
 * backend agent (backend/app/agents/*) and acts out that agent's job. */
export const AGENTS: AgentMeta[] = [
  {
    id: "data",
    tag: "DATA",
    name: "NASA Data Agent",
    role: "Pulls real NASA POWER, SMAP and GRACE records down from the satellite feed and hands them to the lab.",
    color: "#4f8fd1",
  },
  {
    id: "stats",
    tag: "STATS",
    name: "Statistics Agent",
    role: "Runs Mann-Kendall, Sen's slope and OLS regression on every series. Deterministic Python, no guessing.",
    color: "#1baf7a",
  },
  {
    id: "trend",
    tag: "TREND",
    name: "Trend Agent",
    role: "Draws out the direction of change and looks for changepoints in the record.",
    color: "#eda100",
  },
  {
    id: "spatial",
    tag: "SPATIAL",
    name: "Spatial Agent",
    role: "Probes grid cell after grid cell to find where the change happens, and where it goes the other way.",
    color: "#38bdf8",
  },
  {
    id: "skeptic",
    tag: "SKEPTIC",
    name: "Skeptic Agent",
    role: "Doubts everything. Reviews each result for weak data, small effects and causal overreach before it is saved.",
    color: "#e34948",
  },
  {
    id: "report",
    tag: "REPORT",
    name: "Report Agent",
    role: "Files the checked result as a cited scientific finding.",
    color: "#a78bfa",
  },
];

export const AGENT_BY_ID = Object.fromEntries(AGENTS.map((a) => [a.id, a])) as Record<AgentId, AgentMeta>;

/** Order an investigation moves through the crew in the diorama. */
export const PIPELINE_STAGES: AgentId[] = ["data", "stats", "trend", "spatial", "skeptic", "report"];

/** Topics the diorama's "live investigation" cycles through. These are real
 * region/variable pairs from the Discover scan (backend/app/nasa/regions.py
 * DISCOVERY_CANDIDATES), shown without numbers because nothing is computed. */
export const INVESTIGATION_TOPICS = [
  "Soil moisture · Indo-Gangetic Plain",
  "Temperature · Tibetan Plateau",
  "Rainfall · West Sahel",
  "Soil moisture · California Central Valley",
  "Temperature · Arctic Alaska North Slope",
  "Rainfall · Central Amazon Basin",
  "Soil moisture · Lake Chad Basin",
  "Temperature · Bangladesh",
  "Soil moisture · Murray-Darling Basin",
  "Temperature · Southern Greenland",
];
