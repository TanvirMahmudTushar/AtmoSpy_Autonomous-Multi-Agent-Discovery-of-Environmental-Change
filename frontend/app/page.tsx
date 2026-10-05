import { Panel, PanelTitle } from "@/components/ui/panel";
import { PixelSprite } from "@/components/pixel/PixelSprite";
import { TileSprite } from "@/components/pixel/TileSprite";
import { Logo } from "@/components/layout/Logo";
import { HeroAuthCTA } from "@/components/layout/HeroAuthCTA";
import { ThemeToggle } from "@/components/layout/ThemeToggle";

const QUESTION_EXAMPLES = [
  "Find significant changes in soil moisture in South Asia since 2005.",
  "Where has temperature increased significantly?",
  "Compare temperature changes between Bangladesh and the Sahel.",
  "Why might soil moisture be decreasing in California's Central Valley?",
];

const PIPELINE = [
  { icon: "telescope", label: "Discover", desc: "Scan NASA data for candidate trends" },
  { icon: "compass", label: "Investigate", desc: "Plan and run the right analysis" },
  { icon: "mountain", label: "Analyze", desc: "Deterministic trend + significance tests" },
  { icon: "cloud", label: "Visualize", desc: "Charts and maps of real results" },
  { icon: "notebook", label: "Understand", desc: "Plain-language, guarded interpretation" },
  { icon: "star", label: "Record", desc: "Saved as a scientific finding" },
];

const MISSION_STATS = [
  { value: "1981–25", label: "NASA POWER coverage" },
  { value: "10", label: "Autonomous agents" },
  { value: "0", label: "Fabricated numbers" },
  { value: "16", label: "Candidates per scan" },
];

export default function LandingPage() {
  return (
    <div className="relative overflow-hidden">
      {/* Mission hero — telemetry framing over the global starfield backdrop. */}
      <div className="relative border-b border-[var(--app-hud-line)]">
        <div className="grid-texture absolute inset-0" />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[var(--app-bg)]" />
        <div className="absolute right-4 top-4 z-10">
          <ThemeToggle />
        </div>
        <div className="relative mx-auto max-w-6xl px-4 py-20 sm:py-28">
          <div className="flex flex-col items-center gap-7 text-center">
            <div className="relative flex h-40 w-40 items-center justify-center sm:h-52 sm:w-52">
              <div className="orbit-ring absolute inset-0" />
              <div className="orbit-ring orbit-spin-slow absolute inset-4 opacity-60" />
              <div className="orbit-spin-fast absolute inset-0">
                <span className="absolute left-1/2 top-0 h-2 w-2 -translate-x-1/2 rounded-full bg-[var(--app-accent-cyan)] shadow-[0_0_8px_var(--app-accent-cyan)]" />
              </div>
              <Logo size={112} className="relative drop-shadow-[0_0_24px_var(--app-glow)]" />
            </div>

            <h1 className="font-display text-[20px] leading-relaxed text-[var(--app-ink)] sm:text-[30px]">
              Earth is always changing.
            </h1>
            <p className="max-w-2xl text-balance text-lg text-[var(--app-ink-soft)]">
              Let&apos;s find out <em>where</em>, <em>how much</em>, and whether the change is{" "}
              <strong className="glow-text-cyan">statistically significant</strong> — using real NASA Earth
              observation data and an autonomous investigation pipeline, not guesses.
            </p>

            <HeroAuthCTA />

            <div className="mt-4 grid grid-cols-2 gap-x-10 gap-y-4 sm:grid-cols-4">
              {MISSION_STATS.map((s) => (
                <div key={s.label} className="text-center">
                  <div className="font-mono-data glow-text-cyan text-2xl font-semibold">{s.value}</div>
                  <div className="label-telemetry mt-1">{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 py-16 sm:py-20">
        <div className="mt-0 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-6">
          {PIPELINE.map((step, i) => (
            <Panel key={step.label} className="flex flex-col items-center gap-2 text-center">
              <span className="font-display text-[8px] text-[var(--app-muted)]">{i + 1}</span>
              <PixelSprite name={step.icon as never} size={32} />
              <span className="font-display text-[9px] text-[var(--app-ink)]">{step.label}</span>
              <span className="text-[11px] text-[var(--app-ink-soft)]">{step.desc}</span>
            </Panel>
          ))}
        </div>

        <div className="my-10 flex items-center justify-center gap-3 opacity-90">
          {(["sunflower", "cornGrown", "tomatoGrown", "wheatPatch", "sheep", "farmerA"] as const).map((t) => (
            <TileSprite key={t} tile={t} size={28} />
          ))}
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <Panel>
            <PanelTitle>Ask a question, watch the agents work</PanelTitle>
            <ul className="flex flex-col gap-2">
              {QUESTION_EXAMPLES.map((q) => (
                <li key={q} className="rounded-sm border-2 border-[var(--app-border)]/30 bg-[var(--app-panel-alt)] px-3 py-2 text-sm text-[var(--app-ink-soft)]">
                  &ldquo;{q}&rdquo;
                </li>
              ))}
            </ul>
          </Panel>

          <Panel>
            <PanelTitle>What this is not</PanelTitle>
            <div className="flex flex-col gap-3 text-sm text-[var(--app-ink-soft)]">
              <p>
                This is not a chatbot wearing a NASA logo. Every number — trend slope, percent change, p-value,
                confidence interval — comes from deterministic Python statistics (Mann-Kendall, Sen&apos;s slope,
                OLS regression) run on real NASA POWER data.
              </p>
              <p>
                The AI reasoning layer (GPT-OSS-120B via Groq) plans investigations and explains results in plain
                language. It never invents a number, and it never calls correlation causation.
              </p>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
