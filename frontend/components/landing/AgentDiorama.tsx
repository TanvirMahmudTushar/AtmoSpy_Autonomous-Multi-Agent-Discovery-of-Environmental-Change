"use client";

import { useEffect, useRef, useState } from "react";
import { AGENTS, AGENT_BY_ID, PIPELINE_STAGES, type AgentId } from "./agents";
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
  const [stage, setStage] = useState<{ index: number; topic: string } | null>(null);
  const [toast, setToast] = useState<{ topic: string; count: number } | null>(null);

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
          onStage: (index, topic) => setStage({ index, topic }),
          onFinding: (topic, count) => setToast({ topic, count }),
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

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 3800);
    return () => window.clearTimeout(id);
  }, [toast]);

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

        {!failed && (
          <div className="pointer-events-none absolute bottom-2 left-2 max-w-[calc(100%-1rem)] sm:bottom-3 sm:left-3">
            <div className="hud-panel p-2.5 sm:p-3">
              <div className="label-telemetry flex items-center gap-2">
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-[var(--chart-critical)]" />
                Live investigation
              </div>
              <div className="mt-1 text-sm font-medium text-[var(--app-ink)]" aria-live="polite">
                {stage?.topic ?? "Waiting for the next NASA download…"}
              </div>
              {stage && (
                <div className="mt-1 font-display text-[8px] sm:hidden" style={{ color: AGENT_BY_ID[PIPELINE_STAGES[stage.index]].color }}>
                  {AGENT_BY_ID[PIPELINE_STAGES[stage.index]].tag} · {stage.index + 1}/{PIPELINE_STAGES.length}
                </div>
              )}
              <ol className="mt-2 hidden flex-wrap items-center gap-1 sm:flex" aria-label="Pipeline progress">
                {PIPELINE_STAGES.map((id, i) => {
                  const a = AGENT_BY_ID[id];
                  const active = stage?.index === i;
                  const done = stage !== null && i < stage.index;
                  return (
                    <li key={id} className="flex items-center gap-1">
                      <span
                        className="border-2 px-1.5 py-1 font-display text-[7px] transition-colors duration-300"
                        style={
                          active
                            ? { background: a.color, borderColor: a.color, color: "#070b14" }
                            : done
                              ? { borderColor: a.color, color: a.color }
                              : { borderColor: "var(--app-border)", color: "var(--app-muted)" }
                        }
                        aria-current={active ? "step" : undefined}
                      >
                        {done ? "✓ " : ""}
                        {a.tag}
                      </span>
                      {i < PIPELINE_STAGES.length - 1 && <span className="text-[9px] text-[var(--app-muted)]">›</span>}
                    </li>
                  );
                })}
              </ol>
            </div>
          </div>
        )}

        {toast && (
          <div
            key={toast.count}
            className="pointer-events-none absolute right-2 top-2 max-w-[17rem] sm:right-3 sm:top-3"
            role="status"
          >
            <div className="crew-toast hud-panel p-3">
              <div className="label-telemetry" style={{ color: AGENT_BY_ID.report.color }}>
                ★ Finding #{toast.count} filed
              </div>
              <div className="mt-1 text-sm text-[var(--app-ink)]">{toast.topic}</div>
            </div>
          </div>
        )}

        <div className="label-telemetry pointer-events-none absolute left-3 top-3 hidden sm:block">
          Drag to rotate · Click an agent
        </div>

        {meta && (
          <div className="absolute left-2 right-2 top-2 sm:bottom-3 sm:left-auto sm:right-3 sm:top-auto sm:max-w-sm">
            <div className="hud-panel p-3" style={{ borderColor: meta.color }}>
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
