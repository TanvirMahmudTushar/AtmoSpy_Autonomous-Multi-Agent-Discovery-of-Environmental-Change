"use client";

import { useEffect, useRef, useState } from "react";
import { AGENTS, AGENT_BY_ID, type AgentId } from "./agents";
import type { DioramaHandle } from "./scene";

/**
 * Landing-page 3D "mission crew": the pipeline agents acting out their jobs
 * on a floating island. three.js is loaded lazily so it stays out of the
 * initial bundle. Click a character (or a chip) to see what it is doing.
 */
export function AgentDiorama() {
  const hostRef = useRef<HTMLDivElement>(null);
  const handleRef = useRef<DioramaHandle | null>(null);
  const [selected, setSelected] = useState<AgentId | null>(null);
  const [status, setStatus] = useState("");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    import("./scene")
      .then(({ createDiorama }) => {
        if (cancelled || !hostRef.current) return;
        handleRef.current = createDiorama(hostRef.current, {
          onSelect: (id) => {
            setSelected(id);
            setStatus(id ? (handleRef.current?.getStatus(id) ?? "") : "");
          },
        });
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
      handleRef.current?.dispose();
      handleRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!selected) return;
    const id = window.setInterval(() => setStatus(handleRef.current?.getStatus(selected) ?? ""), 300);
    return () => window.clearInterval(id);
  }, [selected]);

  function choose(id: AgentId) {
    const next = selected === id ? null : id;
    handleRef.current?.select(next);
    setSelected(next);
    setStatus(next ? (handleRef.current?.getStatus(next) ?? "") : "");
  }

  const meta = selected ? AGENT_BY_ID[selected] : null;

  return (
    <div className="flex flex-col gap-4">
      <div className="relative">
        {failed ? (
          <div className="flex h-[380px] items-center justify-center text-sm text-[var(--app-muted)] sm:h-[540px]">
            3D view unavailable in this browser.
          </div>
        ) : (
          <div
            ref={hostRef}
            className="h-[380px] w-full select-none sm:h-[540px]"
            role="img"
            aria-label="Animated 3D scene of the AtmoSpy agents at work on a floating island: a data agent carries satellite downloads to a terminal, a statistics agent types, a trend agent draws on a whiteboard, a spatial agent probes the soil, a skeptic peers through a telescope, and a report agent files findings."
          />
        )}

        <div className="label-telemetry pointer-events-none absolute left-2 top-2 hidden sm:block">
          Drag to rotate · Click an agent
        </div>

        {meta && (
          <div
            className="hud-panel absolute bottom-2 left-2 right-2 p-3 sm:right-auto sm:max-w-sm"
            style={{ borderColor: meta.color }}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="font-display text-[9px] leading-relaxed" style={{ color: meta.color }}>
                {meta.name}
              </span>
              <button
                onClick={() => choose(meta.id)}
                aria-label="Close"
                className="font-display text-[9px] text-[var(--app-muted)] hover:text-[var(--app-ink)]"
              >
                ✕
              </button>
            </div>
            <p className="mt-2 text-xs text-[var(--app-ink-soft)]">{meta.role}</p>
            <p className="mt-2 flex items-center gap-2 font-mono-data text-xs text-[var(--app-ink)]" aria-live="polite">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full" style={{ background: meta.color }} />
              {status}
            </p>
          </div>
        )}
      </div>

      <div className="flex flex-wrap justify-center gap-2">
        {AGENTS.map((a) => (
          <button
            key={a.id}
            onClick={() => choose(a.id)}
            aria-pressed={selected === a.id}
            className="pixel-button flex items-center gap-2 bg-[var(--app-panel)] px-3 py-2 text-[var(--app-ink)]"
          >
            <span className="inline-block h-2.5 w-2.5" style={{ background: a.color }} />
            <span className="font-display text-[8px]">{a.tag}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
