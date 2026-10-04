"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { FindingCard } from "@/components/findings/FindingCard";
import { Panel } from "@/components/ui/panel";
import { PixelSprite } from "@/components/pixel/PixelSprite";
import type { FindingSummary } from "@/lib/types";

const SIGNIFICANCE_OPTIONS = [
  { value: "", label: "All" },
  { value: "statistically_significant", label: "Statistically significant" },
  { value: "not_significant", label: "Not significant" },
];

export default function FindingsPage() {
  const [findings, setFindings] = useState<FindingSummary[]>([]);
  const [significance, setSignificance] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .listFindings({ significance: significance || undefined, limit: 100 })
      .then(setFindings)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load findings."))
      .finally(() => setLoading(false));
  }, [significance]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="mb-6 flex items-center gap-3">
        <PixelSprite name="notebook" size={36} />
        <h1 className="font-display text-[16px] text-[var(--app-ink)]">Findings</h1>
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        {SIGNIFICANCE_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setSignificance(opt.value)}
            className={`rounded-sm border-2 px-3 py-1.5 font-display text-[9px] ${
              significance === opt.value
                ? "border-[var(--app-accent-green)] bg-[var(--app-accent-green)] text-[#fbf5e6]"
                : "border-[var(--app-border)]/30 text-[var(--app-ink-soft)]"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-[var(--app-muted)]">Loading findings...</p>}
      {error && (
        <Panel className="border-[var(--chart-critical)]">
          <p className="text-sm text-[var(--chart-critical)]">{error}</p>
        </Panel>
      )}
      {!loading && !error && findings.length === 0 && (
        <Panel className="py-10 text-center">
          <p className="text-sm text-[var(--app-ink-soft)]">
            No findings yet. Run <a href="/discover" className="underline">Discover</a> or{" "}
            <a href="/investigate" className="underline">Investigate a question</a> to produce some.
          </p>
        </Panel>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {findings.map((f) => (
          <FindingCard key={f.id} finding={f} />
        ))}
      </div>
    </div>
  );
}
