"use client";

import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ChangeGlyph, DirectionBadge } from "@/components/change/ChangeGlyph";
import { api } from "@/lib/api";
import { summaryChange } from "@/lib/changeModel";
import type { FindingSummary, RegionInfo } from "@/lib/types";

const DARK_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const LIGHT_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

// Same worker-resolution workaround as SpatialMap.tsx/SpatialTimelapse.tsx.
if (typeof window !== "undefined") {
  maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
}

const COLOR_DECREASING = "#2a78d6";
const COLOR_INCREASING = "#e34948";

interface RegionAgg {
  region_code: string;
  region_name: string;
  lat: number;
  lon: number;
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
  count: number;
  n_increasing: number;
  n_decreasing: number;
  n_significant: number;
  findings: FindingSummary[];
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string);
}

/** The region's most notable change: biggest effect size, with significant findings winning ties. */
function dominantFinding(findings: FindingSummary[]): FindingSummary {
  const score = (f: FindingSummary) =>
    (f.effect_size ?? -1) + (f.significance_classification === "statistically_significant" ? 0.001 : 0);
  return findings.reduce((best, f) => (score(f) > score(best) ? f : best), findings[0]);
}

function aggregateByRegion(findings: FindingSummary[], regions: RegionInfo[]): RegionAgg[] {
  const regionByCode = new Map(regions.map((r) => [r.code, r]));
  const groups = new Map<string, RegionAgg>();

  for (const f of findings) {
    const region = regionByCode.get(f.region_code);
    if (!region) continue;
    let agg = groups.get(f.region_code);
    if (!agg) {
      agg = {
        region_code: f.region_code,
        region_name: region.name,
        lat: region.centroid_lat,
        lon: region.centroid_lon,
        min_lat: region.min_lat,
        max_lat: region.max_lat,
        min_lon: region.min_lon,
        max_lon: region.max_lon,
        count: 0,
        n_increasing: 0,
        n_decreasing: 0,
        n_significant: 0,
        findings: [],
      };
      groups.set(f.region_code, agg);
    }
    agg.count += 1;
    if (f.trend_per_year > 0) agg.n_increasing += 1;
    else agg.n_decreasing += 1;
    if (f.significance_classification === "statistically_significant") agg.n_significant += 1;
    agg.findings.push(f);
  }

  return Array.from(groups.values());
}

// Shades each region's real bounding box (a choropleth) instead of dropping
// a same-sized dot at its centroid, so the marker reflects the area actually
// investigated. A separate point layer carries the finding-count label,
// since a filled shape can't grow/shrink the way a dot's radius used to.
function toRegionShapes(aggs: RegionAgg[]) {
  return {
    type: "FeatureCollection" as const,
    features: aggs.map((a) => ({
      type: "Feature" as const,
      geometry: {
        type: "Polygon" as const,
        coordinates: [
          [
            [a.min_lon, a.min_lat],
            [a.max_lon, a.min_lat],
            [a.max_lon, a.max_lat],
            [a.min_lon, a.max_lat],
            [a.min_lon, a.min_lat],
          ],
        ],
      },
      properties: {
        region_code: a.region_code,
        region_name: a.region_name,
        count: a.count,
        increasing_fraction: a.n_increasing / a.count,
        significant_fraction: a.n_significant / a.count,
      },
    })),
  };
}

function toRegionLabels(aggs: RegionAgg[]) {
  return {
    type: "FeatureCollection" as const,
    features: aggs.map((a) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [a.lon, a.lat] },
      properties: {
        region_code: a.region_code,
        count: a.count,
        increasing_fraction: a.n_increasing / a.count,
        significant_fraction: a.n_significant / a.count,
      },
    })),
  };
}

export function GlobeView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [aggs, setAggs] = useState<RegionAgg[]>([]);
  const [loading, setLoading] = useState(true);
  const aggsRef = useRef<RegionAgg[]>([]);
  useLayoutEffect(() => {
    aggsRef.current = aggs;
  }, [aggs]);
  const openRegionPopupRef = useRef<((agg: RegionAgg, at: maplibregl.LngLatLike) => void) | null>(null);

  useEffect(() => {
    Promise.all([api.listFindings({ limit: 200, unique: true }), api.getRegions()])
      .then(([findings, regions]) => setAggs(aggregateByRegion(findings, regions)))
      .catch(() => setAggs([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const isDark = document.documentElement.getAttribute("data-theme") !== "light";

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: isDark ? DARK_STYLE : LIGHT_STYLE,
      center: [20, 20],
      zoom: 1.2,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.on("error", (e) => console.error("MapLibre error:", e.error?.message));
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");

    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(containerRef.current);

    // Slow auto-rotate until the viewer interacts, so the globe doesn't sit
    // static and dead on first load — stops permanently on any user input.
    let rotating = true;
    const stopRotating = () => {
      rotating = false;
    };
    map.on("mousedown", stopRotating);
    map.on("wheel", stopRotating);
    map.on("touchstart", stopRotating);
    let rafId: number;
    const spin = () => {
      if (rotating) {
        const center = map.getCenter();
        map.jumpTo({ center: [center.lng + 0.06, center.lat] });
      }
      rafId = requestAnimationFrame(spin);
    };
    rafId = requestAnimationFrame(spin);

    const applyData = () => {
      map.setProjection({ type: "globe" });
      const shapes = toRegionShapes(aggsRef.current);
      const labels = toRegionLabels(aggsRef.current);
      const shapeSrc = map.getSource("regions") as maplibregl.GeoJSONSource | undefined;
      if (shapeSrc) {
        shapeSrc.setData(shapes);
        (map.getSource("region-labels") as maplibregl.GeoJSONSource | undefined)?.setData(labels);
        return;
      }
      map.addSource("regions", { type: "geojson", data: shapes });
      map.addSource("region-labels", { type: "geojson", data: labels });
      map.addLayer({
        id: "regions-fill",
        type: "fill",
        source: "regions",
        paint: {
          "fill-color": [
            "interpolate", ["linear"], ["get", "increasing_fraction"],
            0, COLOR_DECREASING, 0.5, "#c9cfdd", 1, COLOR_INCREASING,
          ],
          "fill-opacity": ["interpolate", ["linear"], ["get", "significant_fraction"], 0, 0.35, 1, 0.85],
        },
      });
      map.addLayer({
        id: "regions-outline",
        type: "line",
        source: "regions",
        paint: { "line-color": isDark ? "#ffffff88" : "#00000055", "line-width": 1.5 },
      });
      // A soft glowing "heat blip" sized by finding count, layered on top of
      // the region shape — the shape alone shows true geography but reads as
      // flat and same-sized everywhere, so this brings magnitude back as an
      // immediately visible cue (what a dot's radius used to convey).
      map.addLayer({
        id: "regions-glow",
        type: "circle",
        source: "region-labels",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["get", "count"], 1, 16, 20, 42],
          "circle-color": [
            "interpolate", ["linear"], ["get", "increasing_fraction"],
            0, COLOR_DECREASING, 0.5, "#c9cfdd", 1, COLOR_INCREASING,
          ],
          "circle-blur": 0.7,
          "circle-opacity": ["interpolate", ["linear"], ["get", "significant_fraction"], 0, 0.4, 1, 0.9],
        },
      });
      map.addLayer({
        id: "regions-count-label",
        type: "symbol",
        source: "region-labels",
        layout: {
          "text-field": ["get", "count"],
          "text-size": 12,
          "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
        },
        paint: {
          "text-color": isDark ? "#ffffff" : "#0b0b0b",
          "text-halo-color": isDark ? "#0b0b0b" : "#ffffff",
          "text-halo-width": 1.2,
        },
      });

      let currentPopup: maplibregl.Popup | null = null;
      const openRegionPopup = (agg: RegionAgg, at: maplibregl.LngLatLike) => {
        stopRotating();
        // Each row: the finding's Then -> Now glyph, then what changed in words.
        const listHtml = agg.findings
          .slice(0, 6)
          .map((fd) => {
            const change = summaryChange(fd);
            const glyph = renderToStaticMarkup(
              <ChangeGlyph change={change} size={40} label={`${fd.variable_name}: ${change.sentence}`} />
            );
            return `<a href="/findings/${fd.id}" style="display:flex;align-items:center;gap:8px;margin:6px 0;color:#1c1c1c;text-decoration:none;">${glyph}<span style="font-size:11px;line-height:1.3;"><strong>${escapeHtml(fd.variable_name)}</strong><br/>${escapeHtml(change.sentence)}<br/><span style="color:#666">${fd.significance_classification === "statistically_significant" ? "significant" : "not significant"}</span></span></a>`;
          })
          .join("");
        // The fill and glow layers both fire click, and a marker click can too:
        // keep exactly one popup open. Explicit colours because the popup is
        // always white, while the page text colour follows the theme.
        currentPopup?.remove();
        currentPopup = new maplibregl.Popup({ closeButton: true, maxWidth: "320px" })
          .setLngLat(at)
          .setHTML(
            `<div style="font: 12px sans-serif;color:#1c1c1c;"><strong>${escapeHtml(agg.region_name)}</strong><br/>${agg.count} finding(s), ${agg.n_significant} significant<div style="margin-top:6px;max-height:260px;overflow-y:auto;">${listHtml}</div></div>`
          )
          .addTo(map);
      };
      openRegionPopupRef.current = openRegionPopup;

      const showRegionPopup = (e: maplibregl.MapLayerMouseEvent) => {
        const f = e.features?.[0];
        if (!f) return;
        const code = (f.properties as { region_code: string }).region_code;
        const agg = aggsRef.current.find((a) => a.region_code === code);
        if (agg) openRegionPopup(agg, e.lngLat);
      };
      map.on("click", "regions-fill", showRegionPopup);
      map.on("click", "regions-glow", showRegionPopup);
      map.on("mouseenter", "regions-fill", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseenter", "regions-glow", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", "regions-fill", () => (map.getCanvas().style.cursor = ""));
    };

    if (map.isStyleLoaded()) applyData();
    else map.once("load", applyData);

    return () => {
      cancelAnimationFrame(rafId);
      resizeObserver.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // One glyph marker per region, showing its biggest change (Then -> Now), so
  // the globe shows *what* is changing where, not just how many findings sit there.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    // Two tiers, because ~15 full glyphs on a small globe just pile up: a tiny
    // direction badge at world scale, the full Then -> Now pair once zoomed in.
    const ZOOM_FOR_GLYPHS = 2.4;
    const tiers: Array<{ lo: HTMLElement; hi: HTMLElement }> = [];
    const markers = aggs.map((agg) => {
      const top = dominantFinding(agg.findings);
      const change = summaryChange(top);
      const label = `${agg.region_name}: ${top.variable_name}, ${change.sentence}`;
      const el = document.createElement("div");
      el.style.cursor = "pointer";
      el.innerHTML =
        `<span data-tier="lo" style="display:block;line-height:0;">${renderToStaticMarkup(<DirectionBadge direction={change.direction} size={14} />)}</span>` +
        `<span data-tier="hi" style="display:none;">${renderToStaticMarkup(<ChangeGlyph change={change} size={34} label={label} />)}</span>`;
      el.title = label;
      tiers.push({ lo: el.querySelector('[data-tier="lo"]') as HTMLElement, hi: el.querySelector('[data-tier="hi"]') as HTMLElement });
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        openRegionPopupRef.current?.(agg, [agg.lon, agg.lat]);
      });
      return new maplibregl.Marker({ element: el, anchor: "bottom", offset: [0, -14] })
        .setLngLat([agg.lon, agg.lat])
        .addTo(map);
    });

    const applyTier = () => {
      const zoomedIn = map.getZoom() >= ZOOM_FOR_GLYPHS;
      for (const t of tiers) {
        t.lo.style.display = zoomedIn ? "none" : "block";
        t.hi.style.display = zoomedIn ? "block" : "none";
      }
    };
    applyTier();
    map.on("zoom", applyTier);
    return () => {
      map.off("zoom", applyTier);
      markers.forEach((m) => m.remove());
    };
  }, [aggs]);

  // Push fresh data into the already-mounted map once the fetch resolves.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const shapes = toRegionShapes(aggs);
    const labels = toRegionLabels(aggs);
    const apply = () => {
      (map.getSource("regions") as maplibregl.GeoJSONSource | undefined)?.setData(shapes);
      (map.getSource("region-labels") as maplibregl.GeoJSONSource | undefined)?.setData(labels);
    };
    if (map.isStyleLoaded() && map.getSource("regions")) apply();
    else map.once("load", apply);
  }, [aggs]);

  const totalFindings = aggs.reduce((sum, a) => sum + a.count, 0);

  return (
    <div className="viz-root">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--chart-ink-secondary)]">
        <span>
          {loading ? "Loading global findings..." : `${totalFindings} findings across ${aggs.length} regions`}
        </span>
        <span className="flex items-center gap-3">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: COLOR_INCREASING }} /> increasing-dominant
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: COLOR_DECREASING }} /> decreasing-dominant
          </span>
          <span>
            ▲▼ = direction of the region&apos;s biggest change · zoom in to see it as start → end of record (dashed frame = not significant) · glow = finding count
          </span>
        </span>
      </div>
      <div ref={containerRef} className="h-[560px] w-full rounded-sm border-2 border-[var(--app-border)]/40" />
    </div>
  );
}
