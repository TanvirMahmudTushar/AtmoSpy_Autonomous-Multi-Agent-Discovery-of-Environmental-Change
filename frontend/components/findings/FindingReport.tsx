import { Panel, PanelTitle, StatReadout } from "@/components/ui/panel";
import { SignificanceBadge } from "@/components/ui/badge";
import { TimeSeriesChart } from "@/components/charts/TimeSeriesChart";
import { SpatialMap } from "@/components/charts/SpatialMap";
import { SpatialTimelapse } from "@/components/charts/SpatialTimelapse";
import { RelationshipScatter } from "@/components/charts/RelationshipScatter";
import { ChangeScene } from "@/components/change/ChangeScene";
import { ImpactChain } from "@/components/change/ImpactChain";
import { SpatialChangeMap } from "@/components/change/SpatialChangeMap";
import { ExportMenu } from "@/components/findings/ExportMenu";
import { PixelSprite } from "@/components/pixel/PixelSprite";
import { formatPValue, formatPercent } from "@/lib/utils";
import type { FindingDetail } from "@/lib/types";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="font-display text-[8px] text-[var(--app-muted)]">{label}</div>
      <div className="mt-1 text-sm text-[var(--app-ink)]">{children}</div>
    </div>
  );
}

export function FindingReport({ finding }: { finding: FindingDetail }) {
  return (
    <div className="flex flex-col gap-6">
      <Panel variant="hud">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <span className="label-telemetry">Finding Record</span>
            <h1 className="mt-1 font-display text-[14px] leading-relaxed text-[var(--app-ink)]">{finding.title}</h1>
            <p className="mt-1 font-mono-data text-xs text-[var(--app-muted)]">
              {finding.period_start} &rarr; {finding.period_end}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <SignificanceBadge classification={finding.significance_classification} />
            <ExportMenu finding={finding} />
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-5 sm:grid-cols-4">
          <StatReadout label="What" value={finding.what} accent="sky" />
          <StatReadout label="Where" value={finding.where} accent="green" />
          <StatReadout
            label="How much"
            value={`${finding.trend_per_year.toFixed(4)}`}
            unit={finding.trend_units}
            accent="gold"
          />
          <StatReadout
            label="Significance"
            value={formatPValue(finding.p_value)}
            unit={formatPercent(finding.percent_change) + " total"}
            accent={finding.significance_classification === "statistically_significant" ? "cyan" : "clay"}
          />
        </div>
      </Panel>

      {finding.visualizations.timeseries && (
        <Panel variant="hud">
          <PanelTitle>What changed</PanelTitle>
          <ChangeScene finding={finding} />
        </Panel>
      )}

      {finding.insight && (
        <Panel variant="hud">
          <PanelTitle>Why it may be happening, and what to do</PanelTitle>
          <ImpactChain finding={finding} />
        </Panel>
      )}

      <Panel>
        <PanelTitle>What &ldquo;significant&rdquo; means here</PanelTitle>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-sm border-2 border-[var(--chart-series-1)]/40 bg-[var(--app-panel-alt)] p-3">
            <div className="font-display text-[8px] text-[var(--chart-series-1)]">Visually noticeable</div>
            <p className="mt-1 text-xs text-[var(--app-ink-soft)]">The chart below shows an apparent change — but a pattern alone proves nothing statistically.</p>
          </div>
          <div className="rounded-sm border-2 border-[var(--chart-good)]/50 bg-[var(--app-panel-alt)] p-3">
            <div className="font-display text-[8px] text-[var(--chart-good)]">Statistically significant</div>
            <p className="mt-1 text-xs text-[var(--app-ink-soft)]">
              {finding.significance_classification === "statistically_significant"
                ? `Yes — the Mann-Kendall test rejects "no trend" (${formatPValue(finding.p_value)} < 0.05).`
                : `No — ${formatPValue(finding.p_value)} does not clear the 0.05 threshold.`}
            </p>
          </div>
          <div className="rounded-sm border-2 border-[var(--chart-warning)]/50 bg-[var(--app-panel-alt)] p-3">
            <div className="font-display text-[8px] text-[var(--chart-warning)]">Scientifically important</div>
            <p className="mt-1 text-xs text-[var(--app-ink-soft)]">{finding.importance_note}</p>
          </div>
        </div>
      </Panel>

      {finding.visualizations.timeseries && (
        <Panel variant="hud">
          <PanelTitle>Time series</PanelTitle>
          <TimeSeriesChart data={finding.visualizations.timeseries} />
        </Panel>
      )}

      {finding.visualizations.spatial_map && (
        <Panel variant="hud">
          <PanelTitle>Where the change is happening</PanelTitle>
          <SpatialChangeMap
            map={finding.visualizations.spatial_map}
            timelapse={finding.visualizations.spatial_timelapse}
            summary={finding.spatial_summary}
            spanYears={Number(finding.period_end.slice(0, 4)) - Number(finding.period_start.slice(0, 4))}
            variableCode={finding.variable_code}
            variableName={finding.variable_name}
          />
          {finding.spatial_summary?.has_opposite_regional_trends && (
            <p className="mt-3 rounded-sm border-2 border-[var(--chart-warning)] bg-[var(--app-panel-alt)] p-2 text-xs text-[var(--app-ink-soft)]">
              This region shows the same variable trending in <em>opposite</em> directions in different places —{" "}
              {finding.spatial_summary.increasing_cells} increasing vs {finding.spatial_summary.decreasing_cells}{" "}
              decreasing grid cells.
            </p>
          )}
          <details className="mt-4">
            <summary className="cursor-pointer font-display text-[8px] text-[var(--app-muted)]">
              View on a real basemap
            </summary>
            <div className="mt-3 flex flex-col gap-4">
              <SpatialMap data={finding.visualizations.spatial_map} />
              {finding.visualizations.spatial_timelapse && (
                <SpatialTimelapse data={finding.visualizations.spatial_timelapse} />
              )}
            </div>
          </details>
        </Panel>
      )}

      {finding.visualizations.scatter && (
        <Panel variant="hud">
          <PanelTitle>Related variable</PanelTitle>
          <RelationshipScatter data={finding.visualizations.scatter} />
        </Panel>
      )}

      {finding.related_variables && finding.related_variables.length > 0 && (
        <Panel variant="hud">
          <PanelTitle>Related variables (correlation, not causation)</PanelTitle>
          <div className="flex flex-col gap-2">
            {finding.related_variables.map((rv) => (
              <div
                key={rv.variable_code}
                className="flex items-center justify-between border-l-2 border-[var(--app-accent-sky)] bg-[var(--app-panel-alt)] px-3 py-2 text-sm"
              >
                <span>{rv.variable_name}</span>
                <span className="font-mono-data text-[var(--app-ink-soft)]">
                  {rv.method} r={rv.r.toFixed(2)}, {formatPValue(rv.p_value)}
                </span>
              </div>
            ))}
          </div>
        </Panel>
      )}

      <Panel>
        <PanelTitle>Interpretation</PanelTitle>
        <p className="text-sm leading-relaxed text-[var(--app-ink-soft)]">{finding.interpretation}</p>
        <p className="mt-2 text-xs text-[var(--app-muted)]">
          Narrative generated by: {finding.narrative_source === "llm" ? "GPT-OSS-120B (Groq)" : "deterministic template (no LLM key configured)"}
        </p>
      </Panel>

      <Panel>
        <PanelTitle>Limitations</PanelTitle>
        <p className="text-sm leading-relaxed text-[var(--app-ink-soft)]">{finding.limitations}</p>
      </Panel>

      {finding.skeptic_review && (
        <Panel variant="hud" className="border-l-4" style={{ borderLeftColor: "var(--app-accent-clay)" }}>
          <div className="flex items-center gap-2">
            <PixelSprite name="flag" size={18} />
            <PanelTitle className="mb-0">Peer review (Skeptic Agent)</PanelTitle>
          </div>
          <p className="mb-2 mt-2 text-sm text-[var(--app-ink)]">
            Verdict: <span style={{ color: "var(--app-accent-clay)" }}>{finding.skeptic_review.verdict}</span>
          </p>
          {finding.skeptic_review.points.length === 0 ? (
            <p className="text-sm text-[var(--app-ink-soft)]">
              A deliberately adversarial pass found no major objections to raise against this finding.
            </p>
          ) : (
            <ul className="list-inside list-disc space-y-1.5 text-sm text-[var(--app-ink-soft)]">
              {finding.skeptic_review.points.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-[10px] text-[var(--app-muted)]">
            A dedicated agent deliberately argues against this finding before it&apos;s finalized — every
            point above traces to a number already computed elsewhere on this page, never a new claim.
          </p>
        </Panel>
      )}

      {finding.robustness && finding.robustness.caveats.length > 0 && (
        <Panel>
          <PanelTitle>Robustness check</PanelTitle>
          <p className="mb-2 text-sm text-[var(--app-ink)]">Verdict: {finding.robustness.verdict}</p>
          <ul className="list-inside list-disc text-sm text-[var(--app-ink-soft)]">
            {finding.robustness.caveats.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </Panel>
      )}

      {finding.provenance && (
        <Panel variant="hud" className="font-mono-data">
          <PanelTitle className="font-display">Data provenance</PanelTitle>
          <div className="grid gap-3 text-sm sm:grid-cols-2">
            <Field label="Source">{finding.provenance.source_name}</Field>
            <Field label="Version">{finding.provenance.dataset_version ?? "n/a"}</Field>
            <Field label="Method">{finding.statistical_method}</Field>
            <Field label="Processing">{finding.provenance.processing_method}</Field>
            <Field label="Retrieved">{new Date(finding.provenance.retrieval_time).toLocaleString()}</Field>
            <Field label="Query URL">
              <a
                href={finding.provenance.url}
                target="_blank"
                rel="noreferrer"
                className="break-all text-[var(--app-accent-cyan)] underline"
              >
                {finding.provenance.url}
              </a>
            </Field>
          </div>
        </Panel>
      )}
    </div>
  );
}
