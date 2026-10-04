import type { Metadata } from "next";
import { fetchFindingServer } from "./data";
import { FindingDetailClient } from "./FindingDetailClient";
import { formatPValue, formatPercent } from "@/lib/utils";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const finding = await fetchFindingServer(id);

  if (!finding) {
    return { title: "Finding — AtmoSpy" };
  }

  const sigLabel =
    finding.significance_classification === "statistically_significant"
      ? "statistically significant"
      : "not statistically significant";
  const description = `${finding.what} in ${finding.where}, ${finding.period_start} to ${finding.period_end}: ${finding.trend_per_year.toFixed(4)} ${finding.trend_units} (${formatPercent(finding.percent_change)} total change), ${sigLabel} (${formatPValue(finding.p_value)}). Real NASA POWER data, deterministic statistics.`;

  return {
    title: `${finding.title} — AtmoSpy`,
    description,
    openGraph: {
      title: finding.title,
      description,
      type: "article",
    },
    twitter: {
      card: "summary_large_image",
      title: finding.title,
      description,
    },
  };
}

export default async function FindingDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <FindingDetailClient id={id} />;
}
