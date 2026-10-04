// The single place that turns a finding's computed numbers into "how far does
// the picture move". Every scene, glyph and dial renders from the `level`
// values produced here, so all views agree and none of them invents a number.
//
// Level scale: level(v) = 0.5 + (v - mean) / (4 * std), clamped to
// [LEVEL_MIN, LEVEL_MAX]. The scene's full range therefore spans +/-2 typical
// year-to-year swings, which makes a scene's movement proportional to the
// report's effect size (|total change| / std. dev.) rather than to the raw
// units — a 1 degC shift is dramatic for a stable series and invisible for a
// noisy one, and the picture says so.
//
// Dependency-free on purpose (relative imports with explicit extensions, type
// imports only) so `node --test` can exercise it without a bundler.

import type { FindingDetail, FindingSummary } from "./types";
import { variableMeta, type VariableMeta } from "./variableMeta.ts";

export const LEVEL_MIN = 0.05;
export const LEVEL_MAX = 0.95;
/** Same cut-offs as backend/app/analysis/significance.py::importance_note. */
export const EFFECT_SMALL = 0.2;
export const EFFECT_LARGE = 0.8;
/** How many typical yearly swings the whole scene range covers, end to end. */
export const SCENE_SPAN_STDS = 4;

export type Direction = "up" | "down" | "flat";
export type EffectBucket = "small" | "moderate" | "large";

export function clamp(x: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, x));
}

export function directionOf(delta: number): Direction {
  if (delta > 0) return "up";
  if (delta < 0) return "down";
  return "flat";
}

export function effectBucket(effect: number): EffectBucket {
  if (effect < EFFECT_SMALL) return "small";
  if (effect < EFFECT_LARGE) return "moderate";
  return "large";
}

/** Scene level for an absolute value; a flat series (std 0) sits mid-scale. */
export function levelFor(value: number, mean: number, std: number): number {
  if (!(std > 0)) return 0.5;
  return clamp(0.5 + (value - mean) / (SCENE_SPAN_STDS * std), LEVEL_MIN, LEVEL_MAX);
}

export function mean(values: number[]): number {
  return values.reduce((a, b) => a + b, 0) / values.length;
}

/** Sample standard deviation (ddof = 1), matching analysis/trend.py. */
export function sampleStd(values: number[]): number {
  if (values.length < 2) return 0;
  const m = mean(values);
  return Math.sqrt(values.reduce((a, v) => a + (v - m) ** 2, 0) / (values.length - 1));
}

/** Piecewise-linear lookup over an ascending [{year, y}] list, clamped at the ends. */
export function interpolate(points: Array<{ year: number; y: number }>, year: number): number {
  if (points.length === 0) return NaN;
  if (year <= points[0].year) return points[0].y;
  const last = points[points.length - 1];
  if (year >= last.year) return last.y;
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1];
    const b = points[i];
    if (year <= b.year) {
      const t = (year - a.year) / (b.year - a.year);
      return a.y + t * (b.y - a.y);
    }
  }
  return last.y;
}

/** "0.76 °C", "0.043 on the 0–1 scale" — a value with its units, at a sensible precision. */
export function formatQuantity(value: number, meta: VariableMeta): string {
  let text = Math.abs(value).toFixed(meta.decimals);
  // A tiny but non-zero change must not read as "0.00".
  if (Number(text) === 0 && value !== 0) text = Math.abs(value).toPrecision(2);
  if (!meta.unitLabel) return text;
  if (meta.unitLabel === "(0–1)") return `${text} on the 0–1 scale`;
  return `${text} ${meta.unitLabel}`;
}

function swingPhrase(effect: number): string {
  if (effect < 0.1) return "well under a tenth of a typical year-to-year swing";
  return `${effect.toFixed(1)}× a typical year-to-year swing`;
}

export interface ChangePoint {
  year: number;
  shift: number;
  direction: Direction;
}

export interface ChangeModel {
  meta: VariableMeta;
  direction: Direction;
  significant: boolean;
  effectSize: number;
  bucket: EffectBucket;
  mean: number;
  std: number;
  startYear: number;
  endYear: number;
  span: number;
  startValue: number;
  endValue: number;
  /** end fitted value - start fitted value (the Sen-slope change). */
  delta: number;
  /** total-change interval, from the slope CI x span; null when there is no CI. */
  deltaCI: { lower: number; upper: number } | null;
  startLevel: number;
  endLevel: number;
  changePoints: ChangePoint[];
  /** Trend-line level at a year (clamped to the record). */
  levelAt: (year: number) => number;
  /** Fitted (trend-line) value at a year. */
  valueAt: (year: number) => number;
  /** Observed annual value at a year, or null if that year is absent. */
  observedAt: (year: number) => number | null;
  sentence: string;
  ariaLabel: string;
}

/**
 * Derive the scene model from a full finding. Returns null when the finding
 * carries no annual series to draw from (older or partial findings); callers
 * simply omit the scene rather than draw something made up.
 */
export function deriveChange(finding: FindingDetail): ChangeModel | null {
  const ts = finding.visualizations?.timeseries;
  if (!ts || ts.points.length < 2 || ts.trend_line.length < 2) return null;

  const meta = variableMeta(finding.variable_code, ts.units, finding.variable_name);
  const values = ts.points.map((p) => p.value);
  const m = mean(values);
  const std = sampleStd(values);

  const fitted = ts.trend_line.map((p) => ({ year: p.year, y: p.fitted }));
  const observed = new Map(ts.points.map((p) => [p.year, p.value]));
  const startYear = fitted[0].year;
  const endYear = fitted[fitted.length - 1].year;
  const span = endYear - startYear;
  const startValue = fitted[0].y;
  const endValue = fitted[fitted.length - 1].y;
  const delta = endValue - startValue;

  const effect = finding.effect_size ?? (std > 0 ? Math.abs(delta) / std : 0);
  const direction = directionOf(delta);
  const significant = finding.significance_classification === "statistically_significant";

  const ci = finding.confidence_interval;
  const deltaCI = ci ? { lower: ci.lower * span, upper: ci.upper * span } : null;

  const changePoints: ChangePoint[] = (ts.change_points ?? []).map((c) => ({
    year: c.year,
    shift: c.shift,
    direction: directionOf(c.shift),
  }));

  const levelAt = (year: number) => levelFor(interpolate(fitted, year), m, std);
  const valueAt = (year: number) => interpolate(fitted, year);

  const word = direction === "up" ? meta.upWord : direction === "down" ? meta.downWord : "unchanged";
  const sentence =
    direction === "flat"
      ? `${finding.where} shows no net change in ${finding.variable_name.toLowerCase()} over ${span} years.`
      : `${finding.where} got ${word} by ${formatQuantity(delta, meta)} over ${span} years — ${swingPhrase(effect)}` +
        (significant ? "." : ", but the trend is not statistically significant.");

  return {
    meta,
    direction,
    significant,
    effectSize: effect,
    bucket: effectBucket(effect),
    mean: m,
    std,
    startYear,
    endYear,
    span,
    startValue,
    endValue,
    delta,
    deltaCI,
    startLevel: levelAt(startYear),
    endLevel: levelAt(endYear),
    changePoints,
    levelAt,
    valueAt,
    observedAt: (year) => observed.get(year) ?? null,
    sentence,
    ariaLabel: `${finding.variable_name} in ${finding.where}, ${startYear} to ${endYear}. ${sentence}`,
  };
}

export interface SummaryChange {
  meta: VariableMeta;
  direction: Direction;
  significant: boolean;
  /** false when the finding predates effect_size and could not be backfilled — draw direction only. */
  magnitudeKnown: boolean;
  effectSize: number;
  bucket: EffectBucket;
  startLevel: number;
  endLevel: number;
  sentence: string;
}

/**
 * The same Then/Now pair for views that only have the summary row (Discover
 * cards, globe). A fitted trend line passes through roughly the series mean at
 * its midpoint, so its ends sit at mean -/+ delta/2, which on the level scale
 * is 0.5 -/+ effect/8 — this reproduces what deriveChange shows, to within the
 * trend line's offset from the mean.
 */
export function summaryChange(f: FindingSummary): SummaryChange {
  // trend_units is "<units>/year"; the change itself is quoted in plain units.
  const meta = variableMeta(f.variable_code, f.trend_units.replace(/\/year$/, ""), f.variable_name);
  const direction = directionOf(f.total_change);
  const significant = f.significance_classification === "statistically_significant";
  const known = f.effect_size !== null && f.effect_size !== undefined;
  const effect = known ? (f.effect_size as number) : 0;

  const half = known ? effect / 8 : 0;
  const sign = direction === "down" ? -1 : direction === "up" ? 1 : 0;
  const startLevel = clamp(0.5 - sign * half, LEVEL_MIN, LEVEL_MAX);
  const endLevel = clamp(0.5 + sign * half, LEVEL_MIN, LEVEL_MAX);

  const word = direction === "up" ? meta.upWord : direction === "down" ? meta.downWord : "unchanged";
  const phrase = `${word} by ${formatQuantity(f.total_change, meta)}`;
  const sentence = direction === "flat" ? "No net change" : phrase.charAt(0).toUpperCase() + phrase.slice(1);

  return {
    meta,
    direction,
    significant,
    magnitudeKnown: known,
    effectSize: effect,
    bucket: effectBucket(effect),
    startLevel,
    endLevel,
    sentence,
  };
}

export const DIAL_MAX_TILT = 35;

/** Slope-tilt in degrees for a trend dial: the steeper of the two checks gets DIAL_MAX_TILT. */
export function dialTilt(slope: number, reference: number): number {
  if (!(reference > 0)) return 0;
  return clamp(slope / reference, -1, 1) * DIAL_MAX_TILT;
}

export type WatchVerdict = "first" | "flipped" | "newly_significant" | "lost_significance" | "consistent";

/** Mirrors backend watch_runner._build_note's branch order, without its prose. */
export function watchVerdict(
  prevTrend: number | null,
  prevSig: string | null,
  lastTrend: number | null,
  lastSig: string | null,
): WatchVerdict {
  if (prevTrend === null || lastTrend === null) return "first";
  if (prevTrend >= 0 !== lastTrend >= 0) return "flipped";
  if (prevSig !== "statistically_significant" && lastSig === "statistically_significant") return "newly_significant";
  if (prevSig === "statistically_significant" && lastSig !== "statistically_significant") return "lost_significance";
  return "consistent";
}
