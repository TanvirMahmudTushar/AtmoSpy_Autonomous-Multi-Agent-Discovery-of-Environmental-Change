"use client";

import { useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
  ResponsiveContainer,
} from "recharts";
import type { MonthlySeries, TimeSeriesChartData } from "@/lib/types";

type View = "monthly" | "cycle" | "anomaly" | "annual";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const VIEW_LABEL: Record<View, string> = {
  monthly: "Monthly values",
  cycle: "Seasonal cycle",
  anomaly: "Seasonal cycle removed",
  annual: "Yearly averages",
};

const VIEW_CAPTION: Record<View, string> = {
  monthly:
    "The average of every month. The big regular wave is the seasonal cycle, and it can hide a slow change underneath.",
  cycle: "The normal year: the average for each calendar month over the whole record.",
  anomaly:
    "Each month minus its normal value (an anomaly). With the seasonal wave removed, a slow trend is easier to see and test.",
  annual: "One average per year. Averaging over a full year also removes the seasonal cycle.",
};

const TOOLTIP_STYLE = {
  background: "var(--chart-surface)",
  border: "1px solid var(--chart-grid)",
  color: "var(--chart-ink)",
  fontSize: 12,
};
const TICK = { fill: "var(--chart-muted)", fontSize: 11 };
const AXIS_LINE = { stroke: "var(--chart-axis)" };

/** "2003-07" -> 2003.54 (mid-month), matching the backend's decimal years. */
function decimalYear(ym: string): number {
  const [y, m] = ym.split("-").map(Number);
  return y + (m - 0.5) / 12;
}

function monthLabel(x: number): string {
  const y = Math.floor(x);
  const m = Math.min(12, Math.max(1, Math.round((x - y) * 12 + 0.5)));
  return `${MONTHS[m - 1]} ${y}`;
}

const fmt = (v: unknown) => (typeof v === "number" ? v.toFixed(3) : String(v ?? ""));

function LegendItem({ kind, label }: { kind: "dot" | "series" | "line" | "band"; label: string }) {
  const swatch =
    kind === "dot" ? (
      <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: "var(--chart-series-1)" }} />
    ) : kind === "series" ? (
      <span className="inline-block h-0.5 w-3" style={{ background: "var(--chart-series-1)" }} />
    ) : kind === "line" ? (
      <span className="inline-block h-0.5 w-3" style={{ background: "var(--chart-series-8)" }} />
    ) : (
      <span className="inline-block h-2.5 w-3 rounded-sm" style={{ background: "var(--chart-series-8)", opacity: 0.2 }} />
    );
  return (
    <span className="flex items-center gap-1.5">
      {swatch}
      {label}
    </span>
  );
}

function monthlyRows(m: MonthlySeries) {
  return m.dates.map((d, i) => ({
    x: decimalYear(d),
    raw: m.raw[i],
    anomaly: m.anomaly[i],
    fitted: m.fitted?.[i] ?? null,
    band: m.ci_lower && m.ci_upper && m.ci_lower[i] !== null && m.ci_upper[i] !== null ? [m.ci_lower[i], m.ci_upper[i]] : null,
  }));
}

export function TimeSeriesChart({ data }: { data: TimeSeriesChartData }) {
  const monthly = data.monthly;
  const anomalyHasTrend = Boolean(monthly?.fitted);
  const [view, setView] = useState<View>(anomalyHasTrend ? "anomaly" : "annual");

  const views: View[] = monthly ? ["monthly", "cycle", "anomaly", "annual"] : ["annual"];

  return (
    <div className="viz-root" style={{ colorScheme: "inherit" }}>
      {views.length > 1 && (
        <div role="tablist" aria-label="Chart view" className="mb-2 flex flex-wrap gap-1">
          {views.map((v) => (
            <button
              key={v}
              type="button"
              role="tab"
              aria-selected={view === v}
              data-tour-view={v}
              onClick={() => setView(v)}
              className={`border-2 px-2.5 py-1 font-display text-[8px] ${
                view === v
                  ? "border-[var(--app-border)] bg-[var(--app-panel-alt)] text-[var(--app-ink)]"
                  : "border-transparent text-[var(--app-muted)] hover:text-[var(--app-ink)]"
              }`}
            >
              {VIEW_LABEL[v]}
            </button>
          ))}
        </div>
      )}

      {view === "annual" && <AnnualView data={data} />}
      {view === "monthly" && monthly && <MonthlyView data={data} monthly={monthly} />}
      {view === "cycle" && monthly && <CycleView data={data} monthly={monthly} />}
      {view === "anomaly" && monthly && <AnomalyView data={data} monthly={monthly} />}

      {views.length > 1 && <p className="mt-1 text-xs text-[var(--chart-ink-secondary)]">{VIEW_CAPTION[view]}</p>}
      <DataTable data={data} view={view} />
    </div>
  );
}

function Header({ data, children }: { data: TimeSeriesChartData; children?: React.ReactNode }) {
  return (
    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
      <span className="text-sm text-[var(--chart-ink-secondary)]">
        {data.variable_name} ({data.units})
      </span>
      <span className="flex flex-wrap items-center gap-4 text-xs text-[var(--chart-ink-secondary)]">{children}</span>
    </div>
  );
}

function AnnualView({ data }: { data: TimeSeriesChartData }) {
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
  // v2 charts carry the band from the corrected Sen CI; v1 charts carried a bootstrap band.
  const bandLabel = data.basis ? "95% confidence band" : "95% bootstrap band";

  return (
    <>
      <Header data={data}>
        <LegendItem kind="dot" label="Yearly average" />
        <LegendItem kind="line" label="Trend (Sen's slope)" />
        {hasBand && <LegendItem kind="band" label={bandLabel} />}
      </Header>
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={merged} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
          <XAxis
            dataKey="year"
            type="number"
            domain={["dataMin", "dataMax"]}
            allowDuplicatedCategory={false}
            tick={TICK}
            axisLine={AXIS_LINE}
            tickLine={false}
          />
          <YAxis type="number" domain={["auto", "auto"]} tick={TICK} axisLine={AXIS_LINE} tickLine={false} width={56} />
          <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(value, name) => [fmt(value), name]} />
          {hasBand && (
            <Area
              dataKey="band"
              name={bandLabel}
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
            name="Yearly average"
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
            <ReferenceDot key={cp.year} x={cp.year} y={cp.mean_after} r={5} fill="var(--chart-warning)" stroke="var(--chart-ink)" />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
      {data.change_points.length > 0 && (
        <p className="mt-1 text-xs text-[var(--text-chart-muted)]">
          ⬤ marks a detected change point (PELT algorithm) — a shift in the mean level, not necessarily the start of
          the long-run trend.
        </p>
      )}
    </>
  );
}

function MonthlyView({ data, monthly }: { data: TimeSeriesChartData; monthly: MonthlySeries }) {
  return (
    <>
      <Header data={data} />
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={monthlyRows(monthly)} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
          <XAxis
            dataKey="x"
            type="number"
            domain={["dataMin", "dataMax"]}
            tickFormatter={(x: number) => String(Math.floor(x))}
            tick={TICK}
            axisLine={AXIS_LINE}
            tickLine={false}
          />
          <YAxis type="number" domain={["auto", "auto"]} tick={TICK} axisLine={AXIS_LINE} tickLine={false} width={56} />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelFormatter={(x) => monthLabel(Number(x))}
            formatter={(value, name) => [fmt(value), name]}
          />
          <Line
            dataKey="raw"
            name="Monthly average"
            stroke="var(--chart-series-1)"
            strokeWidth={1.5}
            isAnimationActive={false}
            dot={false}
            activeDot={{ r: 4, fill: "var(--chart-series-1)" }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </>
  );
}

function CycleView({ data, monthly }: { data: TimeSeriesChartData; monthly: MonthlySeries }) {
  const rows = monthly.climatology_by_month.map((v, i) => ({ month: i + 1, value: v }));
  return (
    <>
      <Header data={data} />
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
          <XAxis
            dataKey="month"
            type="number"
            domain={[1, 12]}
            ticks={[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]}
            tickFormatter={(m: number) => MONTHS[m - 1]}
            tick={TICK}
            axisLine={AXIS_LINE}
            tickLine={false}
          />
          <YAxis type="number" domain={["auto", "auto"]} tick={TICK} axisLine={AXIS_LINE} tickLine={false} width={56} />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelFormatter={(m) => MONTHS[Number(m) - 1]}
            formatter={(value) => [fmt(value), "Normal value"]}
          />
          <Line
            dataKey="value"
            name="Normal value"
            stroke="var(--chart-series-1)"
            strokeWidth={2}
            isAnimationActive={false}
            dot={{ r: 4, fill: "var(--chart-series-1)", stroke: "var(--chart-surface)", strokeWidth: 2 }}
            activeDot={{ r: 5, fill: "var(--chart-series-1)" }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </>
  );
}

function AnomalyView({ data, monthly }: { data: TimeSeriesChartData; monthly: MonthlySeries }) {
  const hasTrend = Boolean(monthly.fitted);
  return (
    <>
      <Header data={data}>
        <LegendItem kind="series" label="Monthly anomaly" />
        {hasTrend && <LegendItem kind="line" label="Trend (Sen's slope)" />}
        {hasTrend && <LegendItem kind="band" label="95% confidence band" />}
      </Header>
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={monthlyRows(monthly)} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
          <XAxis
            dataKey="x"
            type="number"
            domain={["dataMin", "dataMax"]}
            tickFormatter={(x: number) => String(Math.floor(x))}
            tick={TICK}
            axisLine={AXIS_LINE}
            tickLine={false}
          />
          <YAxis type="number" domain={["auto", "auto"]} tick={TICK} axisLine={AXIS_LINE} tickLine={false} width={56} />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelFormatter={(x) => monthLabel(Number(x))}
            formatter={(value, name) => [fmt(value), name]}
          />
          <ReferenceLine y={0} stroke="var(--chart-axis)" />
          {hasTrend && (
            <Area
              dataKey="band"
              name="95% confidence band"
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
            dataKey="anomaly"
            name="Monthly anomaly"
            stroke="var(--chart-series-1)"
            strokeWidth={1.5}
            strokeOpacity={0.75}
            isAnimationActive={false}
            dot={false}
            activeDot={{ r: 4, fill: "var(--chart-series-1)" }}
          />
          {hasTrend && (
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
          )}
        </ComposedChart>
      </ResponsiveContainer>
      {!hasTrend && (
        <p className="mt-1 text-xs text-[var(--text-chart-muted)]">
          The trend for this finding was tested on yearly averages, so no trend line is drawn on the monthly anomalies.
        </p>
      )}
    </>
  );
}

/** Table-view twin of the chart, so no value is reachable only by hovering. */
function DataTable({ data, view }: { data: TimeSeriesChartData; view: View }) {
  const m = data.monthly;
  let head: string[];
  let rows: Array<Array<string>>;
  if (view === "cycle" && m) {
    head = ["Month", `Normal value (${data.units})`];
    rows = m.climatology_by_month.map((v, i) => [MONTHS[i], fmt(v)]);
  } else if ((view === "monthly" || view === "anomaly") && m) {
    head = ["Month", `Value (${data.units})`, "Normal for month", "Anomaly"];
    rows = m.dates.map((d, i) => [d, fmt(m.raw[i]), fmt(m.climatology[i]), fmt(m.anomaly[i])]);
  } else {
    head = ["Year", `Yearly average (${data.units})`, "Trend"];
    rows = data.points.map((p) => [String(p.year), fmt(p.value), fmt(data.trend_line.find((t) => t.year === p.year)?.fitted)]);
  }
  return (
    <details className="mt-2 text-xs text-[var(--chart-ink-secondary)]">
      <summary className="cursor-pointer select-none">Show the data as a table</summary>
      <div className="mt-2 max-h-64 overflow-auto">
        <table className="w-full border-collapse tabular-nums">
          <thead>
            <tr>
              {head.map((h) => (
                <th key={h} scope="col" className="border-b border-[var(--chart-grid)] px-2 py-1 text-left font-normal text-[var(--chart-ink)]">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r[0]}>
                {r.map((c, i) => (
                  <td key={i} className="border-b border-[var(--chart-grid)] px-2 py-0.5">
                    {c}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
