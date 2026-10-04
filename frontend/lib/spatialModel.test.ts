import { test } from "node:test";
import assert from "node:assert/strict";

import { anomalyFrames, cellKey, divergingFill, gridLayout, niceCeil, totalChangeCells } from "./spatialModel.ts";
import type { SpatialMapChartData, SpatialTimelapseChartData } from "./types";

const close = (a: number, b: number, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} !~ ${b}`);

function frame(cells: Array<[number, number, number]>) {
  return {
    type: "FeatureCollection" as const,
    features: cells.map(([lon, lat, value]) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [lon, lat] as [number, number] },
      properties: { value },
    })),
  };
}

test("anomalyFrames removes the between-cell offset so only change remains", () => {
  // Cell A sits at ~100, cell B at ~0; both rise by 1 per year.
  const years = [2000, 2001, 2002, 2003, 2004, 2005, 2006];
  const frames: SpatialTimelapseChartData["frames"] = {};
  years.forEach((y, i) => {
    frames[String(y)] = frame([
      [90, 20, 100 + i],
      [90.625, 20, 0 + i],
    ]);
  });
  const t: SpatialTimelapseChartData = {
    kind: "spatial_timelapse",
    variable_name: "x",
    units: "u",
    years,
    value_min: 0,
    value_max: 106,
    frames,
  };
  const a = anomalyFrames(t, 5)!;
  // Baseline = mean of first 5 years = base + 2, so year 2000 anomaly is -2 for both cells.
  const [ka, kb] = [cellKey(90, 20), cellKey(90.625, 20)];
  close(a.frames[2000][ka], -2);
  close(a.frames[2000][kb], -2);
  close(a.frames[2006][ka], 4);
  close(a.frames[2006][kb], 4);
  close(a.maxAbs, 4);
  assert.deepEqual(a.baselineYears, [2000, 2001, 2002, 2003, 2004]);
});

test("anomalyFrames: one freak cell-year does not set the colour scale", () => {
  const years = Array.from({ length: 20 }, (_, i) => 2000 + i);
  const frames: SpatialTimelapseChartData["frames"] = {};
  years.forEach((y, i) => {
    // Alternating +/-1 around 10, except one wild year.
    frames[String(y)] = frame([[90, 20, i === 15 ? 60 : 10 + (i % 2 === 0 ? 1 : -1)]]);
  });
  const a = anomalyFrames(
    { kind: "spatial_timelapse", variable_name: "x", units: "u", years, value_min: 0, value_max: 60, frames },
    5,
  )!;
  assert.ok(a.maxAbs > 40, "the outlier is still the true max");
  assert.ok(a.scaleAbs < 3, `scale should ignore the outlier, got ${a.scaleAbs}`);
});

test("anomalyFrames copes with a cell missing some years", () => {
  const t: SpatialTimelapseChartData = {
    kind: "spatial_timelapse",
    variable_name: "x",
    units: "u",
    years: [2000, 2001, 2002],
    value_min: 0,
    value_max: 3,
    frames: {
      "2000": frame([[90, 20, 1]]),
      "2001": frame([]),
      "2002": frame([[90, 20, 3]]),
    },
  };
  const a = anomalyFrames(t, 5)!;
  const k = cellKey(90, 20);
  close(a.frames[2000][k], -1); // baseline = mean(1, 3) = 2
  assert.equal(a.frames[2001][k], undefined);
  close(a.frames[2002][k], 1);
});

test("anomalyFrames returns null for a single-year or empty record", () => {
  const empty: SpatialTimelapseChartData = {
    kind: "spatial_timelapse", variable_name: "x", units: "u", years: [2000], value_min: null, value_max: null, frames: {},
  };
  assert.equal(anomalyFrames(empty), null);
});

test("totalChangeCells scales the per-year slope by the span", () => {
  const map: SpatialMapChartData = {
    kind: "spatial_map",
    variable_name: "x",
    units: "u",
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        geometry: { type: "Point", coordinates: [92.5, 21] },
        properties: { slope_per_year: -0.03, p_value: 0.01, significant: true, direction: "decreasing" },
      },
    ],
  };
  const [c] = totalChangeCells(map, 35);
  close(c.total, -1.05);
  assert.equal(c.significant, true);
});

test("gridLayout keeps cells square-ish in real distance and puts north up", () => {
  const cells = [
    { key: "a", lon: 90, lat: 20 },
    { key: "b", lon: 90.625, lat: 20 },
    { key: "c", lon: 90, lat: 20.5 },
    { key: "d", lon: 90.625, lat: 20.5 },
  ];
  const g = gridLayout(cells, 400);
  assert.ok(g.y(20.5) < g.y(20)); // higher latitude is nearer the top
  assert.ok(g.x(90.625) > g.x(90));
  // 0.625 deg of lon at ~20 N is shorter than 0.625 deg of lat, by cos(lat).
  close(g.cellW / g.cellH, (0.625 * Math.cos((20.25 * Math.PI) / 180)) / 0.5, 1e-6);
});

test("niceCeil rounds up to 1-2-5 steps", () => {
  assert.equal(niceCeil(0.73), 1);
  assert.equal(niceCeil(1.4), 2);
  assert.equal(niceCeil(3.2), 5);
  assert.equal(niceCeil(5.1), 10);
  assert.equal(niceCeil(0.031), 0.05);
});

test("divergingFill is symmetric, saturates at maxAbs, and is neutral at zero", () => {
  assert.match(divergingFill(2, 2), /diverge-high\) 100%/);
  assert.match(divergingFill(-1, 2), /diverge-low\) 50%/);
  assert.match(divergingFill(0, 2), / 0%/);
  assert.match(divergingFill(99, 2), /100%/); // clamped
});
