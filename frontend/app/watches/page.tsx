"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, eventsUrl } from "@/lib/api";
import { useAuth } from "@/lib/AuthContext";
import { useAgentStream } from "@/lib/useAgentStream";
import { Panel, PanelTitle } from "@/components/ui/panel";
import { PixelButton, PixelLinkButton } from "@/components/ui/button";
import { SignificanceBadge } from "@/components/ui/badge";
import { PixelSprite } from "@/components/pixel/PixelSprite";
import { TrendDialPair } from "@/components/change/TrendDialPair";
import { AgentFlowGraph } from "@/components/investigate/AgentFlowGraph";
import { LiveLogConsole } from "@/components/investigate/LiveLogConsole";
import { formatRelativeTime } from "@/lib/utils";
import type { RegionInfo, VariableInfo, Watch } from "@/lib/types";

const FREQUENCY_OPTIONS = [
  { days: 7, label: "Weekly" },
  { days: 30, label: "Monthly" },
  { days: 90, label: "Quarterly" },
];

function WatchCard({
  watch,
  region,
  variable,
  onDelete,
  onToggle,
  onCheckNow,
  checking,
}: {
  watch: Watch;
  region?: RegionInfo;
  variable?: VariableInfo;
  onDelete: () => void;
  onToggle: () => void;
  onCheckNow: () => void;
  checking: boolean;
}) {
  return (
    <Panel variant="hud" className={!watch.is_active ? "opacity-60" : undefined}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <span className="label-telemetry">{watch.is_active ? "Active watch" : "Paused"}</span>
          <h3 className="mt-1 text-sm text-[var(--app-ink)]">
            {variable?.name ?? watch.variable_code} in {region?.name ?? watch.region_code}
          </h3>
          <p className="mt-1 text-xs text-[var(--app-muted)]">
            Checked every {watch.frequency_days} day{watch.frequency_days === 1 ? "" : "s"} — next check{" "}
            {formatRelativeTime(watch.next_check_at)}
          </p>
        </div>
        {watch.last_significance && <SignificanceBadge classification={watch.last_significance} />}
      </div>

      {watch.last_check_note && (
        <p className="mt-3 rounded-sm border-l-2 border-[var(--app-accent-cyan)] bg-[var(--app-panel-alt)] p-2 text-xs text-[var(--app-ink-soft)]">
          {watch.last_check_note}
          {watch.last_checked_at && <span className="text-[var(--app-muted)]"> — {formatRelativeTime(watch.last_checked_at)}</span>}
        </p>
      )}

      <TrendDialPair
        prevTrend={watch.prev_trend_per_year}
        prevSignificance={watch.prev_significance}
        lastTrend={watch.last_trend_per_year}
        lastSignificance={watch.last_significance}
        units={variable?.units ?? ""}
      />

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <PixelButton onClick={onCheckNow} disabled={checking} size="sm">
          {checking ? "Checking..." : "Check now"}
        </PixelButton>
        {watch.last_finding_id && (
          <PixelLinkButton href={`/findings/${watch.last_finding_id}`} size="sm" variant="ghost">
            View last finding
          </PixelLinkButton>
        )}
        <button
          onClick={onToggle}
          className="rounded-sm border border-[var(--app-border)]/40 px-2.5 py-1.5 text-[11px] text-[var(--app-ink-soft)] hover:bg-[var(--app-panel-alt)]"
        >
          {watch.is_active ? "Pause" : "Resume"}
        </button>
        <button
          onClick={onDelete}
          className="rounded-sm border border-[var(--chart-critical)]/40 px-2.5 py-1.5 text-[11px] text-[var(--chart-critical)] hover:bg-[var(--chart-critical)]/10"
        >
          Delete
        </button>
      </div>
    </Panel>
  );
}

export default function WatchesPage() {
  const { user } = useAuth();
  const [watches, setWatches] = useState<Watch[]>([]);
  const [regions, setRegions] = useState<RegionInfo[]>([]);
  const [variables, setVariables] = useState<VariableInfo[]>([]);
  const [regionCode, setRegionCode] = useState("");
  const [variableCode, setVariableCode] = useState("");
  const [frequencyDays, setFrequencyDays] = useState(30);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [checkingWatchId, setCheckingWatchId] = useState<string | null>(null);
  const [checkingInvestigationId, setCheckingInvestigationId] = useState<string | null>(null);
  const stream = useAgentStream(checkingInvestigationId ? eventsUrl("investigations", checkingInvestigationId) : null);

  useEffect(() => {
    api.getRegions().then(setRegions).catch(() => {});
    api.getVariables().then(setVariables).catch(() => {});
  }, []);

  function refreshWatches() {
    if (!user) return;
    api.listWatches().then(setWatches).catch(() => {});
  }

  useEffect(refreshWatches, [user]);

  useEffect(() => {
    if (!regionCode && regions.length > 0) setRegionCode(regions[0].code);
    if (!variableCode && variables.length > 0) setVariableCode(variables[0].code);
  }, [regions, variables, regionCode, variableCode]);

  // Once a live check-now stream finishes, pull the updated watch snapshot.
  useEffect(() => {
    if (!stream.done || !checkingWatchId) return;
    refreshWatches();
    const t = setTimeout(() => {
      setCheckingWatchId(null);
      setCheckingInvestigationId(null);
    }, 4000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream.done]);

  async function createWatch() {
    if (!regionCode || !variableCode || creating) return;
    setCreating(true);
    setError(null);
    try {
      await api.createWatch(regionCode, variableCode, frequencyDays);
      refreshWatches();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create watch.");
    } finally {
      setCreating(false);
    }
  }

  async function checkNow(watch: Watch) {
    setCheckingWatchId(watch.id);
    setCheckingInvestigationId(null);
    try {
      const { investigation_id } = await api.checkWatchNow(watch.id);
      setCheckingInvestigationId(investigation_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start check.");
      setCheckingWatchId(null);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <div className="mb-8 flex items-center gap-3">
        <PixelSprite name="flag" size={40} />
        <div>
          <h1 className="font-display text-[16px] text-[var(--app-ink)]">Watches</h1>
          <p className="mt-1 text-sm text-[var(--app-ink-soft)]">
            Subscribe to a region and variable — the same investigation pipeline re-runs on a schedule, and flags
            when the result changes.
          </p>
        </div>
      </div>

      {!user && (
        <Panel variant="hud" className="flex flex-col items-center gap-3 py-6 text-center">
          <span className="label-telemetry">Sign in required</span>
          <p className="text-sm text-[var(--app-ink-soft)]">Watches are tied to your account so only you see them.</p>
          <PixelLinkButton href="/signup" size="sm" variant="gold">
            Sign Up
          </PixelLinkButton>
        </Panel>
      )}

      {user && (
        <>
          <Panel className="mb-6">
            <PanelTitle>New watch</PanelTitle>
            <div className="flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1 text-xs text-[var(--app-muted)]">
                Region
                <select
                  value={regionCode}
                  onChange={(e) => setRegionCode(e.target.value)}
                  className="rounded-sm border-2 border-[var(--app-border)]/40 bg-[var(--app-panel-alt)] p-2 text-sm text-[var(--app-ink)]"
                >
                  {regions.map((r) => (
                    <option key={r.code} value={r.code}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-[var(--app-muted)]">
                Variable
                <select
                  value={variableCode}
                  onChange={(e) => setVariableCode(e.target.value)}
                  className="rounded-sm border-2 border-[var(--app-border)]/40 bg-[var(--app-panel-alt)] p-2 text-sm text-[var(--app-ink)]"
                >
                  {variables.map((v) => (
                    <option key={v.code} value={v.code}>
                      {v.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-[var(--app-muted)]">
                Frequency
                <select
                  value={frequencyDays}
                  onChange={(e) => setFrequencyDays(Number(e.target.value))}
                  className="rounded-sm border-2 border-[var(--app-border)]/40 bg-[var(--app-panel-alt)] p-2 text-sm text-[var(--app-ink)]"
                >
                  {FREQUENCY_OPTIONS.map((f) => (
                    <option key={f.days} value={f.days}>
                      {f.label}
                    </option>
                  ))}
                </select>
              </label>
              <PixelButton onClick={createWatch} disabled={creating || !regionCode || !variableCode}>
                {creating ? "Adding..." : "Add watch"}
              </PixelButton>
            </div>
            {error && <p className="mt-3 text-xs text-[var(--chart-critical)]">{error}</p>}
          </Panel>

          {watches.length === 0 && (
            <Panel className="py-10 text-center">
              <p className="text-sm text-[var(--app-ink-soft)]">
                No watches yet. Add one above, or start from a{" "}
                <Link href="/globe" className="text-[var(--app-accent-cyan)] underline">
                  region on the globe
                </Link>
                .
              </p>
            </Panel>
          )}

          <div className="flex flex-col gap-4">
            {watches.map((w) => (
              <div key={w.id}>
                <WatchCard
                  watch={w}
                  region={regions.find((r) => r.code === w.region_code)}
                  variable={variables.find((v) => v.code === w.variable_code)}
                  checking={checkingWatchId === w.id}
                  onDelete={() => api.deleteWatch(w.id).then(refreshWatches)}
                  onToggle={() => api.toggleWatch(w.id).then(refreshWatches)}
                  onCheckNow={() => checkNow(w)}
                />
                {checkingWatchId === w.id && checkingInvestigationId && (
                  <div className="mt-3 flex flex-col gap-3 border-l-4 border-[var(--app-accent-cyan)]/40 pl-4">
                    <AgentFlowGraph steps={stream.steps} mode="single" />
                    <LiveLogConsole steps={stream.steps} live={!stream.done} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
