/**
 * Watchable demos: real investigations frozen as JSON by
 * backend/scripts/export_demos.py (frontend/public/demos/*.json) and replayed
 * with a captioned tour. Captions read every number from the frozen finding,
 * so they can never disagree with the analysis.
 */
import { formatPValue, formatSigFig } from "./utils.ts";
import type { FindingDetail, InvestigationStep, ScanResult } from "./types";

export interface DemoIndexEntry {
  id: string;
  kind: "investigation" | "scan" | "pair";
  title: string;
  summary: string;
  generated_at: string;
}

export interface DemoPart {
  steps: InvestigationStep[];
  finding?: FindingDetail;
  scan_results?: ScanResult[];
  region?: string;
}

export interface Demo extends DemoIndexEntry {
  parts: DemoPart[];
}

export interface TourStep {
  /** data-tour anchor to scroll to and highlight */
  target: string;
  /** optional chart view to switch to first (TimeSeriesChart data-tour-view) */
  view?: "monthly" | "cycle" | "anomaly" | "annual";
  title: string;
  text: string;
}

const signed = (n: number) => `${n > 0 ? "+" : ""}${formatSigFig(n)}`;
const units = (f: FindingDetail) => f.trend_units.replace(/\/year$/, "");

/** The standard walk through one finding. */
export function findingTour(f: FindingDetail, intro: string): TourStep[] {
  const t = f.trend_details;
  const sig = f.significance_classification === "statistically_significant";
  const d = f.detectability;
  const s = f.spatial_summary;
  const steps: TourStep[] = [
    {
      target: "tiles",
      title: "The four questions",
      text:
        `${intro} The case file answers four questions. What: ${f.what}. Where: ${f.where}. ` +
        (t
          ? `How much: ${signed(t.slope_per_decade)} ${units(f)} per decade. Significant: ${sig ? "yes" : "not yet"} (${formatPValue(f.p_value)}).`
          : `Significant: ${sig ? "yes" : "no"} (${formatPValue(f.p_value)}).`),
    },
  ];
  if (f.visualizations.timeseries?.monthly) {
    steps.push(
      {
        target: "timeseries",
        view: "monthly",
        title: "Start with the raw monthly data",
        text: "Every month's average. The big regular wave is the seasonal cycle. It is far larger than any long-term change, so a trend is hard to see here.",
      },
      {
        target: "timeseries",
        view: "cycle",
        title: "The normal year",
        text: "Averaging each calendar month over the whole record gives the seasonal cycle, or climatology: what a normal year looks like.",
      },
      {
        target: "timeseries",
        view: "anomaly",
        title: "Remove the seasons",
        text: "Subtract each month's normal value and what's left are anomalies: how unusual each month was. Slow trends are much easier to see once the seasonal wave is gone.",
      },
    );
  }
  steps.push({
    target: "timeseries",
    view: f.visualizations.timeseries?.monthly ? "annual" : undefined,
    title: "Yearly averages and the trend line",
    text: t
      ? `${t.basis_reason} The red line is Sen's slope and the shaded band its 95% confidence range.`
      : "One average per year, with Sen's slope as the trend line.",
  });
  if (t) {
    steps.push({
      target: "evidence",
      title: "How sure are we?",
      text:
        `Two independent tests agree${sig === t.ols_p_value < 0.05 ? "" : " only partly"}: Mann-Kendall gives ${formatPValue(t.mk_p_value)} ` +
        `and the t-test ${formatPValue(t.ols_p_value)}. Both allow for neighbouring values resembling each other ` +
        `(${t.n_points} values are worth about ${Math.round(t.n_eff)} independent ones).` +
        (d?.years_needed != null && !sig
          ? ` A trend this size typically needs about ${Math.round(d.years_needed)} years of data to stand out; this record has ${d.years_available}.`
          : ""),
    });
  }
  if (s && s.total_cells > 0) {
    steps.push({
      target: "map",
      title: "Where is it changing?",
      text:
        `Each grid cell was tested on its own, with a correction for testing ${s.total_cells} cells at once. ` +
        `${s.increasing_cells} cells show a significant rise and ${s.decreasing_cells} a significant fall.` +
        (s.has_opposite_regional_trends ? " The same variable is moving in opposite directions in different parts of the region." : ""),
    });
  }
  if (f.skeptic_review) {
    steps.push({
      target: "skeptic",
      title: "Argue against it",
      text:
        f.skeptic_review.points.length > 0
          ? `A good detective doubts their own case. The skeptic raised ${f.skeptic_review.points.length} point(s), such as: "${f.skeptic_review.points[0]}"`
          : "A good detective doubts their own case. Here the skeptic found no major objection.",
    });
  }
  return steps;
}

export function scanTour(part: DemoPart): TourStep[] {
  const results = part.scan_results ?? [];
  const sig = results.filter((r) => r.significant);
  const top = sig[0];
  return [
    {
      target: "scan",
      title: "Every variable, one test",
      text: `The detective tested ${results.length} variables over ${part.region ?? "the region"} with the same trend test, on the region's area-weighted average.`,
    },
    {
      target: "scan",
      title: "Correcting for many tests",
      text: `Test ${results.length} things at once and about ${Math.max(1, Math.round(results.length * 0.05))} may look significant by luck. After the false-discovery-rate correction, ${sig.length} remain significant.`,
    },
    {
      target: "scan",
      title: "The strongest signal",
      text: top
        ? `${top.name} changed by ${signed(top.slope_per_decade)} ${top.units} per decade (${formatPValue(top.p_value)}). Together the significant variables tell one story; click a row in the live tool to investigate any of them in depth.`
        : "Nothing passed the correction: no variable shows a trend we can be confident in here.",
    },
  ];
}

export function pairTour(demo: Demo): TourStep[] {
  return demo.parts.flatMap((p, i) => {
    const f = p.finding;
    const t = f?.trend_details;
    if (!f || !t) return [];
    return [{
      target: `part-${i}`,
      title: f.title,
      text: `${signed(t.slope_per_decade)} ${units(f)} per decade (${formatPValue(f.p_value)}, ${f.significance_classification === "statistically_significant" ? "significant" : "not significant"}).`,
    }];
  });
}

/** Demo-specific opening line, read from the frozen finding where it uses numbers. */
export function demoIntro(demo: Demo): string {
  const f = demo.parts[0]?.finding;
  switch (demo.id) {
    case "hidden-by-seasons":
      return "In Arctic Alaska the gap between winter and summer is enormous, yet a steady warming hides underneath.";
    case "not-significant-yet":
      return f?.detectability?.projected_year
        ? `Averaged over the whole plateau, the change isn't significant yet; at this rate it could become detectable around ${f.detectability.projected_year}.`
        : "Averaged over the whole plateau, the change isn't significant yet.";
    case "vanishing-water":
      return "GRACE satellites weigh the water stored in the ground by measuring tiny changes in Earth's gravity.";
    default:
      return demo.summary;
  }
}
