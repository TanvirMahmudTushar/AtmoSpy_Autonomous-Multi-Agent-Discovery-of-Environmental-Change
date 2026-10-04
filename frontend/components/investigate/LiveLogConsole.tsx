"use client";

import { useEffect, useRef, useState } from "react";
import type { InvestigationStep } from "@/lib/types";

const STATUS_COLOR: Record<string, string> = {
  running: "var(--app-accent-cyan)",
  done: "var(--chart-good)",
  error: "var(--chart-critical)",
  skipped: "var(--app-muted)",
};

function timeOf(step: InvestigationStep): string {
  const raw = step.ts || step.created_at;
  if (!raw) return "--:--:--";
  const d = new Date(raw);
  return d.toLocaleTimeString(undefined, { hour12: false });
}

/** A terminal-style live log — every SSE step appended as it arrives,
 * auto-scrolling, with a blinking cursor while the investigation is still
 * running. This is the raw play-by-play; AgentFlowGraph above it is the
 * at-a-glance view. */
export function LiveLogConsole({ steps, live }: { steps: InvestigationStep[]; live: boolean }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [steps, autoScroll]);

  function handleScroll() {
    const el = scrollRef.current;
    if (!el) return;
    setAutoScroll(el.scrollHeight - el.scrollTop - el.clientHeight < 24);
  }

  return (
    <div className="hud-panel flex flex-col p-0">
      <div className="flex items-center justify-between border-b border-[var(--app-hud-line)] px-3 py-2">
        <span className="label-telemetry flex items-center gap-2">
          <span className={`status-led ${live ? "" : "offline"}`} />
          Live Agent Log
        </span>
        <span className="font-mono-data text-[10px] text-[var(--app-muted)]">{steps.length} events</span>
      </div>
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="h-64 overflow-y-auto bg-[var(--app-bg-deep)] px-3 py-2 font-mono-data text-[11px] leading-relaxed"
      >
        {steps.length === 0 && <div className="text-[var(--app-muted)]">Waiting for the orchestrator to start...</div>}
        {steps.map((s, i) => (
          <div key={`${s.agent}-${s.seq}-${i}`} className="flex gap-2 whitespace-pre-wrap break-words">
            <span className="shrink-0 text-[var(--app-muted)]">{timeOf(s)}</span>
            <span className="shrink-0 font-semibold" style={{ color: STATUS_COLOR[s.status] || "var(--app-ink-soft)" }}>
              [{s.agent}]
            </span>
            <span className="text-[var(--app-ink-soft)]">{s.message}</span>
          </div>
        ))}
        {live && (
          <span className="inline-block h-3 w-1.5 animate-pulse bg-[var(--app-accent-cyan)] align-middle" />
        )}
      </div>
    </div>
  );
}
