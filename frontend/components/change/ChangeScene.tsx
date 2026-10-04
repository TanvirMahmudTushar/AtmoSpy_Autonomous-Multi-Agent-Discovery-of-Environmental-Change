"use client";

import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { PixelButton } from "@/components/ui/button";
import {
  EFFECT_LARGE,
  EFFECT_SMALL,
  deriveChange,
  formatQuantity,
  type ChangeModel,
} from "@/lib/changeModel";
import type { FindingDetail } from "@/lib/types";
import { formatPValue } from "@/lib/utils";
import { DirectionBadge, directionColor } from "./ChangeGlyph";
import { SceneFigure } from "./scenes";
import { usePlayer } from "./usePlayer";

function subscribeReducedMotion(cb: () => void) {
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}

function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribeReducedMotion,
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    () => false,
  );
}

/** Where the wipe divider sits over the intro sweep: 50 -> 92 -> 8 -> 50. */
function sweepPosition(p: number): number {
  const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
  if (p < 0.3) return lerp(50, 92, p / 0.3);
  if (p < 0.8) return lerp(92, 8, (p - 0.3) / 0.5);
  return lerp(8, 50, (p - 0.8) / 0.2);
}

const PLAY_SECONDS = 7;

function fmt(value: number, model: ChangeModel): string {
  return value.toFixed(model.meta.decimals);
}

function EffectMeter({ model }: { model: ChangeModel }) {
  const CAP = 2;
  const W = 200;
  const x = (v: number) => (Math.min(v, CAP) / CAP) * W;
  // Keep the whole triangle inside the bar when the effect is off the scale.
  const markerX = Math.min(W - 4, Math.max(4, x(model.effectSize)));
  return (
    <div>
      <div className="font-display text-[8px] text-[var(--app-muted)]">How big vs. normal year-to-year swings</div>
      <svg viewBox={`0 0 ${W} 34`} className="mt-1 w-full" role="img" aria-label={`Effect size ${model.effectSize.toFixed(2)}, ${model.bucket}`}>
        <rect x={0} y={8} width={x(EFFECT_SMALL)} height={8} fill="var(--app-muted)" opacity={0.3} />
        <rect x={x(EFFECT_SMALL)} y={8} width={x(EFFECT_LARGE) - x(EFFECT_SMALL)} height={8} fill="var(--app-accent-gold)" opacity={0.45} />
        <rect x={x(EFFECT_LARGE)} y={8} width={W - x(EFFECT_LARGE)} height={8} fill="var(--app-accent-clay)" opacity={0.55} />
        <polygon
          points={`${markerX - 4},1 ${markerX + 4},1 ${markerX},9`}
          fill="var(--app-ink)"
        />
        {[
          [x(EFFECT_SMALL) / 2, "small"],
          [(x(EFFECT_SMALL) + x(EFFECT_LARGE)) / 2, "moderate"],
          [(x(EFFECT_LARGE) + W) / 2, "large"],
        ].map(([cx, text]) => (
          <text key={text as string} x={cx as number} y={28} textAnchor="middle" fontSize={7} fill="var(--app-ink-soft)">
            {text}
          </text>
        ))}
      </svg>
      <div className="font-mono-data text-xs text-[var(--app-ink-soft)]">
        effect size {model.effectSize.toFixed(2)} ({model.bucket})
      </div>
    </div>
  );
}

function RangeWhisker({ model }: { model: ChangeModel }) {
  const ci = model.deltaCI;
  if (!ci) return null;
  const lo = Math.min(ci.lower, ci.upper, model.delta, 0);
  const hi = Math.max(ci.lower, ci.upper, model.delta, 0);
  const pad = (hi - lo) * 0.12 || 1;
  const W = 200;
  const x = (v: number) => ((v - (lo - pad)) / (hi - lo + 2 * pad)) * W;
  const crossesZero = Math.min(ci.lower, ci.upper) <= 0 && Math.max(ci.lower, ci.upper) >= 0;
  const color = directionColor(model.direction);
  return (
    <div>
      <div className="font-display text-[8px] text-[var(--app-muted)]">Total change and its 95% range</div>
      <svg viewBox={`0 0 ${W} 32`} className="mt-1 w-full" role="img" aria-label={`Total change ${fmt(model.delta, model)}, 95% range ${fmt(ci.lower, model)} to ${fmt(ci.upper, model)}`}>
        <line x1={x(0)} x2={x(0)} y1={2} y2={20} stroke="var(--app-muted)" strokeWidth={1} strokeDasharray="2 2" />
        <rect x={x(Math.min(ci.lower, ci.upper))} y={9} width={Math.abs(x(ci.upper) - x(ci.lower))} height={6} fill={color} opacity={0.35} />
        <rect x={x(model.delta) - 1.5} y={5} width={3} height={14} fill={color} />
        <text x={x(0)} y={30} textAnchor="middle" fontSize={7} fill="var(--app-ink-soft)">0</text>
        <text x={x(model.delta)} y={30} textAnchor="middle" fontSize={7} fill="var(--app-ink)">{fmt(model.delta, model)}</text>
      </svg>
      <div className="font-mono-data text-xs text-[var(--app-ink-soft)]">
        {crossesZero ? "the range includes zero — a flat trend is plausible" : "the range excludes zero"}
      </div>
    </div>
  );
}

export function ChangeScene({ finding }: { finding: FindingDetail }) {
  const model = useMemo(() => deriveChange(finding), [finding]);
  if (!model) return null;
  return <ChangeSceneBody finding={finding} model={model} />;
}

function ChangeSceneBody({ finding, model }: { finding: FindingDetail; model: ChangeModel }) {
  const reduced = usePrefersReducedMotion();
  const [mode, setMode] = useState<"compare" | "years">("compare");
  const [wipe, setWipe] = useState(50);
  const { year, playing, toggle: togglePlay, scrub, pause } = usePlayer(model.startYear, model.endYear, PLAY_SECONDS);
  const touched = useRef(false);

  // One gentle sweep on load so the change is seen, not just available. Any
  // interaction cancels it; reduced-motion users never get it.
  useEffect(() => {
    if (reduced) return;
    let raf = 0;
    const t0 = performance.now();
    const DURATION = 2800;
    const step = (now: number) => {
      if (touched.current) return;
      const p = Math.min(1, (now - t0) / DURATION);
      setWipe(sweepPosition(p));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [reduced]);

  const scene = model.meta.scene;
  const shownYear = Math.round(year);
  const observed = model.observedAt(shownYear);
  const color = directionColor(model.direction);
  const sigColor = model.significant ? "var(--chart-good)" : "var(--app-muted)";

  const tab = (id: "compare" | "years", label: string) => (
    <button
      type="button"
      role="tab"
      aria-selected={mode === id}
      onClick={() => {
        touched.current = true;
        pause();
        setMode(id);
      }}
      className={`border-2 px-2.5 py-1 font-display text-[8px] ${
        mode === id
          ? "border-[var(--app-border)] bg-[var(--app-panel-alt)] text-[var(--app-ink)]"
          : "border-transparent text-[var(--app-muted)] hover:text-[var(--app-ink)]"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
      <figure className="m-0">
        <figcaption className="sr-only">{model.ariaLabel}</figcaption>
        <div role="tablist" aria-label="View" className="mb-2 flex gap-1">
          {tab("compare", "Then vs now")}
          {tab("years", "Year by year")}
        </div>

        {mode === "compare" ? (
          <div
            className="relative select-none overflow-hidden border-2 border-[var(--app-border)] focus-within:ring-2 focus-within:ring-[var(--app-accent-cyan)]"
            style={{ aspectRatio: "64 / 40" }}
          >
            <div className="absolute inset-0">
              <SceneFigure scene={scene} level={model.startLevel} fluid animated={!reduced} decorative label="Start of record" />
            </div>
            <div className="absolute inset-0" style={{ clipPath: `inset(0 0 0 ${wipe}%)` }}>
              <SceneFigure scene={scene} level={model.endLevel} fluid animated={!reduced} decorative label="End of record" />
            </div>
            <div className="pointer-events-none absolute inset-y-0 w-[3px] -translate-x-1/2 bg-white shadow-[0_0_0_1px_rgba(0,0,0,0.5)]" style={{ left: `${wipe}%` }} />
            <div
              className="pointer-events-none absolute top-1/2 flex h-6 w-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center border-2 border-[var(--app-border)] bg-white"
              style={{ left: `${wipe}%` }}
              aria-hidden="true"
            >
              <svg width={16} height={10} viewBox="0 0 12 8" shapeRendering="crispEdges">
                <rect x={0} y={3} width={1} height={2} fill="#000" />
                <rect x={1} y={2} width={1} height={4} fill="#000" />
                <rect x={2} y={1} width={1} height={6} fill="#000" />
                <rect x={3} y={3} width={6} height={2} fill="#000" />
                <rect x={9} y={1} width={1} height={6} fill="#000" />
                <rect x={10} y={2} width={1} height={4} fill="#000" />
                <rect x={11} y={3} width={1} height={2} fill="#000" />
              </svg>
            </div>
            <span className="pointer-events-none absolute left-2 top-2 bg-black/60 px-1.5 py-0.5 font-display text-[8px] text-white">THEN {model.startYear}</span>
            <span className="pointer-events-none absolute right-2 top-2 bg-black/60 px-1.5 py-0.5 font-display text-[8px] text-white">NOW {model.endYear}</span>
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={Math.round(wipe)}
              onChange={(e) => {
                touched.current = true;
                setWipe(Number(e.target.value));
              }}
              aria-label={`Drag to compare ${model.startYear} with ${model.endYear}`}
              className="absolute inset-0 h-full w-full cursor-ew-resize opacity-0"
            />
          </div>
        ) : (
          <div>
            <div className="relative overflow-hidden border-2 border-[var(--app-border)]" style={{ aspectRatio: "64 / 40" }}>
              <SceneFigure scene={scene} level={model.levelAt(year)} fluid animated={!reduced} decorative label={`Trend in ${shownYear}`} />
              <span className="pointer-events-none absolute left-2 top-2 bg-black/60 px-1.5 py-0.5 font-display text-[8px] text-white">{shownYear}</span>
            </div>
            <div className="mt-2 flex items-center gap-3">
              <PixelButton size="sm" onClick={togglePlay}>
                {playing ? "Pause" : "Play"}
              </PixelButton>
              <div className="relative flex-1 pb-4">
                <input
                  type="range"
                  min={model.startYear}
                  max={model.endYear}
                  step={1}
                  value={shownYear}
                  onChange={(e) => scrub(Number(e.target.value))}
                  aria-label="Year"
                  aria-valuetext={`${shownYear}, trend value ${fmt(model.valueAt(shownYear), model)} ${model.meta.unitLabel}`}
                  className="w-full"
                />
                {model.changePoints.map((cp) => (
                  <span
                    key={cp.year}
                    title={`${cp.year}: abrupt step of ${cp.shift > 0 ? "+" : "−"}${formatQuantity(cp.shift, model.meta)}`}
                    className="absolute top-4 -translate-x-1/2 font-display text-[7px] text-[var(--app-accent-gold)]"
                    style={{ left: `${((cp.year - model.startYear) / model.span) * 100}%` }}
                  >
                    ▲ step
                  </span>
                ))}
              </div>
            </div>
            <p className="mt-1 font-mono-data text-xs text-[var(--app-ink-soft)]">
              {shownYear}: trend {fmt(model.valueAt(shownYear), model)} {model.meta.unitLabel}
              {observed !== null && <> · observed that year {fmt(observed, model)} {model.meta.unitLabel}</>}
            </p>
          </div>
        )}

        <p className="mt-2 font-mono-data text-[11px] text-[var(--app-muted)]">
          Scene range = ±2 typical yearly swings (±{formatQuantity(2 * model.std, model.meta)} around the {model.startYear}–{model.endYear} average). Drawn from the trend line, not the raw years.
        </p>
      </figure>

      <div className="flex flex-col gap-4">
        <div className="flex items-start gap-2">
          <DirectionBadge direction={model.direction} size={18} />
          <p className="text-base leading-snug text-[var(--app-ink)]">{model.sentence}</p>
        </div>

        <div className="flex items-center gap-2 font-mono-data text-sm text-[var(--app-ink)]">
          <span title={`Trend line in ${model.startYear}`}>{fmt(model.startValue, model)}</span>
          <span style={{ color }} aria-hidden="true">→</span>
          <span title={`Trend line in ${model.endYear}`}>{fmt(model.endValue, model)}</span>
          <span className="text-xs text-[var(--app-muted)]">{model.meta.unitLabel}</span>
        </div>

        <span
          className="inline-block self-start px-2 py-1 font-display text-[8px]"
          style={{ border: `2px ${model.significant ? "solid" : "dashed"} ${sigColor}`, color: sigColor }}
        >
          {model.significant ? "STATISTICALLY SIGNIFICANT" : "NOT STATISTICALLY SIGNIFICANT"} · {formatPValue(finding.p_value)}
        </span>

        <EffectMeter model={model} />
        <RangeWhisker model={model} />
      </div>
    </div>
  );
}
