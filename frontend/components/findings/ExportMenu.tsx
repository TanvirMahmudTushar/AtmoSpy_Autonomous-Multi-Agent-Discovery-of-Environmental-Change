"use client";

import { useState } from "react";
import { PixelSprite } from "@/components/pixel/PixelSprite";
import {
  downloadTextFile,
  findingCsvFilename,
  findingReportFilename,
  findingToBibtex,
  findingToCsv,
  findingToMarkdownReport,
} from "@/lib/export";
import type { FindingDetail } from "@/lib/types";

export function ExportMenu({ finding }: { finding: FindingDetail }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);

  function exportCsv() {
    downloadTextFile(findingCsvFilename(finding), findingToCsv(finding), "text/csv");
    setOpen(false);
  }

  function exportReport() {
    downloadTextFile(findingReportFilename(finding), findingToMarkdownReport(finding), "text/markdown");
    setOpen(false);
  }

  async function copyBibtex() {
    try {
      await navigator.clipboard.writeText(findingToBibtex(finding));
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard blocked — silently no-op, nothing to recover from here */
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/findings/${finding.id}`);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 1800);
    } catch {
      /* clipboard blocked — silently no-op, nothing to recover from here */
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="pixel-button flex items-center gap-1.5 bg-[var(--app-panel-alt)] px-3 py-2 text-[var(--app-ink)]"
      >
        <PixelSprite name="scroll" size={14} />
        <span className="font-display text-[9px]">Export</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="hud-panel absolute right-0 z-50 mt-2 w-56 !rounded-md p-2">
            <button
              onClick={copyLink}
              className="block w-full rounded-sm px-2 py-1.5 text-left text-sm text-[var(--app-ink-soft)] hover:bg-[var(--app-panel-alt)] hover:text-[var(--app-ink)]"
            >
              {linkCopied ? "Link copied ✓" : "Copy shareable link"}
            </button>
            <button
              onClick={exportCsv}
              className="block w-full rounded-sm px-2 py-1.5 text-left text-sm text-[var(--app-ink-soft)] hover:bg-[var(--app-panel-alt)] hover:text-[var(--app-ink)]"
            >
              Download time series (.csv)
            </button>
            <button
              onClick={exportReport}
              className="block w-full rounded-sm px-2 py-1.5 text-left text-sm text-[var(--app-ink-soft)] hover:bg-[var(--app-panel-alt)] hover:text-[var(--app-ink)]"
            >
              Download report (.md)
            </button>
            <button
              onClick={copyBibtex}
              className="block w-full rounded-sm px-2 py-1.5 text-left text-sm text-[var(--app-ink-soft)] hover:bg-[var(--app-panel-alt)] hover:text-[var(--app-ink)]"
            >
              {copied ? "Copied ✓" : "Copy citation (BibTeX)"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
