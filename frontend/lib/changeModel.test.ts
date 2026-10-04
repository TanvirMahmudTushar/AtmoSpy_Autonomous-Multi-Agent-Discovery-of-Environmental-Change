import { test } from "node:test";
import assert from "node:assert/strict";

import {
  DIAL_MAX_TILT,
  deriveChange,
  dialTilt,
  effectBucket,
  formatQuantity,
  interpolate,
  levelFor,
  sampleStd,
  summaryChange,
  watchVerdict,
} from "./changeModel.ts";
import { variableMeta } from "./variableMeta.ts";
import type { FindingDetail, FindingSummary } from "./types";

const close = (a: number, b: number, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} !~ ${b}`);

// 2000..2019, value = 10 + 0.5*i plus a fixed +/-0.5 wobble so the series has spread.
function series(slope: number, wobble = 0.5) {
  const points = Array.from({ length: 20 }, (_, i) => ({
    year: 2000 + i,
    value: 10 + slope * i + (i % 2 === 0 ? wobble : -wobble),
  }));
  const trend_line = Array.from({ length: 20 }, (_, i) => ({ year: 2000 + i, fitted: 10 + slope * i }));
  return { points, trend_line };
}

function finding(overrides: Partial<FindingDetail> = {}, slope = 0.5, wobble = 0.5): FindingDetail {
  const { points, trend_line } = series(slope, wobble);
  const total = slope * 19;
  return {
    id: "f1",
    title: "T",
    variable_code: "T2M",
    variable_name: "Temperature at 2 Meters",
    region_code: "bangladesh",
    region_name: "Bangladesh",
    period_start: "2000-01-01",
    period_end: "2019-12-31",
    trend_per_year: slope,
    trend_units: "degC/year",
    total_change: total,
    percent_change: 10,
    effect_size: null,
    p_value: 0.001,
    significance_classification: "statistically_significant",
    concern: "none",
    discovery_score: null,
    created_at: "2026-01-01T00:00:00Z",
    what: "Temperature at 2 Meters (degC)",
    where: "Bangladesh",
    statistical_method: "mk",
    confidence_interval: { lower: slope - 0.1, upper: slope + 0.1, confidence: 0.95 },
    importance_note: "",
    data_quality: {},
    spatial_summary: null,
    related_variables: null,
    robustness: null,
    skeptic_review: null,
    interpretation: "",
    limitations: "",
    narrative_source: "template",
    visualizations: {
      timeseries: {
        kind: "timeseries",
        variable_name: "Temperature at 2 Meters",
        units: "degC",
        points,
        trend_line,
        trend_band: [],
        change_points: [{ year: 2010, mean_before: 12, mean_after: 16, shift: 4 }],
        trend_summary: { slope_per_year: slope, p_value: 0.001, method: "mk" },
      },
    },
    provenance: null,
    insight: null,
    ...overrides,
  };
}

test("levelFor: mean sits mid-scale, +/-2 std hits the clamped ends", () => {
  close(levelFor(10, 10, 2), 0.5);
  close(levelFor(14, 10, 2), 0.95); // +2 std would be 1.0, clamped
  close(levelFor(6, 10, 2), 0.05);
  close(levelFor(11, 10, 2), 0.5 + 1 / 8); // +0.5 std
});

test("levelFor: a flat series (std 0) does not divide by zero", () => {
  assert.equal(levelFor(5, 5, 0), 0.5);
});

test("sampleStd uses ddof = 1 like the backend", () => {
  close(sampleStd([1, 2, 3, 4]), Math.sqrt(5 / 3));
  assert.equal(sampleStd([7]), 0);
});

test("interpolate is piecewise linear and clamps at the ends", () => {
  const pts = [
    { year: 2000, y: 0 },
    { year: 2002, y: 10 },
  ];
  close(interpolate(pts, 2001), 5);
  assert.equal(interpolate(pts, 1990), 0);
  assert.equal(interpolate(pts, 2050), 10);
});

test("effectBucket matches the backend's 0.2 / 0.8 cut-offs", () => {
  assert.equal(effectBucket(0.19), "small");
  assert.equal(effectBucket(0.2), "moderate");
  assert.equal(effectBucket(0.79), "moderate");
  assert.equal(effectBucket(0.8), "large");
});

test("deriveChange: a rising series moves the scene up, proportionally to effect size", () => {
  const m = deriveChange(finding())!;
  assert.equal(m.direction, "up");
  assert.equal(m.span, 19);
  close(m.delta, 0.5 * 19);
  assert.ok(m.endLevel > m.startLevel);
  // level change = delta / (4 std) unless clamped
  const expected = Math.min(0.95, m.levelAt(2019)) - Math.max(0.05, m.levelAt(2000));
  close(m.endLevel - m.startLevel, expected);
  assert.equal(m.bucket, "large");
});

test("deriveChange: a small effect barely moves the scene, a large one moves it far", () => {
  // Same total wobble (std), very different slopes.
  const small = deriveChange(finding({}, 0.002, 3))!;
  const large = deriveChange(finding({}, 0.5, 0.5))!;
  assert.ok(small.effectSize < 0.2 && small.bucket === "small");
  assert.ok(Math.abs(small.endLevel - small.startLevel) < 0.05);
  assert.ok(Math.abs(large.endLevel - large.startLevel) > 0.4);
});

test("deriveChange prefers the stored effect_size and falls back to |delta|/std", () => {
  const m = finding();
  const computed = deriveChange(m)!.effectSize;
  assert.ok(computed > 0);
  assert.equal(deriveChange({ ...m, effect_size: 0.33 })!.effectSize, 0.33);
});

test("deriveChange: CI is the slope CI scaled by the span; change points carry direction", () => {
  const m = deriveChange(finding())!;
  close(m.deltaCI!.lower, 0.4 * 19);
  close(m.deltaCI!.upper, 0.6 * 19);
  assert.deepEqual(m.changePoints, [{ year: 2010, shift: 4, direction: "up" }]);
});

test("deriveChange: descending series reads 'cooler' and says so when not significant", () => {
  const m = deriveChange(
    finding({ total_change: -3, significance_classification: "not_significant" }, -0.5),
  )!;
  assert.equal(m.direction, "down");
  // The change comes from the fitted trend line (-0.5/yr x 19 yr), which is what total_change is by construction.
  assert.match(m.sentence, /Bangladesh got cooler by 9\.50 °C over 19 years/);
  assert.match(m.sentence, /not statistically significant/);
});

test("deriveChange returns null instead of inventing a scene when there is no series", () => {
  assert.equal(deriveChange(finding({ visualizations: {} })), null);
});

test("formatQuantity never shows a real change as 0.00", () => {
  const meta = variableMeta("T2M", "degC");
  assert.equal(formatQuantity(0.762, meta), "0.76 °C");
  assert.equal(formatQuantity(-0.0004, meta), "0.00040 °C");
  assert.equal(formatQuantity(0.043, variableMeta("GWETROOT", "fraction (0 dry to 1 saturated)")), "0.043 on the 0–1 scale");
});

test("summaryChange: same direction and proportionality as the detail view", () => {
  const f = finding({ effect_size: 1.6 }) as FindingSummary;
  const s = summaryChange(f);
  assert.equal(s.direction, "up");
  close(s.endLevel - s.startLevel, 1.6 / 4);
  const down = summaryChange({ ...f, total_change: -3 });
  assert.ok(down.endLevel < down.startLevel);
  assert.equal(down.sentence, "Cooler by 3.00 °C");
  assert.equal(
    summaryChange({ ...f, variable_code: "GWETROOT", trend_units: "fraction (0 dry to 1 saturated)/year", total_change: -0.02 }).sentence,
    "Drier by 0.020 on the 0–1 scale",
  );
});

test("summaryChange: unknown effect size draws direction only, no fake magnitude", () => {
  const s = summaryChange({ ...(finding() as FindingSummary), effect_size: null });
  assert.equal(s.magnitudeKnown, false);
  assert.equal(s.startLevel, s.endLevel);
  assert.equal(s.direction, "up");
});

test("dialTilt: the steeper check gets the max tilt, sign follows the slope", () => {
  assert.equal(dialTilt(0.4, 0.4), DIAL_MAX_TILT);
  assert.equal(dialTilt(-0.2, 0.4), -DIAL_MAX_TILT / 2);
  assert.equal(dialTilt(0, 0), 0);
});

test("watchVerdict follows the backend's branch order", () => {
  assert.equal(watchVerdict(null, null, 0.2, "not_significant"), "first");
  assert.equal(watchVerdict(0.3, "statistically_significant", -0.1, "not_significant"), "flipped");
  assert.equal(watchVerdict(0.3, "not_significant", 0.35, "statistically_significant"), "newly_significant");
  assert.equal(watchVerdict(0.3, "statistically_significant", 0.28, "not_significant"), "lost_significance");
  assert.equal(watchVerdict(0.3, "statistically_significant", 0.31, "statistically_significant"), "consistent");
});

test("variableMeta: known codes, keyword fallback, and a generic default", () => {
  assert.equal(variableMeta("PRECTOTCORR").scene, "precipitation");
  assert.equal(variableMeta("WEIRD_CODE", "m/s", "Gust Wind Speed").scene, "wind");
  const g = variableMeta("???", "widgets", "Mystery");
  assert.equal(g.scene, "generic");
  assert.equal(g.upWord, "higher");
});
