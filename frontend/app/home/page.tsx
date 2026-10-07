"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";
import { api } from "@/lib/api";
import { Panel, PanelTitle, StatReadout } from "@/components/ui/panel";
import { PixelLinkButton } from "@/components/ui/button";
import { PixelSprite } from "@/components/pixel/PixelSprite";
import type { FindingSummary, Investigation } from "@/lib/types";

const STATUS_COLOR: Record<string, string> = {
  completed: "var(--chart-good)",
  running: "var(--app-accent-cyan)",
  pending: "var(--app-muted)",
  failed: "var(--chart-critical)",
  insufficient_data: "var(--chart-warning)",
};

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export default function HomePage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [findings, setFindings] = useState<FindingSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login?redirect=/home");
    }
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    Promise.all([api.listMyInvestigations(10), api.listFindings({ limit: 6, unique: true })])
      .then(([inv, find]) => {
        setInvestigations(inv);
        setFindings(find);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user]);

  if (authLoading || !user) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-16 text-center text-sm text-[var(--app-muted)]">
        Loading mission console...
      </div>
    );
  }

  const completedCount = investigations.filter((i) => i.status === "completed").length;
  const runningCount = investigations.filter((i) => i.status === "running" || i.status === "pending").length;

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <PixelSprite name="star" size={40} />
          <div>
            <span className="label-telemetry">Welcome back</span>
            <h1 className="font-display text-[18px] text-[var(--app-ink)]">
              {user.display_name || user.email.split("@")[0]}
            </h1>
          </div>
        </div>
        <div className="flex gap-3">
          <PixelLinkButton href="/discover" variant="primary">
            Discover Changes
          </PixelLinkButton>
          <PixelLinkButton href="/investigate" variant="gold">
            Investigate
          </PixelLinkButton>
        </div>
      </div>

      <Panel variant="hud" className="mb-8">
        <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
          <StatReadout label="Investigations run" value={String(investigations.length)} accent="cyan" />
          <StatReadout label="Completed" value={String(completedCount)} accent="green" />
          <StatReadout label="In progress" value={String(runningCount)} accent="gold" />
          <StatReadout
            label="Member since"
            value={new Date(user.created_at).toLocaleDateString(undefined, { month: "short", year: "numeric" })}
            accent="sky"
          />
        </div>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel variant="hud">
          <PanelTitle>Your recent investigations</PanelTitle>
          {loading && <p className="text-sm text-[var(--app-muted)]">Loading...</p>}
          {!loading && investigations.length === 0 && (
            <p className="text-sm text-[var(--app-ink-soft)]">
              No investigations yet.{" "}
              <Link href="/investigate" className="text-[var(--app-accent-cyan)] underline">
                Ask your first question
              </Link>
              .
            </p>
          )}
          <div className="flex flex-col gap-2">
            {investigations.map((inv) => (
              <Link
                key={inv.id}
                href={`/investigate?resume=${inv.id}`}
                className="flex items-center justify-between border-l-2 bg-[var(--app-panel-alt)] px-3 py-2 text-sm hover:brightness-110"
                style={{ borderColor: STATUS_COLOR[inv.status] || "var(--app-muted)" }}
              >
                <span className="truncate text-[var(--app-ink-soft)]">{inv.question || "Discovery scan"}</span>
                <span className="ml-3 shrink-0 font-mono-data text-[10px] text-[var(--app-muted)]">
                  {timeAgo(inv.created_at)}
                </span>
              </Link>
            ))}
          </div>
        </Panel>

        <Panel variant="hud">
          <PanelTitle>Latest findings across the mission</PanelTitle>
          {!loading && findings.length === 0 && (
            <p className="text-sm text-[var(--app-ink-soft)]">
              No findings yet.{" "}
              <Link href="/discover" className="text-[var(--app-accent-cyan)] underline">
                Run a discovery scan
              </Link>
              .
            </p>
          )}
          <div className="flex flex-col gap-2">
            {findings.map((f) => (
              <Link
                key={f.id}
                href={`/findings/${f.id}`}
                className="flex items-center justify-between border-l-2 border-[var(--app-accent-sky)] bg-[var(--app-panel-alt)] px-3 py-2 text-sm hover:brightness-110"
              >
                <span className="truncate text-[var(--app-ink-soft)]">
                  {f.variable_name} &middot; {f.region_name}
                </span>
                <span
                  className="ml-3 shrink-0 font-mono-data text-[10px]"
                  style={{
                    color:
                      f.significance_classification === "statistically_significant"
                        ? "var(--chart-good)"
                        : "var(--app-muted)",
                  }}
                >
                  {f.percent_change !== null ? `${f.percent_change > 0 ? "+" : ""}${f.percent_change.toFixed(1)}%` : "—"}
                </span>
              </Link>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
