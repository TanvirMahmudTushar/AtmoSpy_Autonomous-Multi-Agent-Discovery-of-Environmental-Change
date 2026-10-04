import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

interface PanelProps extends HTMLAttributes<HTMLDivElement> {
  /** "bevel" = original chunky game-panel chrome. "hud" = telemetry panel
   * with a glow hairline border and corner brackets — used for data-heavy
   * scientific content where instrumentation reads better than a dialog
   * box. */
  variant?: "bevel" | "hud";
}

export function Panel({ className, variant = "bevel", ...props }: PanelProps) {
  return <div className={cn(variant === "hud" ? "hud-panel" : "pixel-panel", "p-5", className)} {...props} />;
}

export function PanelTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn("font-display text-[11px] leading-relaxed tracking-wide text-[var(--app-ink)] mb-3", className)}
      {...props}
    />
  );
}

/** A single large telemetry-style number readout: label, big monospace
 * value, unit, with an accent-colored left rail. Used for the WHAT/WHERE/
 * HOW MUCH/SIGNIFICANCE grid and similar data displays. */
export function StatReadout({
  label,
  value,
  unit,
  accent = "cyan",
  className,
}: {
  label: string;
  value: string;
  unit?: string;
  accent?: "cyan" | "green" | "gold" | "clay" | "sky";
  className?: string;
}) {
  const accentVar = {
    cyan: "var(--app-accent-cyan)",
    green: "var(--app-accent-green)",
    gold: "var(--app-accent-gold)",
    clay: "var(--app-accent-clay)",
    sky: "var(--app-accent-sky)",
  }[accent];

  return (
    <div className={cn("border-l-2 pl-3", className)} style={{ borderColor: accentVar }}>
      <div className="label-telemetry">{label}</div>
      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="font-mono-data text-xl font-semibold text-[var(--app-ink)] sm:text-2xl">{value}</span>
        {unit && <span className="text-xs text-[var(--app-muted)]">{unit}</span>}
      </div>
    </div>
  );
}
