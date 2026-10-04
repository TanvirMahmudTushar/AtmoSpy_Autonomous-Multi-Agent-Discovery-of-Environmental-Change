// Compact Then -> Now pair for places that only have a summary row (Discover
// cards, globe popups and markers). No hooks and inline styles only, so it
// also works when rendered to a static HTML string inside a MapLibre popup,
// where the page's Tailwind classes can't be assumed.

import type { Direction, SummaryChange } from "@/lib/changeModel";
import { SceneFigure } from "./scenes";

export function directionColor(direction: Direction): string {
  if (direction === "up") return "var(--chart-diverge-high)";
  if (direction === "down") return "var(--chart-diverge-low)";
  return "var(--app-muted)";
}

/** A small filled triangle: up for increase, down for decrease, a dash when flat. */
export function DirectionBadge({ direction, size = 14 }: { direction: Direction; size?: number }) {
  const fill = directionColor(direction);
  return (
    <svg width={size} height={size} viewBox="0 0 8 8" shapeRendering="crispEdges" aria-hidden="true" style={{ flex: "none" }}>
      {direction === "up" && (
        <>
          <rect x={3} y={1} width={2} height={1} fill={fill} />
          <rect x={2} y={2} width={4} height={1} fill={fill} />
          <rect x={1} y={3} width={6} height={1} fill={fill} />
          <rect x={0} y={4} width={8} height={2} fill={fill} />
        </>
      )}
      {direction === "down" && (
        <>
          <rect x={0} y={2} width={8} height={2} fill={fill} />
          <rect x={1} y={4} width={6} height={1} fill={fill} />
          <rect x={2} y={5} width={4} height={1} fill={fill} />
          <rect x={3} y={6} width={2} height={1} fill={fill} />
        </>
      )}
      {direction === "flat" && <rect x={0} y={3} width={8} height={2} fill={fill} />}
    </svg>
  );
}

export function ChangeGlyph({
  change,
  size = 76,
  label,
}: {
  change: SummaryChange;
  /** Width of each of the two frames, in CSS px. */
  size?: number;
  /** Accessible description; pass the plain-language change sentence. */
  label: string;
}) {
  const border = `2px ${change.significant ? "solid" : "dashed"} var(--app-border)`;
  const frame = { border, opacity: change.significant ? 1 : 0.85, lineHeight: 0 } as const;
  return (
    <div
      role="img"
      aria-label={label}
      title={change.magnitudeKnown ? label : `${label} (size of change unavailable for this finding)`}
      style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
    >
      <div style={frame}>
        <SceneFigure scene={change.meta.scene} level={change.startLevel} width={size} label="Start of record" decorative />
      </div>
      <DirectionBadge direction={change.direction} />
      <div style={frame}>
        <SceneFigure scene={change.meta.scene} level={change.endLevel} width={size} label="End of record" decorative />
      </div>
    </div>
  );
}
