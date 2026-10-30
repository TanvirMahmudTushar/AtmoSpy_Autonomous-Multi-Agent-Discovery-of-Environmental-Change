"use client";

import { useEffect, useState } from "react";
import { api, eventsUrl } from "@/lib/api";
import { useAgentStream } from "@/lib/useAgentStream";
import { Panel, PanelTitle } from "@/components/ui/panel";
import { AgentFlowGraph } from "@/components/investigate/AgentFlowGraph";
import { LiveLogConsole } from "@/components/investigate/LiveLogConsole";
import { FindingReport } from "@/components/findings/FindingReport";
import type { FindingDetail } from "@/lib/types";

/** Live agent view for one investigation, then its finding report. */
export function InvestigationRun({ investigationId }: { investigationId: string }) {
  const stream = useAgentStream(eventsUrl("investigations", investigationId));
  const [finding, setFinding] = useState<FindingDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  // A new investigation id starts from a clean slate.
  const [shownFor, setShownFor] = useState(investigationId);
  if (shownFor !== investigationId) {
    setShownFor(investigationId);
    setFinding(null);
    setError(null);
  }

  useEffect(() => {
    if (!stream.done || finding || error) return;
    let cancelled = false;
    api
      .listFindings({ investigation_id: investigationId, limit: 1 })
      .then((list) => {
        if (cancelled) return;
        if (list.length === 0) {
          const lastError = [...stream.steps].reverse().find((s) => s.status === "error");
          setError(
            lastError?.message ??
              (stream.finalStatus === "insufficient_data"
                ? "Data quality was insufficient to produce a finding — see the agent log above."
                : "No finding was produced — see the agent log above for why."),
          );
          return;
        }
        return api.getFinding(list[0].id).then((f) => !cancelled && setFinding(f));
      })
      .catch((err) => !cancelled && setError(err instanceof Error ? err.message : "Failed to load result."));
    return () => {
      cancelled = true;
    };
  }, [stream.done, stream.finalStatus, stream.steps, investigationId, finding, error]);

  return (
    <>
      <div className="mt-8 flex flex-col gap-4">
        <PanelTitle>The agents at work</PanelTitle>
        <AgentFlowGraph steps={stream.steps} mode="single" />
        <LiveLogConsole steps={stream.steps} live={!stream.done} />
      </div>
      {error && (
        <Panel className="mt-6 border-[var(--chart-critical)]">
          <p className="text-sm text-[var(--text-critical)]">{error}</p>
        </Panel>
      )}
      {finding && (
        <div className="mt-10">
          <FindingReport finding={finding} />
        </div>
      )}
    </>
  );
}
