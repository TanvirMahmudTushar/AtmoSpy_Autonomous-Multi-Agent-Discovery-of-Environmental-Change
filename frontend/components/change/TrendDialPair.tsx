// Watches: what moved between the previous check and the latest one. Each dial
// is a tilted line — up-right for a rising trend, down-right for a falling
// one, steepest for the larger of the two slopes so the pair reads as a
// comparison. Solid = statistically significant, dashed = not.

import { dialTilt, directionOf, watchVerdict, type WatchVerdict } from "@/lib/changeModel";
import { prettyUnits } from "@/lib/variableMeta";
import { directionColor } from "./ChangeGlyph";

const VERDICT: Record<WatchVerdict, { text: string; color: string }> = {
  first: { text: "First check — nothing to compare yet", color: "var(--app-muted)" },
  flipped: { text: "Direction flipped since the last check", color: "var(--chart-warning)" },
  newly_significant: { text: "Newly statistically significant", color: "var(--chart-good)" },
  lost_significance: { text: "No longer statistically significant", color: "var(--app-accent-clay)" },
  consistent: { text: "Consistent with the previous check", color: "var(--app-muted)" },
};

function Dial({
  label,
  slope,
  significant,
  reference,
  units,
}: {
  label: string;
  slope: number;
  significant: boolean;
  reference: number;
  units: string;
}) {
  const tilt = dialTilt(slope, reference);
  const color = directionColor(directionOf(slope));
  const text = `${slope >= 0 ? "+" : "−"}${Math.abs(slope).toPrecision(2)} ${units}/yr, ${significant ? "significant" : "not significant"}`;
  return (
    <div className="flex flex-col items-center gap-1" role="img" aria-label={`${label}: ${text}`}>
      <svg width={84} height={72} viewBox="0 0 84 72" aria-hidden="true">
        <rect x={0.5} y={0.5} width={83} height={71} fill="var(--app-panel-alt)" stroke="var(--app-border)" strokeWidth={1} opacity={0.6} />
        <line x1={10} x2={76} y1={36} y2={36} stroke="var(--app-muted)" strokeWidth={1} strokeDasharray="2 3" />
        <g transform={`rotate(${-tilt} 12 36)`}>
          <line
            x1={12}
            x2={56}
            y1={36}
            y2={36}
            stroke={color}
            strokeWidth={4}
            strokeDasharray={significant ? undefined : "6 4"}
          />
          <polygon points="56,30 68,36 56,42" fill={color} />
        </g>
        <circle cx={12} cy={36} r={3} fill="var(--app-ink)" />
      </svg>
      <div className="font-display text-[7px] text-[var(--app-muted)]">{label}</div>
      <div className="font-mono-data text-[11px] text-[var(--app-ink-soft)]">
        {slope >= 0 ? "+" : "−"}
        {Math.abs(slope).toPrecision(2)}
        <span className="text-[var(--app-muted)]"> {units}/yr</span>
      </div>
    </div>
  );
}

export function TrendDialPair({
  prevTrend,
  prevSignificance,
  lastTrend,
  lastSignificance,
  units,
}: {
  prevTrend: number | null;
  prevSignificance: string | null;
  lastTrend: number | null;
  lastSignificance: string | null;
  units: string;
}) {
  if (lastTrend === null) return null;
  const verdict = watchVerdict(prevTrend, prevSignificance, lastTrend, lastSignificance);
  const reference = Math.max(Math.abs(prevTrend ?? 0), Math.abs(lastTrend)) || 1;
  const u = prettyUnits(units);
  const v = VERDICT[verdict];

  return (
    <div className="mt-3 flex flex-wrap items-center gap-4">
      {prevTrend !== null && (
        <>
          <Dial
            label="PREVIOUS CHECK"
            slope={prevTrend}
            significant={prevSignificance === "statistically_significant"}
            reference={reference}
            units={u}
          />
          <span aria-hidden="true" className="font-mono-data text-lg text-[var(--app-muted)]">→</span>
        </>
      )}
      <Dial
        label="LATEST CHECK"
        slope={lastTrend}
        significant={lastSignificance === "statistically_significant"}
        reference={reference}
        units={u}
      />
      <span
        className="px-2 py-1 font-display text-[8px]"
        style={{ border: `2px solid ${v.color}`, color: v.color }}
      >
        {v.text}
      </span>
    </div>
  );
}
