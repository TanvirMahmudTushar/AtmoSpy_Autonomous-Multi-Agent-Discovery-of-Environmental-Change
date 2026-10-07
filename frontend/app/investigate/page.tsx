"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, eventsUrl } from "@/lib/api";
import { useAgentStream } from "@/lib/useAgentStream";
import { useStoredId } from "@/lib/useStoredId";
import { Panel, PanelTitle } from "@/components/ui/panel";
import { PixelButton } from "@/components/ui/button";
import { AgentFlowGraph } from "@/components/investigate/AgentFlowGraph";
import { LiveLogConsole } from "@/components/investigate/LiveLogConsole";
import { FindingReport } from "@/components/findings/FindingReport";
import { PixelSprite } from "@/components/pixel/PixelSprite";
import type { FindingDetail } from "@/lib/types";

const EXAMPLES = [
  "Has temperature changed significantly in Bangladesh since 1990?",
  "Find significant changes in soil moisture in the Indo-Gangetic Plain since 2000.",
  "Compare temperature changes between Bangladesh and the Sahel.",
  "Why might soil moisture be decreasing in California's Central Valley?",
];

export default function InvestigatePage() {
  return (
    <Suspense fallback={null}>
      <InvestigatePageInner />
    </Suspense>
  );
}

function InvestigatePageInner() {
  const searchParams = useSearchParams();
  const resumeId = searchParams.get("resume");
  const prefillRegion = searchParams.get("prefill_region");
  const prefillVariable = searchParams.get("prefill_variable");

  const [question, setQuestion] = useState("");
  // The investigation runs on the backend, so its id is kept for the session
  // and re-attached if the user navigates away and back. An explicit
  // ?resume= link takes priority.
  const [storedId, setStoredId] = useStoredId("atmospy:investigation-id");
  const investigationId = resumeId ?? storedId;
  const [submitting, setSubmitting] = useState(false);
  const [finding, setFinding] = useState<FindingDetail | null>(null);
  const [findingError, setFindingError] = useState<string | null>(null);

  const stream = useAgentStream(investigationId ? eventsUrl("investigations", investigationId) : null);

  // Resuming a past investigation: show its original question read-only
  // above the (still-usable) form, so context isn't lost.
  useEffect(() => {
    if (!investigationId) return;
    let cancelled = false;
    api
      .getInvestigation(investigationId)
      .then((inv) => !cancelled && setQuestion((q) => q || inv.question || ""))
      .catch(() => {
        // Stored id the backend no longer knows (e.g. after a reset): forget it.
        if (!cancelled && !resumeId) setStoredId(null);
      });
    return () => {
      cancelled = true;
    };
  }, [investigationId, resumeId, setStoredId]);

  // Arriving from the command palette with a region/variable picked —
  // draft a sensible starting question rather than forcing a blank box.
  // Done during render when the params change (React's "adjust state when a
  // prop changes" pattern) rather than in an effect.
  const prefillKey = `${resumeId}|${prefillRegion}|${prefillVariable}`;
  const [draftedFor, setDraftedFor] = useState<string | null>(null);
  if (draftedFor !== prefillKey) {
    setDraftedFor(prefillKey);
    if (!resumeId) {
      if (prefillRegion && prefillVariable) {
        setQuestion(`Has ${prefillVariable} changed significantly in ${prefillRegion}?`);
      } else if (prefillRegion) {
        setQuestion(`Has anything changed significantly in ${prefillRegion} in recent decades?`);
      } else if (prefillVariable) {
        setQuestion(`Where has ${prefillVariable} changed significantly?`);
      }
    }
  }

  async function submit(q: string) {
    if (!q.trim() || submitting) return;
    setSubmitting(true);
    setFinding(null);
    setFindingError(null);
    try {
      const { investigation_id } = await api.createInvestigation(q.trim());
      setStoredId(investigation_id);
    } catch (err) {
      setFindingError(err instanceof Error ? err.message : "Failed to start investigation.");
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    if (!stream.done || !investigationId || finding || findingError) return;
    let cancelled = false;
    api
      .listFindings({ investigation_id: investigationId, limit: 1 })
      .then((list) => {
        if (cancelled) return;
        if (list.length === 0) {
          setFindingError(
            stream.finalStatus === "insufficient_data"
              ? "Data quality was insufficient to produce a finding for this question — see the agent log above."
              : "No finding was produced — see the agent log above for why."
          );
          return;
        }
        return api.getFinding(list[0].id).then((f) => !cancelled && setFinding(f));
      })
      .catch((err) => !cancelled && setFindingError(err instanceof Error ? err.message : "Failed to load result."));
    return () => {
      cancelled = true;
    };
  }, [stream.done, stream.finalStatus, investigationId, finding, findingError]);

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <div className="mb-8 flex items-center gap-3">
        <PixelSprite name="compass" size={40} />
        <div>
          <h1 className="font-display text-[16px] text-[var(--app-ink)]">Investigate a Question</h1>
          <p className="mt-1 text-sm text-[var(--app-ink-soft)]">
            Ask in plain language. The agents will plan, retrieve real NASA data, run the analysis, and explain it.
          </p>
        </div>
      </div>

      <Panel>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit(question);
          }}
          className="flex flex-col gap-3"
        >
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. Has temperature changed significantly in Bangladesh since 1990?"
            rows={3}
            className="w-full resize-none rounded-sm border-2 border-[var(--app-border)]/40 bg-[var(--app-panel-alt)] p-3 text-sm text-[var(--app-ink)] outline-none focus:border-[var(--app-accent-green)]"
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  type="button"
                  key={ex}
                  onClick={() => setQuestion(ex)}
                  className="rounded-sm border border-[var(--app-border)]/30 px-2 py-1 text-[11px] text-[var(--app-ink-soft)] hover:bg-[var(--app-panel-alt)]"
                >
                  {ex}
                </button>
              ))}
            </div>
            <PixelButton type="submit" disabled={submitting || !question.trim()}>
              {submitting ? "Starting..." : "Investigate"}
            </PixelButton>
          </div>
        </form>
      </Panel>

      {investigationId && (
        <div className="mt-8 flex flex-col gap-4">
          <PanelTitle>The agents at work</PanelTitle>
          <AgentFlowGraph steps={stream.steps} mode="single" />
          <LiveLogConsole steps={stream.steps} live={!stream.done} />
        </div>
      )}

      {findingError && (
        <Panel className="mt-6 border-[var(--chart-critical)]">
          <p className="text-sm text-[var(--chart-critical)]">{findingError}</p>
        </Panel>
      )}

      {finding && (
        <div className="mt-10">
          <FindingReport finding={finding} />
        </div>
      )}
    </div>
  );
}
