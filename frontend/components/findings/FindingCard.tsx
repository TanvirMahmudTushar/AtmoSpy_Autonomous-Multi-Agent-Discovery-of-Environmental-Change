import Link from "next/link";
import { ChangeGlyph } from "@/components/change/ChangeGlyph";
import { SignificanceBadge } from "@/components/ui/badge";
import { summaryChange } from "@/lib/changeModel";
import { CONCERN_COLOR, CONCERN_LABEL } from "@/lib/insightView";
import { formatPercent, formatPValue } from "@/lib/utils";
import type { FindingSummary } from "@/lib/types";

export function FindingCard({ finding }: { finding: FindingSummary }) {
  const direction = finding.trend_per_year > 0 ? "increasing" : "decreasing";
  const change = summaryChange(finding);
  const accent = finding.significance_classification === "statistically_significant" ? "var(--chart-good)" : "var(--app-muted)";
  return (
    <Link href={`/findings/${finding.id}`} className="block">
      <div className="hud-panel flex h-full flex-col gap-3 p-4 transition-transform hover:-translate-y-0.5 hover:shadow-[0_0_24px_-8px_var(--app-glow)]">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="label-telemetry text-[var(--app-accent-cyan)]">{finding.variable_name}</div>
            <div className="text-sm text-[var(--app-ink-soft)]">{finding.region_name}</div>
          </div>
          {finding.discovery_score?.rank && (
            <span className="font-mono-data text-[10px] text-[var(--app-accent-gold)]">#{finding.discovery_score.rank}</span>
          )}
        </div>

        <ChangeGlyph change={change} size={64} label={`${finding.variable_name} in ${finding.region_name}: ${change.sentence}`} />

        <div
          className="border-l-2 pl-3 font-mono-data text-xl font-semibold text-[var(--app-ink)]"
          style={{ borderColor: accent }}
        >
          {change.sentence}
          <div className="text-xs font-normal text-[var(--app-ink-soft)]">
            {formatPercent(finding.percent_change)} of the average · {direction}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <SignificanceBadge classification={finding.significance_classification} />
          <span className="font-mono-data text-xs text-[var(--app-muted)]">{formatPValue(finding.p_value)}</span>
          {finding.concern !== "none" && (
            <span
              className="px-1.5 py-0.5 font-display text-[7px]"
              style={{ border: `2px solid ${CONCERN_COLOR[finding.concern]}`, color: CONCERN_COLOR[finding.concern] }}
              title="Level of concern, from the size and direction of the change — see the finding for why"
            >
              {CONCERN_LABEL[finding.concern]}
            </span>
          )}
        </div>

        <div className="font-mono-data text-xs text-[var(--app-muted)]">
          {finding.period_start} – {finding.period_end}
        </div>

        {finding.discovery_score && (
          <div className="mt-auto grid grid-cols-2 gap-x-3 gap-y-1 border-t border-[var(--app-hud-line)] pt-2 font-mono-data text-[10px] text-[var(--app-muted)]">
            <span>magnitude {(finding.discovery_score.trend_magnitude_pct * 100).toFixed(0)}%</span>
            <span>significance {(finding.discovery_score.significance_strength * 100).toFixed(0)}%</span>
            <span>completeness {(finding.discovery_score.data_completeness * 100).toFixed(0)}%</span>
            <span>spatial extent {(finding.discovery_score.spatial_extent_fraction * 100).toFixed(0)}%</span>
          </div>
        )}
      </div>
    </Link>
  );
}
