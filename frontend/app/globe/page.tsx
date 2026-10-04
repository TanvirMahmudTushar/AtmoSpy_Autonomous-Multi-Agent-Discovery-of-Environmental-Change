import { Panel, PanelTitle } from "@/components/ui/panel";
import { PixelSprite } from "@/components/pixel/PixelSprite";
import { GlobeView } from "@/components/charts/GlobeView";

export default function GlobePage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <div className="mb-8 flex items-center gap-3">
        <PixelSprite name="earth" size={40} />
        <div>
          <h1 className="font-display text-[16px] text-[var(--app-ink)]">Global Trends</h1>
          <p className="mt-1 text-sm text-[var(--app-ink-soft)]">
            Every finding this system has produced, plotted where it happened.
          </p>
        </div>
      </div>

      <Panel variant="hud">
        <PanelTitle>World scan</PanelTitle>
        <GlobeView />
        <p className="mt-3 text-xs text-[var(--app-muted)]">
          Click a shaded region for the findings behind it. Each shape covers the area actually investigated, the
          number is how many findings it has, color is which direction dominates, and brightness is how many were
          statistically significant.
        </p>
      </Panel>
    </div>
  );
}
