"use client";

import { useCallback, useEffect, useState } from "react";
import type { TourStep } from "@/lib/demos";

const AUTO_ADVANCE_MS = 9000;

function reducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * A captioned walk through the page. Each step scrolls to a `data-tour`
 * anchor, highlights it, and can switch the time-series chart to a view.
 * Keyboard: ←/→ to move, Space to play/pause, Esc to close. Captions are
 * announced to screen readers.
 */
export function Tour({ steps, onClose }: { steps: TourStep[]; onClose: () => void }) {
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(!reducedMotion());
  const step = steps[i];

  const go = useCallback((n: number) => setI(Math.max(0, Math.min(steps.length - 1, n))), [steps.length]);

  // Show the step: switch the chart view, scroll to and highlight the anchor.
  useEffect(() => {
    if (!step) return;
    if (step.view) {
      document.querySelector<HTMLElement>(`[data-tour-view="${step.view}"]`)?.click();
    }
    const el = document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
    if (!el) return;
    el.classList.add("tour-highlight");
    el.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "center" });
    return () => el.classList.remove("tour-highlight");
  }, [step]);

  // Playback stops by itself on the last step.
  const autoPlaying = playing && i < steps.length - 1;
  useEffect(() => {
    if (!autoPlaying) return;
    const t = setTimeout(() => go(i + 1), AUTO_ADVANCE_MS);
    return () => clearTimeout(t);
  }, [autoPlaying, i, go]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "ArrowRight") go(i + 1);
      else if (e.key === "ArrowLeft") go(i - 1);
      else if (e.key === "Escape") onClose();
      else if (e.key === " " && !(e.target instanceof HTMLButtonElement)) {
        e.preventDefault();
        setPlaying((p) => !p);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [i, go, onClose]);

  if (!step) return null;
  return (
    <div
      role="region"
      aria-label="Demo walkthrough"
      className="fixed inset-x-0 bottom-4 z-50 mx-auto w-[min(720px,calc(100%-2rem))] rounded-sm border-2 border-[var(--app-accent-gold)] bg-[var(--app-panel)] p-4 shadow-2xl"
    >
      <div className="flex items-start justify-between gap-3">
        <div aria-live="polite">
          <div className="font-display text-[8px] text-[var(--text-warning)]">
            Step {i + 1} of {steps.length}
          </div>
          <div className="mt-1 font-display text-[11px] text-[var(--app-ink)]">{step.title}</div>
          <p className="mt-1.5 text-sm leading-relaxed text-[var(--app-ink-soft)]">{step.text}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close walkthrough"
          className="px-1 text-[var(--app-muted)] hover:text-[var(--app-ink)]"
        >
          ✕
        </button>
      </div>
      <div className="mt-3 flex items-center justify-between gap-2">
        <div className="h-1 flex-1 rounded-sm bg-[var(--chart-grid)]" aria-hidden="true">
          <div
            className="h-1 rounded-sm bg-[var(--app-accent-gold)]"
            style={{ width: `${((i + 1) / steps.length) * 100}%` }}
          />
        </div>
        <div className="flex gap-1.5">
          <TourButton onClick={() => go(i - 1)} disabled={i === 0}>
            ← Back
          </TourButton>
          <TourButton onClick={() => setPlaying(!autoPlaying)} disabled={i === steps.length - 1}>
            {autoPlaying ? "Pause" : "Play"}
          </TourButton>
          <TourButton onClick={() => (i === steps.length - 1 ? onClose() : go(i + 1))}>
            {i === steps.length - 1 ? "Done" : "Next →"}
          </TourButton>
        </div>
      </div>
    </div>
  );
}

function TourButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className="border-2 border-[var(--app-border)] px-2.5 py-1 font-display text-[8px] text-[var(--app-ink)] hover:bg-[var(--app-panel-alt)] disabled:opacity-40"
    />
  );
}
