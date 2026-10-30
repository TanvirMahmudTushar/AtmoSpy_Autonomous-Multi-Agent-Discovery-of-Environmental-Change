import { Panel, PanelTitle } from "@/components/ui/panel";
import { PixelSprite } from "@/components/pixel/PixelSprite";

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <div className="mb-8 flex items-center gap-3">
        <PixelSprite name="earth" size={40} />
        <h1 className="font-display text-[16px] text-[var(--app-ink)]">About</h1>
      </div>

      <div className="flex flex-col gap-6">
        <Panel>
          <PanelTitle>The challenge</PanelTitle>
          <p className="text-sm leading-relaxed text-[var(--app-ink-soft)]">
            NASA Space Apps 2026&apos;s &ldquo;Be an Earth System Trend Detective&rdquo; challenge asks for a tool
            that selects variables measured by NASA missions or produced by NASA models, visualizes how they change
            over time, and determines what is changing, where, how much, and whether the change is statistically
            significant — while never overstating what the data shows.
          </p>
        </Panel>

        <Panel>
          <PanelTitle>What this system does</PanelTitle>
          <p className="text-sm leading-relaxed text-[var(--app-ink-soft)]">
            You choose a place and a variable (guided by suggestions), ask in plain language, or scan every variable
            over a region at once. Agent modules retrieve real NASA data for the whole region, check its quality,
            compute trend statistics, test significance, map where it is changing, look for related variables,
            check robustness, argue against the result, and assemble a report — all deterministic Python. An LLM
            (GPT-OSS-120B via Groq) only plans from plain language, suggests variables to look at, and words the
            interpretation of numbers it is given. It never computes a statistic, and its text is discarded if it
            quotes a number that doesn&apos;t trace back to the analysis.
          </p>
        </Panel>

        <Panel>
          <PanelTitle>Scientific methodology</PanelTitle>
          <ul className="list-inside list-disc space-y-1.5 text-sm text-[var(--app-ink-soft)]">
            <li>
              Region: the trend is computed on the region&apos;s cos(latitude) area-weighted average over every grid
              cell; a month counts only when at least 70% of the region&apos;s area has data.
            </li>
            <li>
              Seasons: daily data become monthly means (months under 70% observed are dropped); each calendar
              month&apos;s average (the climatology) is subtracted to give anomalies, and the trend is tested on the
              anomalies. When calendar months vary very differently (e.g. wet and dry seasons), the median-based slope
              would be dominated by the quiet months, so yearly averages are tested instead and the report says so.
            </li>
            <li>
              Trend and significance: Sen&apos;s slope (Sen 1968) with the Mann-Kendall test (Mann 1945; Kendall
              1975), its variance inflated by (1 + r₁)/(1 − r₁) for lag-1 autocorrelation r₁; the same corrected
              variance gives Sen&apos;s 95% confidence interval. A t-test on the OLS slope with effective sample size
              n(1 − r₁)/(1 + r₁) (Santer et al. 2000) is a second check, and the seasonal Mann-Kendall test (Hirsch
              et al. 1982) a third. In a Monte Carlo study on trendless monthly noise with lag-1 autocorrelation
              0.6, these keep false alarms at 5–9%, where the uncorrected test reaches about 30%.
            </li>
            <li>
              Record length: the years of data a trend of this size needs to be detected (Weatherhead et al. 1998),
              so a real but not-yet-significant trend is reported as such.
            </li>
            <li>
              Spatial: each grid cell is tested the same way, with the Benjamini-Hochberg false discovery rate at
              0.10 (Benjamini &amp; Hochberg 1995; Wilks 2016) so that testing many cells doesn&apos;t manufacture
              &ldquo;significant&rdquo; ones. Region scans and Discover correct across variables the same way.
            </li>
            <li>
              Relationships: correlation of each variable&apos;s detrended yearly anomalies (shared trends alone
              would correlate), with a multiple-testing correction, reported only as association.
            </li>
            <li>Change points: PELT (ruptures) on yearly averages. Robustness: the trend re-estimated on each half.</li>
            <li>
              Reproducibility: every recent finding can be downloaded as a Jupyter notebook that recomputes its
              statistics from the exact series analyzed.
            </li>
          </ul>
        </Panel>

        <Panel>
          <PanelTitle>&ldquo;Significant&rdquo; ≠ &ldquo;important&rdquo;</PanelTitle>
          <p className="text-sm leading-relaxed text-[var(--app-ink-soft)]">
            Every finding separates three distinct claims: whether a chart looks like it changed (visually
            noticeable), whether a statistical test rejects &ldquo;no trend&rdquo; (statistically significant),
            and how large the change is relative to natural year-to-year variability (an effect-size ratio, shown
            as a number, not a hidden verdict of &ldquo;important&rdquo;).
          </p>
        </Panel>

        <Panel>
          <PanelTitle>NASA data</PanelTitle>
          <ul className="list-inside list-disc space-y-1.5 text-sm text-[var(--app-ink-soft)]">
            <li>
              NASA POWER, NASA Langley Research Center: MERRA-2 meteorology and land-surface fields and GEWEX
              SRB/CERES solar radiation, from 1981, no login required (
              <a href="https://power.larc.nasa.gov/docs/" target="_blank" rel="noreferrer" className="underline">
                power.larc.nasa.gov/docs
              </a>
              ).
            </li>
            <li>GRACE/GRACE-FO JPL mascons (PO.DAAC) and SMAP L3 soil moisture (NSIDC), with a NASA Earthdata login.</li>
            <li>
              MERRA-2 (including pressure levels and aerosols), GPM IMERG, GLDAS, AIRS and OMI from NASA GES DISC, as
              analysis-ready monthly cubes regridded to 1° (0.5° for OMI). Each cube records its product version,
              DOI and the granules it was built from; a variable appears in the app only once its cube is built.
            </li>
            <li>
              Checked against the original files: for every monthly cube, regional averages over five test regions
              (from the whole Tibetan Plateau down to Delhi) were recomputed from the native-resolution NASA files.
              Large regions agree to a correlation of 0.9997 or better, with a bias under 4.5% of the month-to-month
              spread. A city-sized box covers only a few 1° cells, so there the 0.25° GLDAS land fields can differ by
              up to a fifth of their spread; for a single city, read land-water trends from a larger box.
            </li>
            <li>The Variables list shows each variable&apos;s source, first year and any known break in its record.</li>
          </ul>
        </Panel>

        <Panel>
          <PanelTitle>Art credits</PanelTitle>
          <p className="text-sm leading-relaxed text-[var(--app-ink-soft)]">
            Pixel-art UI chrome, agent-pipeline icons, and the Earth Observatory-style icon set are original,
            hand-built for this project (see <code>components/pixel/icons.ts</code>). The farm scenery — hero
            banner and decorative crop/animal sprites — is{" "}
            <a href="https://kenney.nl/assets/tiny-farm" target="_blank" rel="noreferrer" className="underline">
              &ldquo;Tiny Farm&rdquo; by Kenney
            </a>
            , released under{" "}
            <a href="https://creativecommons.org/publicdomain/zero/1.0/" target="_blank" rel="noreferrer" className="underline">
              CC0 1.0
            </a>{" "}
            (public domain) — free for commercial use, attribution appreciated but not required.
          </p>
        </Panel>

        <Panel>
          <PanelTitle>Technology</PanelTitle>
          <p className="text-sm leading-relaxed text-[var(--app-ink-soft)] [overflow-wrap:anywhere]">
            Next.js, TypeScript and Tailwind on the frontend, FastAPI and Python on the backend, PostgreSQL with
            PostGIS (Supabase works), Groq (GPT-OSS-120B), NumPy, SciPy, pandas, statsmodels, pymannkendall and
            ruptures for statistics, MapLibre GL for spatial maps, and Recharts for time series.
          </p>
        </Panel>

        <Panel>
          <PanelTitle>Limitations</PanelTitle>
          <ul className="list-inside list-disc space-y-1 text-sm text-[var(--app-ink-soft)]">
            <li>Reanalysis and model data (MERRA-2, GLDAS, NASA POWER) are not direct measurements; changes in the observations fed into them can create steps.</li>
            <li>A regional average can mask differences inside the region; the per-cell map shows them.</li>
            <li>NASA POWER grid requests are limited to 10° boxes; larger boxes fall back to the centre point, and the report says so.</li>
            <li>Only linear (monotonic) trends are tested; curved or step-like changes are flagged by the change-point and robustness checks rather than modelled.</li>
            <li>Relationship analysis only ever reports correlation, never causation.</li>
            <li>Discovery mode scans a curated candidate list, not an exhaustive global search.</li>
          </ul>
        </Panel>

        <Panel>
          <PanelTitle>Project</PanelTitle>
          <p className="text-sm leading-relaxed text-[var(--app-ink-soft)]">
            Built for NASA Space Apps Challenge 2026. Not an official NASA product; NASA does not endorse this
            project.
          </p>
        </Panel>
      </div>
    </div>
  );
}
