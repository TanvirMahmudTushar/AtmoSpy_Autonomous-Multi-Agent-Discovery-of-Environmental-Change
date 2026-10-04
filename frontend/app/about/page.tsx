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
            NASA Space Apps 2026&apos;s &ldquo;Through the Radar Looking Glass&rdquo;-adjacent Earth-system trend
            challenge asks: find variables measured by NASA missions or models, visualize how they change over
            time, and determine what is changing, where, how much, and whether the change is statistically
            significant — while never overstating what the data shows.
          </p>
        </Panel>

        <Panel>
          <PanelTitle>What this system does</PanelTitle>
          <p className="text-sm leading-relaxed text-[var(--app-ink-soft)]">
            An orchestrator agent turns a question (typed or autonomously generated) into a structured
            investigation plan. Specialized agent modules retrieve real NASA POWER data, check its quality,
            compute trend statistics, test significance, look for spatial and cross-variable relationships, check
            robustness, and assemble a report — all deterministic Python computation. An LLM (GPT-OSS-120B via
            Groq) is used only to plan the investigation from natural language and to phrase the final
            interpretation of numbers it is given; it never computes or invents a statistic.
          </p>
        </Panel>

        <Panel>
          <PanelTitle>Scientific methodology</PanelTitle>
          <ul className="list-inside list-disc space-y-1 text-sm text-[var(--app-ink-soft)]">
            <li>Trend: Mann-Kendall test + Sen&apos;s slope (primary, non-parametric), OLS regression (comparison).</li>
            <li>Significance: Mann-Kendall p-value at α=0.05, with a bootstrapped Sen&apos;s-slope 95% confidence interval.</li>
            <li>Change points: PELT algorithm (ruptures) on the annual series.</li>
            <li>Spatial: per-grid-cell Mann-Kendall/Sen&apos;s slope across a bounded NASA POWER regional query.</li>
            <li>Relationships: Pearson or Spearman correlation (chosen by a Shapiro normality screen), reported only as association.</li>
            <li>Robustness: first-half vs. second-half trend re-estimation to check persistence.</li>
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
          <p className="text-sm leading-relaxed text-[var(--app-ink-soft)]">
            NASA POWER (Prediction Of Worldwide Energy Resources), NASA Langley Research Center — MERRA-2
            reanalysis and GLDAS Noah land-surface model output, daily from 1981, no authentication required.{" "}
            <a href="https://power.larc.nasa.gov/docs/" target="_blank" rel="noreferrer" className="underline">
              power.larc.nasa.gov/docs
            </a>
            . SMAP, GRACE-FO, and MODIS NDVI are registered as extension points requiring NASA Earthdata
            credentials this deployment does not have configured — see the project README.
          </p>
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
          <p className="text-sm leading-relaxed text-[var(--app-ink-soft)]">
            Next.js/TypeScript/Tailwind frontend, FastAPI/Python backend, PostgreSQL + PostGIS (Supabase-portable),
            Groq (GPT-OSS-120B), NumPy/SciPy/pandas/statsmodels/pymannkendall/ruptures for statistics, MapLibre GL
            for spatial maps, Recharts for time series.
          </p>
        </Panel>

        <Panel>
          <PanelTitle>Limitations</PanelTitle>
          <ul className="list-inside list-disc space-y-1 text-sm text-[var(--app-ink-soft)]">
            <li>NASA POWER is reanalysis/model-derived data, not direct satellite retrieval — it carries its own uncertainty.</li>
            <li>A regional average can mask sub-regional variability (mitigated by the spatial grid analysis).</li>
            <li>Relationship analysis only ever reports correlation, never causation.</li>
            <li>Discovery mode scans a curated candidate list, not an exhaustive global search.</li>
            <li>No authentication/user accounts in this build — investigations are anonymous.</li>
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
