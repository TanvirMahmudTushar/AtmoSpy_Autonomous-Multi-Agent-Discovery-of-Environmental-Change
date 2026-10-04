"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { api, eventsUrl } from "@/lib/api";
import { useAgentStream } from "@/lib/useAgentStream";
import { PixelButton } from "@/components/ui/button";
import { Panel, PanelTitle } from "@/components/ui/panel";
import { AgentFlowGraph } from "@/components/investigate/AgentFlowGraph";
import { LiveLogConsole } from "@/components/investigate/LiveLogConsole";
import { FindingCard } from "@/components/findings/FindingCard";
import { PixelSprite } from "@/components/pixel/PixelSprite";
import type { FindingSummary } from "@/lib/types";

// The scan runs on the backend regardless of what the browser does, so its id
// is kept in sessionStorage and the stream is re-attached (the SSE endpoint
// replays past steps) when the user navigates away and comes back.
const STORAGE_KEY = "atmospy:discover-id";
const listeners = new Set<() => void>();
let memoryId: string | null = null; // fallback when storage is unavailable (private mode)

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function readStoredId(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return memoryId;
  }
}

function writeStoredId(id: string | null) {
  memoryId = id;
  try {
    if (id) sessionStorage.setItem(STORAGE_KEY, id);
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // keep memoryId only
  }
  listeners.forEach((l) => l());
}

export default function DiscoverPage() {
  const investigationId = useSyncExternalStore(subscribe, readStoredId, () => null);
  const [starting, setStarting] = useState(false);
  const [findings, setFindings] = useState<FindingSummary[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const stream = useAgentStream(investigationId ? eventsUrl("discover", investigationId) : null);

  // Drop a stored id the backend no longer knows (e.g. after a reset).
  useEffect(() => {
    if (!investigationId) return;
    let cancelled = false;
    api.getInvestigation(investigationId).catch(() => {
      if (!cancelled) writeStoredId(null);
    });
    return () => {
      cancelled = true;
    };
  }, [investigationId]);

  async function start() {
    setStarting(true);
    setFindings([]);
    setLoadError(null);
    try {
      const { investigation_id } = await api.startDiscovery();
      writeStoredId(investigation_id);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Failed to start discovery.");
    } finally {
      setStarting(false);
    }
  }

  useEffect(() => {
    if (!stream.done || !investigationId) return;
    let cancelled = false;
    api
      .listFindings({ investigation_id: investigationId, limit: 50 })
      .then((list) => {
        if (!cancelled) {
          setFindings([...list].sort((a, b) => (a.discovery_score?.rank ?? 999) - (b.discovery_score?.rank ?? 999)));
        }
      })
      .catch((err) => !cancelled && setLoadError(err instanceof Error ? err.message : "Failed to load findings."));
    return () => {
      cancelled = true;
    };
  }, [stream.done, investigationId]);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="mb-8 flex items-center gap-3">
        <PixelSprite name="telescope" size={40} />
        <div>
          <h1 className="font-display text-[16px] text-[var(--app-ink)]">Discover Earth Changes</h1>
          <p className="mt-1 text-sm text-[var(--app-ink-soft)]">
            Autonomously scans a curated set of NASA POWER region/variable pairs for statistically significant
            trends, ranked by explicit, displayed criteria — never a hidden AI score.
          </p>
        </div>
      </div>

      {!investigationId && (
        <Panel className="flex flex-col items-center gap-4 py-10 text-center">
          <PixelSprite name="earth" size={56} />
          <p className="max-w-lg text-sm text-[var(--app-ink-soft)]">
            This scans ~16 region/variable combinations end-to-end (data retrieval, quality checks, trend and
            significance testing, spatial and relationship analysis) — it takes roughly a minute.
          </p>
          <PixelButton size="lg" onClick={start} disabled={starting}>
            {starting ? "Starting..." : "Discover Changes"}
          </PixelButton>
        </Panel>
      )}

      {loadError && (
        <Panel className="mt-6 border-[var(--chart-critical)]">
          <p className="text-sm text-[var(--chart-critical)]">{loadError}</p>
        </Panel>
      )}

      {investigationId && !stream.done && (
        <div className="flex flex-col gap-4">
          <PanelTitle>Scanning &mdash; 16 candidates running this pipeline concurrently</PanelTitle>
          <AgentFlowGraph steps={stream.steps} mode="aggregate" />
          <LiveLogConsole steps={stream.steps} live={!stream.done} />
        </div>
      )}

      {investigationId && stream.done && (
        <div>
          <div className="mb-4 flex items-center justify-between">
            <PanelTitle>{findings.length} findings discovered</PanelTitle>
            <PixelButton variant="ghost" size="sm" onClick={() => writeStoredId(null)}>
              Scan again
            </PixelButton>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {findings.map((f) => (
              <FindingCard key={f.id} finding={f} />
            ))}
          </div>
          <details className="mt-8">
            <summary className="cursor-pointer font-display text-[9px] text-[var(--app-muted)]">
              Show full agent log
            </summary>
            <div className="mt-3">
              <LiveLogConsole steps={stream.steps} live={false} />
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
