import { Term } from "@/components/glossary/Term";
import { formatPValue, formatSigFig } from "@/lib/utils";
import type { Detectability, FindingDetail, SeasonalTrend, TrendDetails } from "@/lib/types";

const SEASON_NAME: Record<SeasonalTrend["season"], string> = {
  DJF: "Dec–Feb",
  MAM: "Mar–May",
  JJA: "Jun–Aug",
  SON: "Sep–Nov",
};

const signed = (n: number) => `${n > 0 ? "+" : ""}${formatSigFig(n)}`;

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-sm border-2 border-[var(--app-border)] bg-[var(--app-panel-alt)] p-3">
      <div className="font-display text-[8px] text-[var(--app-muted)]">{title}</div>
      <div className="mt-1.5 text-xs leading-relaxed text-[var(--app-ink-soft)]">{children}</div>
    </div>
  );
}

function Tests({ t, units }: { t: TrendDetails; units: string }) {
  const perDecade = `${units} per decade`;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Card title="Mann-Kendall test + Sen's slope (headline)">
        <p className="text-sm text-[var(--app-ink)]">{formatPValue(t.mk_p_value)}</p>
        <p>
          Rate: {signed(t.slope_per_decade)} {perDecade}, 95% confidence interval {signed(t.sen_ci_lower * 10)} to{" "}
          {signed(t.sen_ci_upper * 10)}.
        </p>
        <p className="mt-1 text-[var(--app-muted)]">
          The <Term k="mann_kendall">Mann-Kendall test</Term> counts how often later values beat earlier ones;{" "}
          <Term k="sens_slope">Sen&apos;s slope</Term> gives the rate. Neither is thrown off by outliers.
        </p>
      </Card>
      <Card title="t-test on the regression slope (second check)">
        <p className="text-sm text-[var(--app-ink)]">{formatPValue(t.ols_p_value)}</p>
        {t.ols_ci_lower !== null && t.ols_ci_upper !== null && (
          <p>
            Rate: {signed(t.ols_slope_per_year * 10)} {perDecade}, 95% confidence interval {signed(t.ols_ci_lower * 10)} to{" "}
            {signed(t.ols_ci_upper * 10)}.
          </p>
        )}
        <p className="mt-1 text-[var(--app-muted)]">
          The <Term k="t_test">t-test</Term> fits a straight line and asks whether its slope could be zero. Both
          ranges are <Term k="confidence_interval">95% confidence intervals</Term>.
        </p>
      </Card>
    </div>
  );
}

function Autocorrelation({ t }: { t: TrendDetails }) {
  const unit = t.basis === "monthly_anomaly" ? "months" : "years";
  if (t.lag1 <= 0.05) {
    return (
      <p>
        Neighbouring {unit} are nearly independent of each other (lag-1 autocorrelation {t.lag1.toFixed(2)}), so no
        correction was needed.
      </p>
    );
  }
  return (
    <p>
      Neighbouring {unit} resemble each other (<Term k="autocorrelation">autocorrelation</Term> {t.lag1.toFixed(2)}),
      so the {t.n_points} {unit} carry about as much independent information as {Math.round(t.n_eff)} (the{" "}
      <Term k="effective_sample_size">effective sample size</Term>). Both tests account for this. Without the
      correction the Mann-Kendall result would have been {formatPValue(t.mk_p_value_original)}, which overstates the
      certainty.
    </p>
  );
}

function DetectabilityGauge({ d, significant }: { d: Detectability; significant: boolean }) {
  if (d.years_needed === null) {
    return <p>There is no measurable trend, so there is no detection horizon to estimate.</p>;
  }
  const max = Math.max(d.years_needed, d.years_available) * 1.1;
  const pct = (v: number) => `${Math.min(100, (v / max) * 100)}%`;
  const label = significant
    ? `The trend is already significant with ${d.years_available} years of data. A trend this size typically needs about ${Math.round(d.years_needed)} years to be detected.`
    : d.projected_year
      ? `Not significant yet. A trend this size typically needs about ${Math.round(d.years_needed)} years of data to be detected, and this record has ${d.years_available}. If the trend continues, it could become detectable around ${d.projected_year}.`
      : `Not significant, even though ${d.years_available} years is usually enough to detect a trend this size (about ${Math.round(d.years_needed)} years). The change may simply not be there.`;
  return (
    <div>
      <div
        className="relative h-3 w-full rounded-sm bg-[var(--chart-grid)]"
        role="img"
        aria-label={`${d.years_available} years of data available, about ${Math.round(d.years_needed)} years needed`}
      >
        <div className="absolute inset-y-0 left-0 rounded-sm bg-[var(--chart-series-1)]" style={{ width: pct(d.years_available) }} />
        <div className="absolute inset-y-[-3px] w-0.5 bg-[var(--chart-ink)]" style={{ left: pct(d.years_needed) }} />
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-[var(--app-muted)]">
        <span>
          <span className="mr-1 inline-block h-2 w-2 rounded-sm bg-[var(--chart-series-1)] align-middle" />
          {d.years_available} years available
        </span>
        <span>
          <span className="mr-1 inline-block h-2.5 w-0.5 bg-[var(--chart-ink)] align-middle" />
          ~{Math.round(d.years_needed)} years needed
        </span>
      </div>
      <p className="mt-2">{label}</p>
      <p className="mt-1 text-[var(--app-muted)]">
        <Term k="detectability">Years to detect</Term>, estimated with Weatherhead et al. (1998) from this record&apos;s
        own noise.
      </p>
    </div>
  );
}

function Seasons({ seasons, units }: { seasons: SeasonalTrend[]; units: string }) {
  const maxAbs = Math.max(...seasons.map((s) => Math.abs(s.slope_per_decade)), 1e-12);
  return (
    <table className="w-full border-collapse text-xs">
      <caption className="sr-only">Trend for each season, {units} per decade</caption>
      <thead>
        <tr className="text-left text-[var(--app-muted)]">
          <th scope="col" className="py-1 font-normal">Season</th>
          <th scope="col" className="py-1 font-normal">Per decade</th>
          <th scope="col" className="w-2/5 py-1 font-normal" aria-hidden="true" />
          <th scope="col" className="py-1 font-normal">Significant?</th>
        </tr>
      </thead>
      <tbody>
        {seasons.map((s) => {
          const w = `${(Math.abs(s.slope_per_decade) / maxAbs) * 50}%`;
          const up = s.slope_per_decade > 0;
          return (
            <tr key={s.season} className="border-t border-[var(--chart-grid)]">
              <th scope="row" className="py-1 text-left font-normal text-[var(--app-ink)]">{SEASON_NAME[s.season]}</th>
              <td className="py-1 tabular-nums">{signed(s.slope_per_decade)}</td>
              <td className="py-1 pr-4" aria-hidden="true">
                <div className="relative h-2.5">
                  <div className="absolute inset-y-0 left-1/2 w-px bg-[var(--chart-axis)]" />
                  <div
                    className="absolute inset-y-0 rounded-sm"
                    style={{
                      width: w,
                      left: up ? "50%" : undefined,
                      right: up ? undefined : "50%",
                      background: up ? "var(--chart-diverge-high)" : "var(--chart-diverge-low)",
                      opacity: s.significant ? 1 : 0.35,
                    }}
                  />
                </div>
              </td>
              <td className="py-1">{s.significant ? `Yes (${formatPValue(s.p_value)})` : `No (${formatPValue(s.p_value)})`}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/** "How sure are we?" — the evidence behind an analysis-version-2 verdict. */
export function TrendEvidence({ finding }: { finding: FindingDetail }) {
  const t = finding.trend_details;
  if (!t) return null;
  const units = finding.trend_units.replace(/\/year$/, "");
  const significant = finding.significance_classification === "statistically_significant";
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-[var(--app-ink-soft)]">{t.basis_reason}</p>
      <Tests t={t} units={units} />
      <div className="grid gap-3 sm:grid-cols-2">
        <Card title="Why both tests were corrected">
          <Autocorrelation t={t} />
          {t.seasonal_mk_p_value !== null && (
            <p className="mt-1">
              Testing each calendar month separately (seasonal Mann-Kendall) gives {formatPValue(t.seasonal_mk_p_value)}.
            </p>
          )}
        </Card>
        {finding.detectability && (
          <Card title="Is the record long enough?">
            <DetectabilityGauge d={finding.detectability} significant={significant} />
          </Card>
        )}
      </div>
      {finding.seasonal_trends && finding.seasonal_trends.length > 0 && (
        <Card title={`Trend by season (${units} per decade)`}>
          <Seasons seasons={finding.seasonal_trends} units={units} />
        </Card>
      )}
    </div>
  );
}
