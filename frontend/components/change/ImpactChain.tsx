// Why it may be happening, what it could mean, what can be done — drawn as a
// chain: drivers -> the change -> impacts -> actions. The left-hand side and
// the actions are general, cited context for this *kind* of change (from the
// backend's curated knowledge base), and the page says so; the change in the
// middle, the concern level and the confidence come from this finding's own
// computed numbers. Nothing here is generated, and a change the data can't
// confirm gets no causal story at all.
//
// No hooks, so it renders on the server.

import type { ReactNode } from "react";
import { PixelSprite } from "@/components/pixel/PixelSprite";
import { summaryChange } from "@/lib/changeModel";
import {
  CONCERN_COLOR,
  CONCERN_LABEL,
  CONCERN_LEVELS,
  CONFIDENCE_LABEL,
  SECTOR_LABEL,
  SECTOR_SPRITE,
  isHarmful,
} from "@/lib/insightView";
import type { Concern, Confidence, FindingDetail, Insight } from "@/lib/types";
import { ChangeGlyph } from "./ChangeGlyph";

/** Four-step scale with the current level lit — reads at a glance, not just as a word. */
export function ConcernMeter({ concern }: { concern: Concern }) {
  const active = CONCERN_LEVELS.indexOf(concern);
  return (
    <svg
      viewBox="0 0 160 30"
      className="w-full max-w-[260px]"
      role="img"
      aria-label={`Concern level: ${CONCERN_LABEL[concern]}`}
    >
      {CONCERN_LEVELS.map((level, i) => {
        // "No clear change" lights only its own segment; otherwise the scale fills up to the level.
        const lit = active === 0 ? i === 0 : i <= active;
        const cx = i * 40 + 20;
        return (
          <g key={level}>
            <rect x={i * 40 + 1} y={4} width={38} height={10} fill={CONCERN_COLOR[level]} opacity={lit ? 0.95 : 0.18} stroke="var(--app-border)" strokeWidth={0.5} />
            {i === active && <polygon points={`${cx - 4},22 ${cx + 4},22 ${cx},16`} fill="var(--app-ink)" />}
          </g>
        );
      })}
    </svg>
  );
}

function ConfidenceBars({ confidence }: { confidence: Confidence }) {
  const lit = confidence === "high" ? 3 : confidence === "medium" ? 2 : 1;
  const color = confidence === "low" ? "var(--chart-warning)" : "var(--chart-good)";
  return (
    <svg width={30} height={16} viewBox="0 0 30 16" aria-hidden="true" shapeRendering="crispEdges">
      {[0, 1, 2].map((i) => {
        const h = (i + 1) * 5;
        return <rect key={i} x={i * 10} y={16 - h} width={8} height={h} fill={i < lit ? color : "var(--app-muted)"} opacity={i < lit ? 1 : 0.3} />;
      })}
    </svg>
  );
}

function Arrow() {
  return (
    <div className="flex items-center justify-center py-1 lg:px-0.5 lg:py-0" aria-hidden="true">
      <svg width={26} height={20} viewBox="0 0 13 10" shapeRendering="crispEdges" className="rotate-90 lg:rotate-0">
        <rect x={0} y={4} width={9} height={2} fill="var(--app-muted)" />
        <rect x={9} y={2} width={1} height={6} fill="var(--app-muted)" />
        <rect x={10} y={3} width={1} height={4} fill="var(--app-muted)" />
        <rect x={11} y={4} width={1} height={2} fill="var(--app-muted)" />
      </svg>
    </div>
  );
}

function Column({
  title,
  sprite,
  accent,
  children,
}: {
  title: string;
  sprite: string;
  accent: string;
  children: ReactNode;
}) {
  return (
    <section
      className="flex min-w-0 flex-col gap-2 border-2 border-[var(--app-border)]/40 bg-[var(--app-panel-alt)] p-3"
      style={{ borderTop: `4px solid ${accent}` }}
    >
      <div className="flex items-center gap-2">
        <PixelSprite name={sprite} size={18} />
        <h4 className="font-display text-[8px] leading-relaxed text-[var(--app-ink)]">{title}</h4>
      </div>
      {children}
    </section>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="flex flex-col gap-1.5">
      {items.map((t) => (
        <li key={t} className="flex gap-1.5 text-xs leading-snug text-[var(--app-ink-soft)]">
          <span aria-hidden="true" className="mt-[5px] h-1.5 w-1.5 flex-none bg-[var(--app-muted)]" />
          <span>{t}</span>
        </li>
      ))}
    </ul>
  );
}

const EVIDENCE_COLOR: Record<string, string> = {
  step: "var(--chart-warning)",
  related: "var(--app-accent-sky)",
  spatial: "var(--app-accent-clay)",
  data: "var(--app-muted)",
};

function Evidence({ insight }: { insight: Insight }) {
  if (insight.evidence.length === 0) return null;
  return (
    <div>
      <div className="font-display text-[8px] text-[var(--app-muted)]">What this finding&apos;s own data adds</div>
      <ul className="mt-1.5 flex flex-col gap-1.5">
        {insight.evidence.map((e) => (
          <li key={e.text} className="flex gap-2 text-xs leading-snug text-[var(--app-ink-soft)]">
            <span aria-hidden="true" className="mt-[5px] h-2 w-2 flex-none" style={{ background: EVIDENCE_COLOR[e.kind] ?? "var(--app-muted)" }} />
            <span>{e.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ImpactChain({ finding }: { finding: FindingDetail }) {
  const insight = finding.insight;
  if (!insight) return null;

  const change = summaryChange(finding);
  const harmful = isHarmful(insight.concern);
  const color = CONCERN_COLOR[insight.concern];
  const actionTitle = harmful ? "How to reduce it" : "How to prepare";

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <div className="font-display text-[8px] text-[var(--app-muted)]">Level of concern</div>
          <div className="mt-1 font-display text-[10px]" style={{ color }}>
            {CONCERN_LABEL[insight.concern]}
          </div>
          <ConcernMeter concern={insight.concern} />
        </div>
        <div>
          <div className="font-display text-[8px] text-[var(--app-muted)]">Confidence in the finding itself</div>
          <div className="mt-1 flex items-center gap-2">
            <ConfidenceBars confidence={insight.confidence} />
            <span className="font-display text-[10px] text-[var(--app-ink)]">{CONFIDENCE_LABEL[insight.confidence]}</span>
          </div>
          {insight.confidence_reasons.length > 0 && (
            <p className="mt-1 text-[11px] leading-snug text-[var(--app-muted)]">{insight.confidence_reasons.join(" ")}</p>
          )}
        </div>
      </div>

      <p className="text-sm leading-snug text-[var(--app-ink)]">{insight.headline}</p>

      {insight.applicable && insight.confidence === "low" && (
        <p className="border-2 border-[var(--chart-warning)] bg-[var(--app-panel-alt)] p-2 text-xs leading-snug text-[var(--app-ink-soft)]">
          The analysis itself doubts this result. Check it against weather-station or other independent records before
          acting on it, and treat the context below as a hypothesis to test rather than an explanation.
        </p>
      )}

      {insight.applicable ? (
        <div className="grid gap-1 lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,0.85fr)_auto_minmax(0,1fr)_auto_minmax(0,1.1fr)] lg:items-stretch">
          <Column title="Possible drivers" sprite="magnifier" accent="var(--app-accent-sky)">
            <ul className="flex flex-col gap-2">
              {insight.drivers.map((d) => (
                <li key={d.title}>
                  <div className="text-xs font-semibold text-[var(--app-ink)]">{d.title}</div>
                  <div className="text-xs leading-snug text-[var(--app-ink-soft)]">{d.text}</div>
                </li>
              ))}
            </ul>
            {insight.region_context && (
              <p className="mt-1 border-t border-[var(--app-hud-line)] pt-2 text-[11px] italic leading-snug text-[var(--app-muted)]">
                About this place: {insight.region_context}
              </p>
            )}
          </Column>

          <Arrow />

          <Column title="The change" sprite="chart" accent={color}>
            <div className="flex flex-col items-start gap-2">
              <ChangeGlyph change={change} size={56} label={`${finding.variable_name} in ${finding.where}: ${change.sentence}`} />
              <div className="font-mono-data text-sm font-semibold text-[var(--app-ink)]">{change.sentence}</div>
              <div className="text-[11px] leading-snug text-[var(--app-muted)]">
                {finding.period_start.slice(0, 4)} → {finding.period_end.slice(0, 4)}, computed from NASA data
              </div>
            </div>
          </Column>

          <Arrow />

          <Column title="What it could mean" sprite="scales" accent="var(--app-accent-gold)">
            <ul className="flex flex-col gap-2">
              {insight.impacts.map((i) => (
                <li key={`${i.sector}-${i.text}`} className="flex gap-2">
                  <span className="mt-0.5 flex-none">
                    <PixelSprite name={SECTOR_SPRITE[i.sector] ?? "star"} size={16} />
                  </span>
                  <div>
                    <div className="text-xs font-semibold text-[var(--app-ink)]">{SECTOR_LABEL[i.sector] ?? i.sector}</div>
                    <div className="text-xs leading-snug text-[var(--app-ink-soft)]">{i.text}</div>
                  </div>
                </li>
              ))}
            </ul>
          </Column>

          <Arrow />

          <Column title={actionTitle} sprite="flag" accent="var(--app-accent-green)">
            {insight.mitigate.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-[var(--app-ink)]">
                  {harmful ? "Reduce the cause" : "Limit the cause"}
                </div>
                <div className="mt-1">
                  <BulletList items={insight.mitigate} />
                </div>
              </div>
            )}
            {insight.adapt.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-[var(--app-ink)]">Cope with the effect</div>
                <div className="mt-1">
                  <BulletList items={insight.adapt} />
                </div>
              </div>
            )}
            {!harmful && (
              <p className="text-[11px] leading-snug text-[var(--app-muted)]">
                This change is not clearly harmful on its own, so these are preparations rather than prevention.
              </p>
            )}
          </Column>
        </div>
      ) : (
        <div className="border-2 border-dashed border-[var(--app-border)]/50 bg-[var(--app-panel-alt)] p-3">
          <p className="text-sm text-[var(--app-ink)]">{insight.concern_reasons.join(" ")}</p>
          <p className="mt-1 text-xs text-[var(--app-muted)]">
            A cause-and-effect story is not offered for a trend the data cannot confirm.
          </p>
        </div>
      )}

      <Evidence insight={insight} />

      <div className="border-t border-[var(--app-hud-line)] pt-3">
        <p className="text-[11px] leading-snug text-[var(--app-muted)]">{insight.disclaimer}</p>
        {insight.references.length > 0 && (
          <details className="mt-1">
            <summary className="cursor-pointer font-display text-[8px] text-[var(--app-muted)]">Sources</summary>
            <ul className="mt-1 flex flex-col gap-0.5">
              {insight.references.map((r) => (
                <li key={r.url}>
                  <a href={r.url} target="_blank" rel="noreferrer" className="text-[11px] text-[var(--app-accent-cyan)] underline">
                    {r.label}
                  </a>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}
