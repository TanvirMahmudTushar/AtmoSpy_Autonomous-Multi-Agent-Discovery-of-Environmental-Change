"use client";

import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { SpatialTimelapseChartData } from "@/lib/types";
import { cellSpacing, cellSquare } from "./gridGeo";

const LIGHT_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";
const DARK_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

// Same worker-resolution workaround as SpatialMap.tsx — see the comment
// there for why this static /public copy is required under Next.js.
if (typeof window !== "undefined") {
  maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
}

const COLOR_LOW = "#2a78d6";
const COLOR_MID = "#c9cfdd";
const COLOR_HIGH = "#e34948";
const PLAY_INTERVAL_MS = 900;

type FrameFC = SpatialTimelapseChartData["frames"][string];

// Renders each sampled point as a fixed-size tile at the grid's own spacing,
// so the animation reads as a continuous surface changing color over time
// rather than dots jumping between colors.
function toGridTiles(frame: FrameFC, dLon: number, dLat: number): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: frame.features.map((f) => ({
      type: "Feature",
      geometry: cellSquare(f.geometry.coordinates[0], f.geometry.coordinates[1], dLon, dLat),
      properties: f.properties,
    })),
  };
}

export function SpatialTimelapse({ data }: { data: SpatialTimelapseChartData }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const dataRef = useRef(data);
  useLayoutEffect(() => {
    dataRef.current = data;
  }, [data]);
  const cellSizeRef = useRef({ dLon: 0.625, dLat: 0.5 });

  const [yearIndex, setYearIndex] = useState(0);
  const [playing, setPlaying] = useState(false);

  const years = data.years;
  const currentYear = years[yearIndex];
  const valueMin = data.value_min ?? 0;
  const valueMax = data.value_max ?? 1;

  useEffect(() => {
    if (!containerRef.current) return;
    const isDark = document.documentElement.getAttribute("data-theme") !== "light";

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: isDark ? DARK_STYLE : LIGHT_STYLE,
      center: [0, 20],
      zoom: 1,
      attributionControl: false,
    });
    mapRef.current = map;
    map.on("error", (e) => console.error("MapLibre error:", e.error?.message));
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(containerRef.current);

    map.on("load", () => {
      const d = dataRef.current;
      const firstFrame = d.frames[String(d.years[0])];
      if (!firstFrame || firstFrame.features.length === 0) return;

      const lons = firstFrame.features.map((f) => f.geometry.coordinates[0]);
      const lats = firstFrame.features.map((f) => f.geometry.coordinates[1]);
      map.jumpTo({
        center: [(Math.min(...lons) + Math.max(...lons)) / 2, (Math.min(...lats) + Math.max(...lats)) / 2],
        zoom: 3.5,
      });

      // Fixed grid spacing derived once from the first frame — every frame
      // samples the same cells, just with different values per year.
      const { dLon, dLat } = cellSpacing(lons, lats);
      cellSizeRef.current = { dLon, dLat };
      const firstTiles = toGridTiles(firstFrame, dLon, dLat);

      map.addSource("timelapse", { type: "geojson", data: firstTiles });
      map.addLayer({
        id: "timelapse-fill",
        type: "fill",
        source: "timelapse",
        paint: {
          "fill-color": [
            "interpolate",
            ["linear"],
            ["get", "value"],
            d.value_min ?? 0, COLOR_LOW,
            (d.value_min ?? 0) + ((d.value_max ?? 1) - (d.value_min ?? 0)) / 2, COLOR_MID,
            d.value_max ?? 1, COLOR_HIGH,
          ],
          "fill-opacity": 0.9,
        },
      });
      map.addLayer({
        id: "timelapse-outline",
        type: "line",
        source: "timelapse",
        paint: { "line-color": isDark ? "#ffffff33" : "#00000022", "line-width": 1 },
      });

      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
      map.on("mousemove", "timelapse-fill", (e: maplibregl.MapLayerMouseEvent) => {
        map.getCanvas().style.cursor = "pointer";
        const f = e.features?.[0];
        if (!f) return;
        const p = f.properties as { value: number };
        popup.setLngLat(e.lngLat).setHTML(`<div style="font: 12px sans-serif;">${p.value.toFixed(3)} ${dataRef.current.units}</div>`).addTo(map);
      });
      map.on("mouseleave", "timelapse-fill", () => {
        map.getCanvas().style.cursor = "";
        popup.remove();
      });
    });

    return () => {
      resizeObserver.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Swap the source data whenever the scrubber year changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const frame = data.frames[String(currentYear)];
    if (!frame) return;
    const apply = () => {
      const { dLon, dLat } = cellSizeRef.current;
      (map.getSource("timelapse") as maplibregl.GeoJSONSource | undefined)?.setData(toGridTiles(frame, dLon, dLat));
    };
    if (map.isStyleLoaded() && map.getSource("timelapse")) apply();
    else map.once("load", apply);
  }, [currentYear, data]);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      setYearIndex((i) => (i + 1) % years.length);
    }, PLAY_INTERVAL_MS);
    return () => clearInterval(id);
  }, [playing, years.length]);

  if (years.length === 0) return null;

  return (
    <div className="viz-root">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--chart-ink-secondary)]">
        <span>{data.variable_name} over time, by grid cell</span>
        <span className="flex items-center gap-3">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-8 rounded-sm" style={{ background: `linear-gradient(90deg, ${COLOR_LOW}, ${COLOR_MID}, ${COLOR_HIGH})` }} />
            {valueMin.toFixed(2)} &rarr; {valueMax.toFixed(2)} {data.units}
          </span>
        </span>
      </div>
      <div ref={containerRef} className="h-[380px] w-full rounded-sm border-2 border-[var(--app-border)]/40" />
      <div className="mt-3 flex items-center gap-3">
        <button
          onClick={() => setPlaying((p) => !p)}
          className="pixel-button flex items-center justify-center bg-[var(--app-panel-alt)] px-3 py-1.5 text-[var(--app-ink)]"
          aria-label={playing ? "Pause" : "Play"}
        >
          <span className="font-display text-[9px]">{playing ? "PAUSE" : "PLAY"}</span>
        </button>
        <input
          type="range"
          min={0}
          max={years.length - 1}
          step={1}
          value={yearIndex}
          onChange={(e) => {
            setPlaying(false);
            setYearIndex(Number(e.target.value));
          }}
          className="flex-1 accent-[var(--app-accent-cyan)]"
        />
        <span className="font-mono-data w-14 text-right text-sm text-[var(--app-ink)]">{currentYear}</span>
      </div>
    </div>
  );
}
