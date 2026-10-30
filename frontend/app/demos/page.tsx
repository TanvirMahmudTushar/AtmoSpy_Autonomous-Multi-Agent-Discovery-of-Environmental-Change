"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Panel } from "@/components/ui/panel";
import { PixelSprite } from "@/components/pixel/PixelSprite";
import type { DemoIndexEntry } from "@/lib/demos";

export default function DemosPage() {
  const [demos, setDemos] = useState<DemoIndexEntry[] | null>(null);
  useEffect(() => {
    fetch("/demos/index.json")
      .then((r) => (r.ok ? r.json() : []))
      .then(setDemos)
      .catch(() => setDemos([]));
  }, []);

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <div className="mb-6 flex items-center gap-3">
        <PixelSprite name="compass" size={40} />
        <div>
          <h1 className="font-display text-[16px] text-[var(--app-ink)]">Watch a detective at work</h1>
          <p className="mt-1 text-sm text-[var(--app-ink-soft)]">
            Short guided replays of real investigations. Every number comes from NASA data analyzed by this app.
          </p>
        </div>
      </div>
      {demos === null ? (
        <p className="text-sm text-[var(--app-muted)]">Loading…</p>
      ) : demos.length === 0 ? (
        <Panel>
          <p className="text-sm text-[var(--app-ink-soft)]">
            No demos have been exported yet. Run <code>python -m scripts.export_demos</code> in the backend.
          </p>
        </Panel>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {demos.map((d) => (
            <Link key={d.id} href={`/demos/${d.id}`} className="group">
              <Panel className="h-full transition-colors group-hover:bg-[var(--app-panel-alt)]">
                <div className="font-display text-[10px] text-[var(--app-ink)]">{d.title}</div>
                <p className="mt-2 text-sm leading-relaxed text-[var(--app-ink-soft)]">{d.summary}</p>
                <p className="mt-3 text-[10px] text-[var(--app-muted)]">
                  {d.kind === "scan" ? "Region scan" : d.kind === "pair" ? "Two investigations" : "Investigation"} ·
                  analyzed {new Date(d.generated_at).toLocaleDateString()} ·{" "}
                  <span className="text-[var(--app-accent-cyan)] underline">Watch</span>
                </p>
              </Panel>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
