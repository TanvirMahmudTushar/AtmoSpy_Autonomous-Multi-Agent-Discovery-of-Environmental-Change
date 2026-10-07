import { Panel } from "@/components/ui/panel";
import { PixelLinkButton } from "@/components/ui/button";
import { PixelSprite } from "@/components/pixel/PixelSprite";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl px-4 py-20">
      <Panel className="flex flex-col items-center gap-4 py-10 text-center">
        <PixelSprite name="compass" size={48} />
        <div className="label-telemetry">Error 404</div>
        <h1 className="font-display text-[14px] leading-relaxed text-[var(--app-ink)]">Off the map</h1>
        <p className="max-w-sm text-sm text-[var(--app-ink-soft)]">
          This page doesn&apos;t exist. It may have moved, or the link may be mistyped.
        </p>
        <div className="mt-2 flex flex-wrap justify-center gap-3">
          <PixelLinkButton href="/" variant="primary" size="sm">
            Back to start
          </PixelLinkButton>
          <PixelLinkButton href="/findings" variant="ghost" size="sm">
            Browse findings
          </PixelLinkButton>
        </div>
      </Panel>
    </div>
  );
}
