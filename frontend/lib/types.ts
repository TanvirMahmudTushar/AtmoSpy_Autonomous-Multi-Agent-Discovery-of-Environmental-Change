// Mirrors backend/app/schemas/api.py — kept hand-in-sync deliberately (no
// codegen step) since the schema surface is small and stable.

export interface User {
  id: string;
  email: string;
  display_name: string | null;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export type InvestigationMode = "nlp" | "discover";
export type InvestigationStatus = "pending" | "running" | "completed" | "failed" | "insufficient_data";
export type SignificanceClassification = "statistically_significant" | "not_significant";
export type DatasetStatus = "active" | "planned" | "requires_credentials";

export interface InvestigationStep {
  seq: number;
  agent: string;
  status: "running" | "done" | "error" | "skipped";
  message: string;
  detail: Record<string, unknown> | null;
  created_at?: string;
  ts?: string;
}

export interface Investigation {
  id: string;
  mode: InvestigationMode;
  question: string | null;
  status: InvestigationStatus;
  plan: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
  steps: InvestigationStep[];
}

export interface DiscoveryScore {
  trend_magnitude_pct: number;
  significance_strength: number;
  data_completeness: number;
  persistence_score: number;
  spatial_extent_fraction: number;
  weights: Record<string, number>;
  weighted_total: number;
  rank?: number;
}

/** none | watch | concerning | serious — from the backend's app/knowledge/insight.py. */
export type Concern = "none" | "watch" | "concerning" | "serious";
export type Confidence = "low" | "medium" | "high";

export interface Insight {
  concern: Concern;
  concern_reasons: string[];
  /** Trust in the finding itself (robustness + skeptic verdicts), not in any explanation of it. */
  confidence: Confidence;
  confidence_reasons: string[];
  family: string;
  direction: "up" | "down" | "flat";
  /** false when there is no clear change: nothing is explained, and nothing is invented. */
  applicable: boolean;
  headline: string;
  /** What this finding's own computed data says that bears on cause. */
  evidence: Array<{ kind: "step" | "related" | "spatial" | "data"; text: string }>;
  /** General, hedged context for this kind of change — not attributed to this finding. */
  drivers: Array<{ title: string; text: string }>;
  impacts: Array<{ sector: string; text: string }>;
  mitigate: string[];
  adapt: string[];
  region_context: string | null;
  disclaimer: string;
  references: Array<{ label: string; url: string }>;
}

export interface FindingSummary {
  id: string;
  title: string;
  variable_code: string;
  variable_name: string;
  region_code: string;
  region_name: string;
  period_start: string;
  period_end: string;
  trend_per_year: number;
  trend_units: string;
  total_change: number;
  percent_change: number | null;
  /** |total_change| / std. dev. of the annual series; null on un-backfilled legacy rows. */
  effect_size: number | null;
  p_value: number;
  significance_classification: SignificanceClassification;
  concern: Concern;
  discovery_score: DiscoveryScore | null;
  created_at: string;
}

export interface RelatedVariable {
  variable_code: string;
  variable_name: string;
  units: string;
  method: string;
  r: number;
  p_value: number;
  n: number;
  aligned_years: number[];
}

export interface SpatialSummary {
  total_cells: number;
  significant_cells: number;
  increasing_cells: number;
  decreasing_cells: number;
  increasing_fraction: number;
  decreasing_fraction: number;
  has_opposite_regional_trends: boolean;
  increasing_examples: Array<{ lat: number; lon: number; slope_per_year: number; p_value: number }>;
  decreasing_examples: Array<{ lat: number; lon: number; slope_per_year: number; p_value: number }>;}

export interface TimeSeriesChartData {
  kind: "timeseries";
  variable_name: string;
  units: string;
  points: Array<{ year: number; value: number }>;
  trend_line: Array<{ year: number; fitted: number }>;
  trend_band: Array<{ year: number; lower: number; upper: number }>;
  change_points: Array<{ year: number; mean_before: number; mean_after: number; shift: number }>;
  trend_summary: { slope_per_year: number; p_value: number; method: string };
}

export interface SpatialMapChartData {
  kind: "spatial_map";
  variable_name: string;
  units: string;
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: { slope_per_year: number; p_value: number; significant: boolean; direction: "increasing" | "decreasing" };
  }>;
}

export interface SpatialTimelapseChartData {
  kind: "spatial_timelapse";
  variable_name: string;
  units: string;
  years: number[];
  value_min: number | null;
  value_max: number | null;
  frames: Record<
    string,
    {
      type: "FeatureCollection";
      features: Array<{
        type: "Feature";
        geometry: { type: "Point"; coordinates: [number, number] };
        properties: { value: number };
      }>;
    }
  >;
}

export interface ScatterChartData {
  kind: "scatter";
  x_name: string;
  y_name: string;
  points: Array<{ year: number; x: number; y: number }>;
  correlation: { method: string; r: number; p_value: number };
}

export interface FindingDetail extends FindingSummary {
  what: string;
  where: string;
  statistical_method: string;
  confidence_interval: { lower: number; upper: number; confidence: number } | null;
  importance_note: string;
  data_quality: Record<string, unknown>;
  spatial_summary: SpatialSummary | null;
  related_variables: RelatedVariable[] | null;
  robustness: { verdict: string; caveats: string[] } | null;
  skeptic_review: { verdict: string; points: string[] } | null;
  interpretation: string;
  limitations: string;
  narrative_source: "llm" | "template";
  visualizations: {
    timeseries?: TimeSeriesChartData;
    spatial_map?: SpatialMapChartData;
    spatial_timelapse?: SpatialTimelapseChartData;
    scatter?: ScatterChartData;
  };
  provenance: {
    source_name: string;
    dataset_version: string | null;
    retrieval_time: string;
    processing_method: string;
    statistical_method: string;
    url: string;
  } | null;
  insight: Insight | null;
}

export interface DatasetInfo {
  code: string;
  name: string;
  provider: string;
  description: string;
  status: DatasetStatus;
  requires_credentials: boolean;
  version: string | null;
  variables: Array<{ code: string; name: string; units: string }>;
}

export interface VariableInfo {
  code: string;
  name: string;
  units: string;
  description: string;
  dataset_code: string;
}

export interface Watch {
  id: string;
  region_code: string;
  variable_code: string;
  frequency_days: number;
  is_active: boolean;
  created_at: string;
  last_checked_at: string | null;
  next_check_at: string;
  last_investigation_id: string | null;
  last_finding_id: string | null;
  last_trend_per_year: number | null;
  last_significance: SignificanceClassification | null;
  prev_trend_per_year: number | null;
  prev_significance: SignificanceClassification | null;
  last_check_note: string | null;
}

export interface RegionInfo {
  code: string;
  name: string;
  kind: string;
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
  centroid_lat: number;
  centroid_lon: number;
}
