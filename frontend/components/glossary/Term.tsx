"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { GLOSSARY, type GlossaryKey } from "@/lib/glossary";

/**
 * An inline science term with a plain-language definition on hover, focus or
 * tap. Keyboard accessible: Tab to it, Enter/Space toggles, Escape closes.
 */
export function Term({ k, children }: { k: GlossaryKey; children?: React.ReactNode }) {
  const entry = GLOSSARY[k];
  const [open, setOpen] = useState(false);
  const id = useId();
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <span ref={ref} className="relative inline" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        onClick={() => setOpen((o) => !o)}
        onFocus={() => setOpen(true)}
        onBlur={(e) => {
          // stay open while focus moves into the popover (its glossary link)
          if (!ref.current?.contains(e.relatedTarget as Node)) setOpen(false);
        }}
        className="cursor-help border-b border-dotted border-current p-0 text-inherit"
      >
        {children ?? entry.term}
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className="absolute bottom-full left-1/2 z-50 mb-2 block w-64 -translate-x-1/2 rounded-sm border-2 border-[var(--app-border)] bg-[var(--app-panel)] p-2.5 text-left text-xs leading-relaxed text-[var(--app-ink-soft)] shadow-lg"
        >
          <span className="block font-display text-[8px] text-[var(--app-ink)]">{entry.term}</span>
          <span className="mt-1 block">{entry.short}</span>
          <Link href={`/learn#${k}`} className="mt-1 block text-[var(--app-accent-cyan)] underline">
            More in the glossary
          </Link>
        </span>
      )}
    </span>
  );
}
