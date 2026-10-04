"use client";

import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import type { ScatterChartData } from "@/lib/types";

export function RelationshipScatter({ data }: { data: ScatterChartData }) {
  return (
    <div className="viz-root">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm text-[var(--chart-ink-secondary)]">
          {data.x_name} vs {data.y_name}
        </span>
        <span className="text-xs text-[var(--chart-muted)]">
          {data.correlation.method} r = {data.correlation.r.toFixed(2)}, p = {data.correlation.p_value.toFixed(4)}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="var(--chart-grid)" />
          <XAxis
            dataKey="x"
            name={data.x_name}
            type="number"
            domain={["auto", "auto"]}
            tickFormatter={(v: number) => v.toFixed(1)}
            tick={{ fill: "var(--chart-muted)", fontSize: 11 }}
            axisLine={{ stroke: "var(--chart-axis)" }}
            tickLine={false}
          />
          <YAxis
            dataKey="y"
            name={data.y_name}
            type="number"
            domain={["auto", "auto"]}
            tickFormatter={(v: number) => v.toFixed(1)}
            tick={{ fill: "var(--chart-muted)", fontSize: 11 }}
            axisLine={{ stroke: "var(--chart-axis)" }}
            tickLine={false}
            width={56}
          />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            contentStyle={{ background: "var(--chart-surface)", border: "1px solid var(--chart-grid)", fontSize: 12 }}
            formatter={(value) => (typeof value === "number" ? value.toFixed(3) : value)}
          />
          <Scatter data={data.points} fill="var(--chart-series-3)" />
        </ScatterChart>
      </ResponsiveContainer>
      <p className="mt-1 text-xs text-[var(--chart-muted)]">
        Association only — not evidence of causation. Each point is one year.
      </p>
    </div>
  );
}
