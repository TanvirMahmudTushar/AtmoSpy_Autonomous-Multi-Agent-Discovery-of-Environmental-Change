import { cn } from "@/lib/utils";
import { CheckCircle2, CircleDashed, XCircle } from "lucide-react";

/** Status colors are never used alone — always paired with an icon + label,
 * per the dataviz skill's status-palette rule. */
export function SignificanceBadge({ classification }: { classification: "statistically_significant" | "not_significant" }) {
  const significant = classification === "statistically_significant";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border-2 px-2 py-1 text-[9px] font-display",
        significant
          ? "border-[var(--chart-good)] text-[var(--chart-good)]"
          : "border-[var(--chart-muted)] text-[var(--chart-muted)]"
      )}
    >
      {significant ? <CheckCircle2 size={12} /> : <CircleDashed size={12} />}
      {significant ? "Statistically significant" : "Not significant"}
    </span>
  );
}

export function StepStatusIcon({ status }: { status: "running" | "done" | "error" | "skipped" }) {
  if (status === "running") return <CircleDashed size={14} className="animate-spin text-[var(--app-accent-sky)]" />;
  if (status === "done") return <CheckCircle2 size={14} style={{ color: "var(--chart-good)" }} />;
  if (status === "error") return <XCircle size={14} style={{ color: "var(--chart-critical)" }} />;
  return <CircleDashed size={14} className="text-[var(--app-muted)]" />;
}
