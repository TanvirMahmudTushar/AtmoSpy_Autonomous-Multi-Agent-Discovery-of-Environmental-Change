"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { FindingReport } from "@/components/findings/FindingReport";
import { Panel } from "@/components/ui/panel";
import type { FindingDetail } from "@/lib/types";

export function FindingDetailClient({ id }: { id: string }) {
  const [finding, setFinding] = useState<FindingDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getFinding(id)
      .then(setFinding)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load finding."));
  }, [id]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      {error && (
        <Panel className="border-[var(--chart-critical)]">
          <p className="text-sm text-[var(--chart-critical)]">{error}</p>
        </Panel>
      )}
      {!finding && !error && <p className="text-sm text-[var(--app-muted)]">Loading...</p>}
      {finding && <FindingReport finding={finding} />}
    </div>
  );
}
