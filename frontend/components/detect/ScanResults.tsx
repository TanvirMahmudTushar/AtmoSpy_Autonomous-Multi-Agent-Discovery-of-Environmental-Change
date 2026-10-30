"use client";

import { eventsUrl } from "@/lib/api";
import { useAgentStream } from "@/lib/useAgentStream";
import { formatPValue, formatSigFig } from "@/lib/utils";
import { Term } from "@/components/glossary/Term";
import { LiveLogConsole } from "@/components/investigate/LiveLogConsole";
import { Panel, PanelTitle } from "@/components/ui/panel";
import type { ScanResult } from "@/lib/types";

const signed = (n: number) => `${n > 0 ? "+" : ""}${formatSigFig(n)}`;

type OnInvestigate = (variableCode: string, startYear: number, endYear: number) => void;

/** Live progress of a region scan, then its ranked shortlist. */
export function ScanResults({
  scanId,
  regionName,
  onInvestigate,
}: {
  scanId: string;
  regionName: string;
  /** Runs the full investigation over the same period the scan tested. */
  onInvestigate: OnInvestigate;
}) {
  const stream = useAgentStream(eventsUrl("scan", scanId));
  const final = stream.steps.find((s) => s.detail && "scan_results" in s.detail);
  const results = (final?.detail?.scan_results as ScanResult[] | undefined) ?? null;

  return (
    <div className="mt-8 flex flex-col gap-4">
      <LiveLogConsole steps={stream.steps} live={!stream.done} />
      {results && <ScanTable results={results} regionName={regionName} onInvestigate={onInvestigate} />}
    </div>
  );
}

/** The ranked shortlist of a finished scan. Without `onInvestigate` (e.g. in a
 * replayed demo) the rows have no action button. */
export function ScanTable({
  results,
  regionName,
  onInvestigate,
}: {
  results: ScanResult[];
  regionName: string;
  onInvestigate?: OnInvestigate;
}) {
  const maxEffect = Math.max(1, ...results.map((r) => r.effect_size));
  return (
    <Panel variant="hud" data-tour="scan">
      <PanelTitle>What is changing over {regionName}?</PanelTitle>
      <p className="mb-3 text-xs text-[var(--app-ink-soft)]">
        Every variable below was tested the same way on the region&apos;s area-weighted average. Because{" "}
        {results.length} variables were tested at once, significance is judged after a{" "}
        <Term k="false_discovery_rate">false-discovery-rate correction</Term>: with {results.length} tests, about{" "}
        {Math.max(1, Math.round(results.length * 0.05))} could look significant by luck alone.
      </p>
      {results.length === 0 ? (
        <p className="text-sm text-[var(--app-ink-soft)]">No variable had a long enough record here to test.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs">
            <caption className="sr-only">Trend screen of every available variable over {regionName}</caption>
            <thead>
              <tr className="text-left text-[var(--app-muted)]">
                <th scope="col" className="py-1.5 pr-3 font-normal">Variable</th>
                <th scope="col" className="py-1.5 pr-3 font-normal">Change per decade (95% CI)</th>
                <th scope="col" className="py-1.5 pr-3 font-normal">
                  <Term k="significant">Significant?</Term>
                </th>
                <th scope="col" className="py-1.5 pr-3 font-normal">
                  <Term k="effect_size">Size of change</Term>
                </th>
                {onInvestigate && (
                  <th scope="col" className="py-1.5 font-normal">
                    <span className="sr-only">Action</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.variable_code} className="border-t border-[var(--chart-grid)] align-top">
                  <th scope="row" className="py-2 pr-3 text-left font-normal">
                    <span className="text-[var(--app-ink)]">{r.name}</span>
                    <span className="block text-[10px] text-[var(--app-muted)]">
                      {r.start_year}–{r.end_year}
                      {r.sampling === "centroid_point" ? " · centre point only" : ""}
                    </span>
                  </th>
                  <td className="py-2 pr-3 tabular-nums text-[var(--app-ink-soft)]">
                    {signed(r.slope_per_decade)} {r.units}
                    <span className="block text-[10px] text-[var(--app-muted)]">
                      {signed(r.sen_ci_per_decade[0])} to {signed(r.sen_ci_per_decade[1])}
                    </span>
                  </td>
                  <td className="py-2 pr-3">
                    <span className={r.significant ? "text-[var(--text-good)]" : "text-[var(--app-muted)]"}>
                      {r.significant ? "Yes" : "No"}
                    </span>
                    <span className="block text-[10px] text-[var(--app-muted)]">
                      {formatPValue(r.p_value)}, after correction q = {formatSigFig(r.q_value, 2)}
                    </span>
                  </td>
                  <td className="py-2 pr-3">
                    <div className="h-2 w-24 rounded-sm bg-[var(--chart-grid)]" aria-hidden="true">
                      <div
                        className="h-2 rounded-sm"
                        style={{
                          width: `${(r.effect_size / maxEffect) * 100}%`,
                          background: "var(--chart-series-1)",
                          opacity: r.significant ? 1 : 0.4,
                        }}
                      />
                    </div>
                    <span className="text-[10px] text-[var(--app-muted)]">{r.effect_size.toFixed(2)}</span>
                  </td>
                  {onInvestigate && (
                    <td className="py-2">
                      <button
                        type="button"
                        onClick={() => onInvestigate(r.variable_code, r.start_year, r.end_year)}
                        className="whitespace-nowrap rounded-sm border border-[var(--app-border)]/40 px-2 py-1 text-[var(--app-ink)] hover:bg-[var(--app-panel-alt)]"
                      >
                        Investigate
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
