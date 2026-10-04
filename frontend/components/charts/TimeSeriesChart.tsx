"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  Tooltip,
  XAxis,
  YAxis,
  ResponsiveContainer,
} from "recharts";
import type { TimeSeriesChartData } from "@/lib/types";

export function TimeSeriesChart({ data }: { data: TimeSeriesChartData }) {
  const hasBand = data.trend_band && data.trend_band.length > 0;
  const merged = data.points.map((p) => {
    const fitted = data.trend_line.find((t) => t.year === p.year);
    const band = data.trend_band?.find((t) => t.year === p.year);
    return {
      year: p.year,
      observed: p.value,
      fitted: fitted?.fitted,
      band: band ? [band.lower, band.upper] : undefined,
    };
  });

  return (
    <div className="viz-root" style={{ colorScheme: "inherit" }}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-[var(--chart-ink-secondary)]">
          {data.variable_name} ({data.units})
        </span>
        <span className="flex items-center gap-4 text-xs text-[var(--chart-ink-secondary)]">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: "var(--chart-series-1)" }} />
            Annual observation
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-3" style={{ background: "var(--chart-series-8)" }} />
            Trend (Sen&apos;s slope)
          </span>
          {hasBand && (
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-3 rounded-sm" style={{ background: "var(--chart-series-8)", opacity: 0.2 }} />
              95% bootstrap band
            </span>
          )}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={merged} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
          <XAxis
            dataKey="year"
            type="number"
            domain={["dataMin", "dataMax"]}
            allowDuplicatedCategory={false}
            tick={{ fill: "var(--chart-muted)", fontSize: 11 }}
            axisLine={{ stroke: "var(--chart-axis)" }}
            tickLine={false}
          />
          <YAxis
            type="number"
            domain={["auto", "auto"]}
            tick={{ fill: "var(--chart-muted)", fontSize: 11 }}
            axisLine={{ stroke: "var(--chart-axis)" }}
            tickLine={false}
            width={56}
          />
          <Tooltip
            contentStyle={{
              background: "var(--chart-surface)",
              border: "1px solid var(--chart-grid)",
              color: "var(--chart-ink)",
              fontSize: 12,
            }}
            formatter={(value, name) => [typeof value === "number" ? value.toFixed(3) : value, name]}
          />
          {hasBand && (
            <Area
              dataKey="band"
              name="95% bootstrap band"
              stroke="none"
              fill="var(--chart-series-8)"
              fillOpacity={0.16}
              isAnimationActive={false}
              connectNulls
              legendType="none"
              tooltipType="none"
            />
          )}
          <Line
            dataKey="observed"
            name="Annual observation"
            stroke="none"
            isAnimationActive={false}
            dot={{ r: 3.5, fill: "var(--chart-series-1)", strokeWidth: 0 }}
            activeDot={{ r: 5, fill: "var(--chart-series-1)" }}
            connectNulls
          />
          <Line
            dataKey="fitted"
            name="Trend (Sen's slope)"
            stroke="var(--chart-series-8)"
            strokeWidth={2}
            isAnimationActive={false}
            dot={false}
            activeDot={false}
            connectNulls
          />
          {data.change_points.map((cp) => (
            <ReferenceDot
              key={cp.year}
              x={cp.year}
              y={cp.mean_after}
              r={5}
              fill="var(--chart-warning)"
              stroke="var(--chart-ink)"
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
      {data.change_points.length > 0 && (
        <p className="mt-1 text-xs text-[var(--chart-muted)]">
          ⬤ marks a detected change point (PELT algorithm) — a shift in the mean level, not necessarily the
          start of the long-run trend.
        </p>
      )}
    </div>
  );
}
