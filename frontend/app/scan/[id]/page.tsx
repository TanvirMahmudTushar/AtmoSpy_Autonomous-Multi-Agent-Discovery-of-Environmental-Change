"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { BBox, Investigation } from "@/lib/types";
import { Panel } from "@/components/ui/panel";
import { ScanResults } from "@/components/detect/ScanResults";

/** Reopens a region scan ("what is changing here?") by id. */
export default function ScanPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [scan, setScan] = useState<Investigation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getInvestigation(id)
      .then((inv) => (inv.mode === "scan" ? setScan(inv) : setError("That isn't a region scan.")))
      .catch(() => setError("This scan could not be found."));
  }, [id]);

  async function investigate(variableCode: string, start: number, end: number) {
    const plan = (scan?.plan ?? {}) as { region_code?: string; bbox?: number[] };
    const where: { region_code?: string; bbox?: BBox } =
      plan.region_code && !plan.region_code.startsWith("bbox_")
        ? { region_code: plan.region_code }
        : plan.bbox
          ? { bbox: { min_lat: plan.bbox[0], max_lat: plan.bbox[1], min_lon: plan.bbox[2], max_lon: plan.bbox[3] } }
          : {};
    try {
      const { investigation_id } = await api.createStructuredInvestigation({
        variable_code: variableCode,
        ...where,
        start_year: start,
        end_year: end,
      });
      router.push(`/investigate?resume=${investigation_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the investigation.");
    }
  }

  const regionName = (scan?.plan as { region_name?: string } | null)?.region_name ?? "the region";
  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <Link href="/detect" className="text-xs text-[var(--app-accent-cyan)] underline">
        ← New investigation
      </Link>
      <h1 className="mt-3 font-display text-[16px] text-[var(--app-ink)]">What is changing over {regionName}?</h1>
      {error && (
        <Panel className="mt-6 border-[var(--chart-critical)]">
          <p className="text-sm text-[var(--text-critical)]">{error}</p>
        </Panel>
      )}
      {scan && <ScanResults scanId={id} regionName={regionName} onInvestigate={investigate} />}
    </div>
  );
}
