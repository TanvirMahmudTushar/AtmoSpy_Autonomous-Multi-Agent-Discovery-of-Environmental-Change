import { ImageResponse } from "next/og";
import { fetchFindingServer } from "./data";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "AtmoSpy finding";

const COLORS = {
  bg: "#070b14",
  panel: "#0d1526",
  ink: "#e8edf7",
  muted: "#7c8aa8",
  cyan: "#5fd4d6",
  green: "#7fce8c",
  gold: "#e0b45a",
  clay: "#d98b6e",
};

function StatBlock({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent: string }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        flex: 1,
        borderLeft: `4px solid ${accent}`,
        backgroundColor: COLORS.panel,
        padding: "16px 20px",
      }}
    >
      <div style={{ display: "flex", fontSize: 16, letterSpacing: 2, color: COLORS.muted, textTransform: "uppercase" }}>
        {label}
      </div>
      <div style={{ display: "flex", fontSize: 30, color: COLORS.ink, marginTop: 6, fontWeight: 700 }}>{value}</div>
      {sub && <div style={{ display: "flex", fontSize: 16, color: COLORS.muted, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

export default async function Image({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const finding = await fetchFindingServer(id);

  if (!finding) {
    return new ImageResponse(
      (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: COLORS.bg,
            color: COLORS.ink,
            fontSize: 40,
          }}
        >
          AtmoSpy
        </div>
      ),
      { ...size }
    );
  }

  const significant = finding.significance_classification === "statistically_significant";
  const sigAccent = significant ? COLORS.cyan : COLORS.clay;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          backgroundColor: COLORS.bg,
          padding: 56,
          position: "relative",
        }}
      >
        {/* corner-bracket HUD accents, echoing the site's mission-control theme */}
        <div style={{ position: "absolute", top: 24, left: 24, width: 28, height: 28, borderTop: `3px solid ${COLORS.cyan}`, borderLeft: `3px solid ${COLORS.cyan}`, display: "flex" }} />
        <div style={{ position: "absolute", top: 24, right: 24, width: 28, height: 28, borderTop: `3px solid ${COLORS.cyan}`, borderRight: `3px solid ${COLORS.cyan}`, display: "flex" }} />
        <div style={{ position: "absolute", bottom: 24, left: 24, width: 28, height: 28, borderBottom: `3px solid ${COLORS.cyan}`, borderLeft: `3px solid ${COLORS.cyan}`, display: "flex" }} />
        <div style={{ position: "absolute", bottom: 24, right: 24, width: 28, height: 28, borderBottom: `3px solid ${COLORS.cyan}`, borderRight: `3px solid ${COLORS.cyan}`, display: "flex" }} />

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ display: "flex", width: 14, height: 14, backgroundColor: COLORS.cyan, borderRadius: 2 }} />
          <div style={{ display: "flex", fontSize: 20, letterSpacing: 3, color: COLORS.muted, textTransform: "uppercase" }}>
            AtmoSpy · Finding Record
          </div>
        </div>

        <div
          style={{
            display: "flex",
            fontSize: 48,
            fontWeight: 700,
            color: COLORS.ink,
            marginTop: 24,
            lineHeight: 1.2,
            maxHeight: 130,
            overflow: "hidden",
          }}
        >
          {finding.title}
        </div>

        <div style={{ display: "flex", fontSize: 20, color: COLORS.muted, marginTop: 8 }}>
          {finding.period_start} &rarr; {finding.period_end}
        </div>

        <div style={{ display: "flex", gap: 16, marginTop: 40 }}>
          <StatBlock label="Where" value={finding.where} accent={COLORS.green} />
          <StatBlock
            label="How much"
            value={finding.trend_per_year.toFixed(4)}
            sub={finding.trend_units}
            accent={COLORS.gold}
          />
          <StatBlock
            label="Significance"
            value={significant ? "Significant" : "Not significant"}
            sub={`p = ${finding.p_value.toFixed(4)}`}
            accent={sigAccent}
          />
        </div>

        <div style={{ display: "flex", marginTop: "auto", fontSize: 16, color: COLORS.muted }}>
          Real NASA POWER data · Mann-Kendall trend test · No fabricated numbers
        </div>
      </div>
    ),
    { ...size }
  );
}
