"use client";

import { useId, useMemo, useState } from "react";
import { PixelButton } from "@/components/ui/button";
import { formatQuantity } from "@/lib/changeModel";
import {
  anomalyFrames,
  divergingFill,
  gridLayout,
  niceCeil,
  totalChangeCells,
  type Cell,
} from "@/lib/spatialModel";
import type { SpatialMapChartData, SpatialSummary, SpatialTimelapseChartData } from "@/lib/types";
import { variableMeta } from "@/lib/variableMeta";
import { formatPValue } from "@/lib/utils";
import { usePlayer } from "./usePlayer";

const W = 640;
const MAX_H = 440;
const PLAY_SECONDS = 8;

/** Round tick positions inside [min, max], about `n` of them, on a 1-2-5 step. */
function ticks(min: number, max: number, n = 4): number[] {
  const step = niceCeil((max - min) / n);
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(Number(v.toFixed(4)));
  return out;
}

const lat = (v: number) => `${Math.abs(v)}°${v >= 0 ? "N" : "S"}`;
const lon = (v: number) => `${Math.abs(v)}°${v >= 0 ? "E" : "W"}`;

function Legend({ maxAbs, unit, decimals, caption }: { maxAbs: number; unit: string; decimals: number; caption: string }) {
  const id = useId().replace(/:/g, "");
  return (
    <div className="mt-3">
      <svg viewBox="0 0 220 30" className="w-full max-w-[320px]" role="img" aria-label={`Colour scale from −${maxAbs} to +${maxAbs} ${unit}`}>
        <defs>
          <linearGradient id={id} x1="0" x2="1">
            <stop offset="0" style={{ stopColor: "var(--chart-diverge-low)" }} />
            <stop offset="0.5" style={{ stopColor: "var(--chart-diverge-mid)" }} />
            <stop offset="1" style={{ stopColor: "var(--chart-diverge-high)" }} />
          </linearGradient>
        </defs>
        <rect x={10} y={2} width={200} height={10} fill={`url(#${id})`} stroke="var(--app-border)" strokeWidth={0.5} />
        <text x={10} y={25} fontSize={8} textAnchor="start" fill="var(--app-ink-soft)">{`−${maxAbs.toFixed(decimals)}`}</text>
        <text x={110} y={25} fontSize={8} textAnchor="middle" fill="var(--app-ink-soft)">0</text>
        <text x={210} y={25} fontSize={8} textAnchor="end" fill="var(--app-ink-soft)">{`+${maxAbs.toFixed(decimals)} ${unit}`}</text>
      </svg>
      <p className="font-mono-data text-[11px] text-[var(--app-muted)]">{caption}</p>
    </div>
  );
}

function DirectionSplitBar({ summary }: { summary: SpatialSummary }) {
  const total = summary.total_cells || 1;
  const rest = Math.max(0, summary.total_cells - summary.increasing_cells - summary.decreasing_cells);
  const seg = (n: number) => `${(n / total) * 100}%`;
  return (
    <div className="mt-4">
      <div className="font-display text-[8px] text-[var(--app-muted)]">Which way each grid cell moved</div>
      <div
        className="mt-1 flex h-4 w-full overflow-hidden border-2 border-[var(--app-border)]"
        role="img"
        aria-label={`${summary.decreasing_cells} cells significantly decreasing, ${summary.increasing_cells} increasing, ${rest} with no clear trend`}
      >
        <div style={{ width: seg(summary.decreasing_cells), background: "var(--chart-diverge-low)" }} />
        <div style={{ width: seg(rest), background: "repeating-linear-gradient(45deg, var(--app-panel-alt) 0 3px, var(--app-muted) 3px 4px)" }} />
        <div style={{ width: seg(summary.increasing_cells), background: "var(--chart-diverge-high)" }} />
      </div>
      <div className="mt-1 flex justify-between font-mono-data text-[11px] text-[var(--app-ink-soft)]">
        <span>{summary.decreasing_cells} cells decreasing</span>
        <span>{rest} no clear trend</span>
        <span>{summary.increasing_cells} increasing</span>
      </div>
    </div>
  );
}

export function SpatialChangeMap({
  map,
  timelapse,
  summary,
  spanYears,
  variableCode,
  variableName,
}: {
  map: SpatialMapChartData;
  timelapse?: SpatialTimelapseChartData;
  summary: SpatialSummary | null;
  /** end year - start year: the span `total_change` is measured over. */
  spanYears: number;
  variableCode: string;
  variableName: string;
}) {
  const meta = variableMeta(variableCode, map.units, variableName);
  const patternId = useId().replace(/:/g, "");
  const cells = useMemo(() => totalChangeCells(map, spanYears), [map, spanYears]);
  const anomaly = useMemo(() => (timelapse ? anomalyFrames(timelapse) : null), [timelapse]);
  // Draw at natural size (1 unit = 1 px) so axis labels stay legible; a tall
  // region gets a narrower canvas instead of being shrunk to fit.
  const layout = useMemo(() => {
    const wide = gridLayout(cells as Cell[], W);
    return wide.viewH > MAX_H ? gridLayout(cells as Cell[], (W * MAX_H) / wide.viewH) : wide;
  }, [cells]);

  const [mode, setMode] = useState<"total" | "years">("total");
  const first = anomaly?.years[0] ?? 0;
  const last = anomaly?.years[anomaly.years.length - 1] ?? 0;
  const player = usePlayer(first, last, PLAY_SECONDS);
  const [hover, setHover] = useState<string | null>(null);

  if (cells.length === 0) return null;

  const maxTotal = niceCeil(Math.max(...cells.map((c) => Math.abs(c.total))));
  const maxAnomaly = anomaly ? niceCeil(anomaly.scaleAbs) : 1;
  const showYears = mode === "years" && anomaly !== null;
  const shownYear = Math.round(player.year);
  const frame = showYears ? anomaly.frames[shownYear] ?? {} : {};
  const hovered = hover ? cells.find((c) => c.key === hover) : undefined;
  const unit = meta.unitLabel === "(0–1)" ? "" : meta.unitLabel;
  const decimals = meta.decimals;

  const marginL = 40;
  const marginB = 22;
  const latTicks = ticks(layout.latMin, layout.latMax, 4);
  const lonTicks = ticks(layout.lonMin, layout.lonMax, 4);
  const vbW = layout.viewW + marginL + 10;
  const vbH = layout.viewH + marginB + 6;

  const tab = (id: "total" | "years", label: string, disabled = false) => (
    <button
      type="button"
      role="tab"
      aria-selected={mode === id}
      disabled={disabled}
      onClick={() => {
        player.pause();
        setMode(id);
      }}
      className={`border-2 px-2.5 py-1 font-display text-[8px] disabled:opacity-40 ${
        mode === id
          ? "border-[var(--app-border)] bg-[var(--app-panel-alt)] text-[var(--app-ink)]"
          : "border-transparent text-[var(--app-muted)] hover:text-[var(--app-ink)]"
      }`}
    >
      {label}
    </button>
  );

  const inc = summary?.increasing_cells ?? cells.filter((c) => c.significant && c.total > 0).length;
  const dec = summary?.decreasing_cells ?? cells.filter((c) => c.significant && c.total < 0).length;
  const aria = `Map of ${cells.length} grid cells: ${dec} significantly decreasing, ${inc} significantly increasing.`;

  return (
    <div>
      <div role="tablist" aria-label="Map view" className="mb-2 flex gap-1">
        {tab("total", "Total change")}
        {tab("years", "Year by year", anomaly === null)}
      </div>

      <svg
        viewBox={`${-marginL} -6 ${vbW} ${vbH}`}
        width={vbW}
        height={vbH}
        className="mx-auto block"
        style={{ maxWidth: "100%", height: "auto" }}
        role="img"
        aria-label={aria}
        shapeRendering="crispEdges"
        onPointerLeave={() => setHover(null)}
      >
        <defs>
          <pattern id={patternId} width={6} height={6} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width={1.6} height={6} fill="var(--app-ink)" opacity={0.4} />
          </pattern>
        </defs>

        <rect x={0} y={0} width={layout.viewW} height={layout.viewH} fill="var(--app-panel-alt)" />

        {showYears
          ? anomaly.cells.map((c) => {
              const v = frame[c.key];
              return (
                <rect
                  key={c.key}
                  x={layout.x(c.lon) - layout.cellW / 2}
                  y={layout.y(c.lat) - layout.cellH / 2}
                  width={layout.cellW + 0.5}
                  height={layout.cellH + 0.5}
                  fill={v === undefined ? "var(--app-panel-alt)" : divergingFill(v, maxAnomaly)}
                />
              );
            })
          : cells.map((c) => {
              const x = layout.x(c.lon) - layout.cellW / 2;
              const y = layout.y(c.lat) - layout.cellH / 2;
              const strength = Math.min(1, Math.abs(c.total) / maxTotal);
              const cx = x + layout.cellW / 2;
              const cy = y + layout.cellH / 2;
              const r = Math.max(2, Math.min(layout.cellW, layout.cellH) * 0.34 * (0.4 + 0.6 * strength));
              const up = c.total >= 0;
              return (
                <g key={c.key} onPointerEnter={() => setHover(c.key)}>
                  <rect x={x} y={y} width={layout.cellW + 0.5} height={layout.cellH + 0.5} fill={divergingFill(c.total, maxTotal)} />
                  {!c.significant && <rect x={x} y={y} width={layout.cellW + 0.5} height={layout.cellH + 0.5} fill={`url(#${patternId})`} />}
                  {c.significant && (
                    <path
                      d={up ? `M${cx} ${cy - r} L${cx + r} ${cy + r} L${cx - r} ${cy + r} Z` : `M${cx} ${cy + r} L${cx + r} ${cy - r} L${cx - r} ${cy - r} Z`}
                      fill="var(--app-ink)"
                      opacity={0.6}
                    />
                  )}
                </g>
              );
            })}

        <rect x={0} y={0} width={layout.viewW} height={layout.viewH} fill="none" stroke="var(--app-border)" strokeWidth={1.5} />

        {latTicks.map((v) => (
          <g key={`lat${v}`}>
            <line x1={-4} x2={0} y1={layout.y(v)} y2={layout.y(v)} stroke="var(--app-border)" />
            <text x={-7} y={layout.y(v) + 3} fontSize={11} textAnchor="end" fill="var(--app-ink-soft)">{lat(v)}</text>
          </g>
        ))}
        {lonTicks.map((v) => (
          <g key={`lon${v}`}>
            <line x1={layout.x(v)} x2={layout.x(v)} y1={layout.viewH} y2={layout.viewH + 4} stroke="var(--app-border)" />
            <text x={layout.x(v)} y={layout.viewH + 16} fontSize={11} textAnchor="middle" fill="var(--app-ink-soft)">{lon(v)}</text>
          </g>
        ))}
      </svg>

      <div className="mt-1 min-h-[1.25rem] font-mono-data text-xs text-[var(--app-ink-soft)]" aria-live="polite">
        {!showYears && hovered
          ? `${lat(hovered.lat)} ${lon(hovered.lon)} — ${hovered.total >= 0 ? "+" : "−"}${formatQuantity(hovered.total, meta)} over ${spanYears} yr (${formatPValue(hovered.pValue)}, ${hovered.significant ? "significant" : "not significant"})`
          : !showYears
            ? "Hover a cell for its numbers. Hatched cells: no statistically clear trend."
            : ""}
      </div>

      {showYears && anomaly && (
        <div className="mt-2 flex items-center gap-3">
          <PixelButton size="sm" onClick={player.toggle}>
            {player.playing ? "Pause" : "Play"}
          </PixelButton>
          <input
            type="range"
            min={first}
            max={last}
            step={1}
            value={shownYear}
            onChange={(e) => player.scrub(Number(e.target.value))}
            aria-label="Year"
            className="flex-1"
          />
          <span className="w-12 font-mono-data text-sm text-[var(--app-ink)]">{shownYear}</span>
        </div>
      )}

      {showYears && anomaly ? (
        <Legend
          maxAbs={maxAnomaly}
          unit={unit}
          decimals={decimals}
          caption={`Change since each cell's own ${anomaly.baselineYears[0]}–${anomaly.baselineYears[anomaly.baselineYears.length - 1]} average. Blank cells have no data that year.`}
        />
      ) : (
        <Legend
          maxAbs={maxTotal}
          unit={unit}
          decimals={decimals}
          caption={`Total change over ${spanYears} years per cell (trend × years). Arrows mark statistically clear cells; size shows how much.`}
        />
      )}

      {summary && <DirectionSplitBar summary={summary} />}
    </div>
  );
}
