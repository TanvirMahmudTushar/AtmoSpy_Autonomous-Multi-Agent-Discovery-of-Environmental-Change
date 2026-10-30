"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Panel, PanelTitle } from "@/components/ui/panel";
import { PixelButton } from "@/components/ui/button";
import { AgentFlowGraph } from "@/components/investigate/AgentFlowGraph";
import { LiveLogConsole } from "@/components/investigate/LiveLogConsole";
import { FindingReport } from "@/components/findings/FindingReport";
import { ScanTable } from "@/components/detect/ScanResults";
import { Tour } from "@/components/tour/Tour";
import { demoIntro, findingTour, pairTour, scanTour, type Demo, type TourStep } from "@/lib/demos";

const REPLAY_STEP_MS = 180;

export default function DemoPlayerPage() {
  const { id } = useParams<{ id: string }>();
  const [demo, setDemo] = useState<Demo | null>(null);
  const [missing, setMissing] = useState(false);
  const [shown, setShown] = useState(0); // agent steps revealed so far
  const [tourClosed, setTourClosed] = useState(false);

  useEffect(() => {
    fetch(`/demos/${id}.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setDemo)
      .catch(() => setMissing(true));
  }, [id]);

  const steps = demo?.parts.flatMap((p) => p.steps) ?? [];
  const replaying = demo !== null && shown < steps.length;

  // Replay the frozen agent log, one event at a time.
  useEffect(() => {
    if (!replaying) return;
    const t = setTimeout(() => setShown((n) => n + 1), REPLAY_STEP_MS);
    return () => clearTimeout(t);
  }, [replaying, shown]);

  // The captioned tour opens when the replay ends, unless the viewer closed it.
  const touring = demo !== null && !replaying && steps.length > 0 && !tourClosed;

  if (missing) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <Panel>
          <p className="text-sm text-[var(--app-ink-soft)]">
            This demo isn&apos;t available. <Link href="/demos" className="underline">See all demos</Link>.
          </p>
        </Panel>
      </div>
    );
  }
  if (!demo) return <div className="mx-auto max-w-3xl px-4 py-10 text-sm text-[var(--app-muted)]">Loading…</div>;

  const tour: TourStep[] =
    demo.kind === "scan"
      ? scanTour(demo.parts[0])
      : demo.kind === "pair"
        ? pairTour(demo)
        : demo.parts[0].finding
          ? findingTour(demo.parts[0].finding, demoIntro(demo))
          : [];

  return (
    <div className="mx-auto max-w-5xl px-4 pb-48 pt-10">
      <Link href="/demos" className="text-xs text-[var(--app-accent-cyan)] underline">
        ← All demos
      </Link>
      <h1 className="mt-3 font-display text-[16px] text-[var(--app-ink)]">{demo.title}</h1>
      <p className="mt-2 max-w-3xl text-sm text-[var(--app-ink-soft)]">{demo.summary}</p>
      <p className="mt-1 text-[11px] text-[var(--app-muted)]">
        A replay of a real analysis run on {new Date(demo.generated_at).toLocaleDateString()}.
      </p>

      <div className="mt-6 flex flex-col gap-4">
        <PanelTitle>The agents at work</PanelTitle>
        {demo.kind !== "scan" && <AgentFlowGraph steps={steps.slice(0, shown)} mode="single" />}
        <LiveLogConsole steps={steps.slice(0, shown)} live={replaying} />
        {replaying && (
          <div className="flex justify-end">
            <PixelButton type="button" variant="ghost" size="sm" onClick={() => setShown(steps.length)}>
              Skip to the results
            </PixelButton>
          </div>
        )}
      </div>

      {!replaying && (
        <div className="mt-10 flex flex-col gap-10">
          {demo.kind === "scan" && demo.parts[0].scan_results && (
            <ScanTable results={demo.parts[0].scan_results} regionName={demo.parts[0].region ?? "the region"} />
          )}
          {demo.kind !== "scan" &&
            demo.parts.map(
              (p, i) =>
                p.finding && (
                  <div key={i} data-tour={`part-${i}`}>
                    <FindingReport finding={p.finding} />
                  </div>
                ),
            )}
          {!touring && tour.length > 0 && (
            <div className="flex justify-center">
              <PixelButton type="button" variant="gold" onClick={() => setTourClosed(false)}>
                Replay the walkthrough
              </PixelButton>
            </div>
          )}
        </div>
      )}

      {touring && tour.length > 0 && <Tour steps={tour} onClose={() => setTourClosed(true)} />}
    </div>
  );
}
