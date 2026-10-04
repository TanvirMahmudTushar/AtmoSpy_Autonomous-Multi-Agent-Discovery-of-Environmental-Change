"use client";

import { useEffect } from "react";
import { PixelSprite } from "@/components/pixel/PixelSprite";
import type { ICONS } from "@/components/pixel/icons";
import type { InvestigationStep } from "@/lib/types";

function JsonValue({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value === null || value === undefined) return <span className="text-[var(--app-muted)]">null</span>;
  if (typeof value === "number") return <span style={{ color: "var(--app-accent-gold)" }}>{value}</span>;
  if (typeof value === "boolean") return <span style={{ color: "var(--app-accent-sky)" }}>{String(value)}</span>;
  if (typeof value === "string") return <span style={{ color: "var(--chart-good)" }}>&quot;{value}&quot;</span>;

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-[var(--app-muted)]">[]</span>;
    // Long numeric arrays (annual series etc.) — show a compact inline preview, not 30 lines.
    if (value.length > 8 && value.every((v) => typeof v === "number" || typeof v === "string")) {
      return (
        <span className="text-[var(--app-ink-soft)]">
          [{value.slice(0, 4).map((v) => JSON.stringify(v)).join(", ")}, ...{value.length - 4} more]
        </span>
      );
    }
    return (
      <div style={{ paddingLeft: depth > 0 ? 14 : 0 }}>
        {value.map((v, i) => (
          <div key={i}>
            <JsonValue value={v} depth={depth + 1} />
            {i < value.length - 1 && <span className="text-[var(--app-muted)]">,</span>}
          </div>
        ))}
      </div>
    );
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return <span className="text-[var(--app-muted)]">{"{}"}</span>;
    return (
      <div style={{ paddingLeft: depth > 0 ? 14 : 0 }}>
        {entries.map(([k, v], i) => (
          <div key={k}>
            <span style={{ color: "var(--app-accent-cyan)" }}>{k}</span>
            <span className="text-[var(--app-muted)]">: </span>
            <JsonValue value={v} depth={depth + 1} />
            {i < entries.length - 1 && <span className="text-[var(--app-muted)]">,</span>}
          </div>
        ))}
      </div>
    );
  }

  return <span>{String(value)}</span>;
}

export function NodeDetailModal({
  agentLabel,
  icon,
  steps,
  onClose,
}: {
  agentLabel: string;
  icon: keyof typeof ICONS;
  steps: InvestigationStep[];
  onClose: () => void;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const latestWithDetail = [...steps].reverse().find((s) => s.detail && Object.keys(s.detail).length > 0);

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto bg-black/60 p-4 pt-16 sm:pt-24" onClick={onClose}>
      <div
        className="hud-panel w-full max-w-2xl !rounded-md p-0"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[var(--app-hud-line)] px-4 py-3">
          <div className="flex items-center gap-2.5">
            <PixelSprite name={icon} size={24} />
            <div>
              <div className="font-display text-[10px] text-[var(--app-ink)]">{agentLabel}</div>
              <div className="label-telemetry">Tool call inspector</div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-sm border border-[var(--app-hud-line)] px-2 py-1 font-display text-[9px] text-[var(--app-ink-soft)] hover:border-[var(--chart-critical)] hover:text-[var(--chart-critical)]"
          >
            ESC ✕
          </button>
        </div>

        <div className="max-h-[70vh] overflow-y-auto p-4">
          <div className="label-telemetry mb-2">Event log for this agent</div>
          <div className="mb-4 flex flex-col gap-1.5">
            {steps.length === 0 && <p className="text-sm text-[var(--app-muted)]">No events yet.</p>}
            {steps.map((s, i) => (
              <div key={i} className="border-l-2 border-[var(--app-border)]/40 pl-2 text-xs">
                <span className="font-mono-data text-[var(--app-muted)]">
                  {new Date(s.ts || s.created_at || Date.now()).toLocaleTimeString(undefined, { hour12: false })}
                </span>{" "}
                <span className="uppercase" style={{ color: s.status === "error" ? "var(--chart-critical)" : s.status === "done" ? "var(--chart-good)" : "var(--app-accent-cyan)" }}>
                  {s.status}
                </span>{" "}
                <span className="text-[var(--app-ink-soft)]">{s.message}</span>
              </div>
            ))}
          </div>

          {latestWithDetail ? (
            <>
              <div className="label-telemetry mb-2">
                Raw computed data (from {new Date(latestWithDetail.ts || latestWithDetail.created_at || Date.now()).toLocaleTimeString(undefined, { hour12: false })})
              </div>
              <pre className="overflow-x-auto rounded-sm bg-[var(--app-bg-deep)] p-3 font-mono-data text-[11px] leading-relaxed">
                <JsonValue value={latestWithDetail.detail} />
              </pre>
              <p className="mt-2 text-[10px] text-[var(--app-muted)]">
                This is exactly what the agent computed and passed downstream — the same object the Report Agent
                and frontend charts read from. Nothing here is summarized or reworded by an LLM.
              </p>
            </>
          ) : (
            <p className="text-sm text-[var(--app-muted)]">This agent hasn&apos;t returned structured data yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
