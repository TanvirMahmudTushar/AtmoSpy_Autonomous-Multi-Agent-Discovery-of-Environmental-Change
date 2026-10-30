import { test } from "node:test";
import assert from "node:assert/strict";

import { findingTour, scanTour } from "./demos.ts";
import { findingToMonthlyCsv } from "./export.ts";
import { GLOSSARY } from "./glossary.ts";
import type { FindingDetail, ScanResult } from "./types";

function finding(overrides: Partial<FindingDetail> = {}): FindingDetail {
  return {
    id: "f1",
    title: "Temperature in Testland, 1990-2020",
    variable_code: "T2M",
    variable_name: "Temperature",
    region_code: "testland",
    region_name: "Testland",
    period_start: "1990-01-01",
    period_end: "2020-12-31",
    trend_per_year: 0.03,
    trend_units: "degC/year",
    total_change: 0.9,
    percent_change: null,
    effect_size: 1.2,
    p_value: 0.004,
    significance_classification: "statistically_significant",
    concern: "watch",
    discovery_score: null,
    created_at: "2026-10-30T00:00:00Z",
    what: "Temperature (degC)",
    where: "Testland",
    statistical_method: "test",
    confidence_interval: null,
    importance_note: "",
    data_quality: {},
    spatial_summary: null,
    related_variables: null,
    robustness: null,
    skeptic_review: { verdict: "no major objections raised", points: [] },
    interpretation: "",
    limitations: "",
    narrative_source: "template",
    visualizations: {
      timeseries: {
        kind: "timeseries",
        variable_name: "Temperature",
        units: "degC",
        basis: "monthly_anomaly",
        points: [],
        trend_line: [],
        trend_band: [],
        change_points: [],
        trend_summary: { slope_per_year: 0.03, p_value: 0.004, method: "m" },
        monthly: {
          dates: ["1990-01", "1990-02"],
          raw: [-5.5, null],
          climatology: [-5, -4],
          anomaly: [-0.5, null],
          climatology_by_month: [-5, -4, 0, 5, 10, 15, 18, 17, 12, 6, 0, -4],
          fitted: [-0.4, -0.39],
        },
      },
    },
    provenance: null,
    insight: null,
    analysis_version: 2,
    temporal_basis: "monthly_anomaly",
    trend_details: {
      basis: "monthly_anomaly",
      basis_reason: "Monthly values with the average seasonal cycle removed were tested.",
      seasonal_sd_ratio: 1.4,
      n_points: 372,
      n_years: 31,
      start_year: 1990,
      end_year: 2020,
      sen_slope_per_year: 0.03,
      slope_per_decade: 0.3,
      sen_ci_lower: 0.01,
      sen_ci_upper: 0.05,
      mk_p_value: 0.004,
      mk_variant: "lag1_variance_corrected",
      mk_p_value_original: 0.0001,
      mk_p_value_prewhitened: 0.003,
      seasonal_mk_p_value: 0.002,
      ols_slope_per_year: 0.028,
      ols_t: 3.1,
      ols_p_value: 0.009,
      ols_p_value_naive: 0.0004,
      ols_ci_lower: 0.008,
      ols_ci_upper: 0.048,
      lag1: 0.4,
      n_eff: 160,
      low_n_eff: false,
      std_dev: 0.5,
      residual_std: 0.8,
    },
    detectability: { method: "weatherhead_1998", years_needed: 22, years_available: 31, detectable_now: true, projected_year: null },
    seasonal_trends: [],
    ...overrides,
  };
}

test("the finding tour reads its numbers from the finding and visits the monthly views", () => {
  const steps = findingTour(finding(), "Intro.");
  assert.equal(steps[0].target, "tiles");
  assert.match(steps[0].text, /\+0\.300 degC per decade/);
  assert.match(steps[0].text, /p = 0\.0040/);
  assert.deepEqual(
    steps.filter((s) => s.view).map((s) => s.view),
    ["monthly", "cycle", "anomaly", "annual"],
  );
  assert.ok(steps.some((s) => s.target === "evidence" && /160 independent ones|about 160/.test(s.text)));
  assert.equal(steps.at(-1)?.target, "skeptic");
});

test("a version-1 finding gets a shorter tour without the monthly views", () => {
  const f = finding({ trend_details: null, detectability: null });
  f.visualizations.timeseries = { ...f.visualizations.timeseries!, monthly: undefined };
  const steps = findingTour(f, "Intro.");
  assert.ok(steps.every((s) => s.target !== "evidence"));
  assert.ok(steps.every((s) => s.view === undefined || s.view === "annual"));
});

test("the scan tour reports how many results survive the multiple-testing correction", () => {
  const r = (code: string, significant: boolean): ScanResult => ({
    variable_code: code, name: code, units: "u", definition: "", start_year: 1990, end_year: 2020,
    slope_per_decade: 1, sen_ci_per_decade: [0.5, 1.5], total_change: 3, effect_size: 1, p_value: 0.001,
    q_value: significant ? 0.01 : 0.2, significant, basis: "annual", sampling: "area_mean",
  });
  const steps = scanTour({ steps: [], region: "Sahel", scan_results: [r("A", true), r("B", false), r("C", true)] });
  assert.match(steps[1].text, /2 remain significant/);
  assert.match(steps[2].text, /^A changed/);
});

test("monthly CSV keeps gaps empty and includes the fitted trend", () => {
  const csv = findingToMonthlyCsv(finding());
  assert.equal(
    csv,
    "month,T2M,normal_for_month,anomaly,fitted_trend_on_anomaly\n1990-01,-5.5,-5,-0.5,-0.4\n1990-02,,-4,,-0.39\n",
  );
  const noMonthly = finding();
  noMonthly.visualizations.timeseries = { ...noMonthly.visualizations.timeseries!, monthly: undefined };
  assert.equal(findingToMonthlyCsv(noMonthly), null);
});

test("every glossary entry has a term and a short definition", () => {
  for (const [key, e] of Object.entries(GLOSSARY)) {
    assert.ok(e.term.length > 0, key);
    assert.ok(e.short.length > 20 && e.short.length < 260, `${key} definition length`);
  }
});
