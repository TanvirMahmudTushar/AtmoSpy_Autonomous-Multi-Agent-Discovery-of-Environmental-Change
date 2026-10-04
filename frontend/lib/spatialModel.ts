// Geometry and value maths for the SVG spatial change map. Pure functions so
// the maths is testable with plain `node --test`; the component only draws.

import type { SpatialMapChartData, SpatialTimelapseChartData } from "./types";
import { clamp } from "./changeModel.ts";
import { cellSpacing } from "../components/charts/gridGeo.ts";

export interface Cell {
  key: string;
  lon: number;
  lat: number;
}

export interface TotalChangeCell extends Cell {
  slopePerYear: number;
  pValue: number;
  significant: boolean;
  /** slope x span: how far this cell moved over the whole record, in the variable's units. */
  total: number;
}

export function cellKey(lon: number, lat: number): string {
  return `${lon.toFixed(4)},${lat.toFixed(4)}`;
}

export function totalChangeCells(map: SpatialMapChartData, spanYears: number): TotalChangeCell[] {
  return map.features.map((f) => {
    const [lon, lat] = f.geometry.coordinates;
    const slope = f.properties.slope_per_year;
    return {
      key: cellKey(lon, lat),
      lon,
      lat,
      slopePerYear: slope,
      pValue: f.properties.p_value,
      significant: f.properties.significant,
      total: slope * spanYears,
    };
  });
}

export interface GridLayout {
  viewW: number;
  viewH: number;
  cellW: number;
  cellH: number;
  x: (lon: number) => number;
  y: (lat: number) => number;
  lonMin: number;
  lonMax: number;
  latMin: number;
  latMax: number;
}

/**
 * Equirectangular layout with longitude compressed by cos(mid-latitude), so
 * the region keeps roughly its real shape. Latitude runs bottom-to-top.
 */
export function gridLayout(cells: Cell[], targetWidth = 640): GridLayout {
  const lons = cells.map((c) => c.lon);
  const lats = cells.map((c) => c.lat);
  const { dLon, dLat } = cellSpacing(lons, lats);
  const lonMin = Math.min(...lons) - dLon / 2;
  const lonMax = Math.max(...lons) + dLon / 2;
  const latMin = Math.min(...lats) - dLat / 2;
  const latMax = Math.max(...lats) + dLat / 2;

  const midLat = (latMin + latMax) / 2;
  const lonScale = Math.max(0.2, Math.cos((midLat * Math.PI) / 180));
  const widthDeg = (lonMax - lonMin) * lonScale;
  const heightDeg = latMax - latMin;
  const k = targetWidth / widthDeg;

  return {
    viewW: targetWidth,
    viewH: heightDeg * k,
    cellW: dLon * lonScale * k,
    cellH: dLat * k,
    x: (lon) => (lon - lonMin) * lonScale * k,
    y: (lat) => (latMax - lat) * k,
    lonMin,
    lonMax,
    latMin,
    latMax,
  };
}

export interface AnomalySeries {
  years: number[];
  cells: Cell[];
  /** year -> cell key -> (value - that cell's own baseline). */
  frames: Record<number, Record<string, number>>;
  /** Largest |anomaly| anywhere. */
  maxAbs: number;
  /**
   * 95th-percentile |anomaly| — what the symmetric colour scale saturates at.
   * One freak cell-year would otherwise set the scale and wash out everything
   * else; values beyond it just saturate.
   */
  scaleAbs: number;
  baselineYears: number[];
}

/** Nearest-rank quantile of an ascending-sorted list. */
export function quantileSorted(sorted: number[], q: number): number {
  if (sorted.length === 0) return 0;
  return sorted[Math.min(sorted.length - 1, Math.max(0, Math.ceil(q * sorted.length) - 1))];
}

/**
 * Re-express the raw per-year cell values as a change from each cell's own
 * baseline (its mean over the first `baselineCount` years it has data). Raw
 * values are dominated by how cells differ from each other, so scrubbing them
 * barely moves; anomalies remove that and show only what changed.
 */
export function anomalyFrames(t: SpatialTimelapseChartData, baselineCount = 5): AnomalySeries | null {
  const years = [...t.years].sort((a, b) => a - b);
  if (years.length < 2) return null;

  const byCell = new Map<string, { lon: number; lat: number; values: Map<number, number> }>();
  for (const year of years) {
    const frame = t.frames[String(year)];
    if (!frame) continue;
    for (const f of frame.features) {
      const [lon, lat] = f.geometry.coordinates;
      const key = cellKey(lon, lat);
      let entry = byCell.get(key);
      if (!entry) {
        entry = { lon, lat, values: new Map() };
        byCell.set(key, entry);
      }
      entry.values.set(year, f.properties.value);
    }
  }
  if (byCell.size === 0) return null;

  const baselineYears = years.slice(0, Math.min(baselineCount, years.length));
  const frames: Record<number, Record<string, number>> = {};
  for (const year of years) frames[year] = {};
  const absAll: number[] = [];

  for (const [key, entry] of byCell) {
    const base = years.filter((y) => entry.values.has(y)).slice(0, baselineCount).map((y) => entry.values.get(y) as number);
    if (base.length === 0) continue;
    const baseline = base.reduce((a, b) => a + b, 0) / base.length;
    for (const [year, value] of entry.values) {
      const anomaly = value - baseline;
      frames[year][key] = anomaly;
      absAll.push(Math.abs(anomaly));
    }
  }

  absAll.sort((a, b) => a - b);
  const maxAbs = absAll.length ? absAll[absAll.length - 1] : 0;
  const scaleAbs = quantileSorted(absAll, 0.95);

  return {
    years,
    cells: [...byCell].map(([key, e]) => ({ key, lon: e.lon, lat: e.lat })),
    frames,
    maxAbs: maxAbs > 0 ? maxAbs : 1e-9,
    scaleAbs: scaleAbs > 0 ? scaleAbs : 1e-9,
    baselineYears,
  };
}

/** Round up to a 1-2-5 step so a legend reads "±1.5" instead of "±1.4734". */
export function niceCeil(x: number): number {
  if (!(x > 0)) return 1;
  const exp = Math.floor(Math.log10(x));
  const base = 10 ** exp;
  const f = x / base;
  const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
  return nice * base;
}

/**
 * Fill for a signed value on a symmetric diverging scale. Uses the theme's
 * --chart-diverge-* tokens via color-mix, so it follows light/dark for free.
 */
export function divergingFill(value: number, maxAbs: number): string {
  const t = clamp(Math.abs(value) / maxAbs, 0, 1);
  const pct = Math.round(t * 100);
  const end = value >= 0 ? "var(--chart-diverge-high)" : "var(--chart-diverge-low)";
  return `color-mix(in srgb, ${end} ${pct}%, var(--chart-diverge-mid))`;
}
