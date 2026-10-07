"use client";

import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useLayoutEffect, useRef } from "react";
import type { SpatialMapChartData } from "@/lib/types";
import { cellSpacing, cellSquare } from "./gridGeo";

const LIGHT_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";
const DARK_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

// maplibre-gl locates its worker bundle at runtime via
// `new URL(path, import.meta.url)` inside a dynamically-imported Blob, which
// Next.js's bundlers (both Turbopack and webpack) don't resolve correctly —
// the worker silently never starts, so the map hangs forever on "loading"
// with no error. Pointing it at a static copy in /public sidesteps that
// resolution entirely. (Copied from
// node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs — re-copy after
// upgrading the maplibre-gl version.)
if (typeof window !== "undefined") {
  maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
}

// Diverging pair from the validated chart palette: blue = decreasing, red = increasing.
const COLOR_DECREASING = "#2a78d6";
const COLOR_INCREASING = "#e34948";

// Turns the point-sampled grid into filled tiles sized to the data's own
// sample spacing, so the map reads as a continuous heatmap surface over the
// region rather than dots floating at each sample's centroid.
function toGridTiles(data: SpatialMapChartData): GeoJSON.FeatureCollection {
  const lons = data.features.map((f) => f.geometry.coordinates[0]);
  const lats = data.features.map((f) => f.geometry.coordinates[1]);
  const { dLon, dLat } = cellSpacing(lons, lats);
  const maxAbsSlope = Math.max(...data.features.map((f) => Math.abs(f.properties.slope_per_year)), 1e-9);
  return {
    type: "FeatureCollection",
    features: data.features.map((f) => ({
      type: "Feature",
      geometry: cellSquare(f.geometry.coordinates[0], f.geometry.coordinates[1], dLon, dLat),
      properties: { ...f.properties, magnitude: Math.abs(f.properties.slope_per_year) / maxAbsSlope },
    })),
  };
}

function addCellsLayer(map: maplibregl.Map, data: SpatialMapChartData, isDark: boolean) {
  const tiles = toGridTiles(data);
  if (map.getSource("cells")) {
    (map.getSource("cells") as maplibregl.GeoJSONSource).setData(tiles);
    return;
  }

  map.addSource("cells", { type: "geojson", data: tiles });
  map.addLayer({
    id: "cells-fill",
    type: "fill",
    source: "cells",
    paint: {
      "fill-color": ["case", ["==", ["get", "direction"], "increasing"], COLOR_INCREASING, COLOR_DECREASING],
      "fill-opacity": [
        "*",
        ["case", ["get", "significant"], 0.9, 0.3],
        ["interpolate", ["linear"], ["get", "magnitude"], 0, 0.35, 1, 1],
      ],
    },
  });
  map.addLayer({
    id: "cells-outline",
    type: "line",
    source: "cells",
    paint: { "line-color": isDark ? "#ffffff33" : "#00000022", "line-width": 1 },
  });

  const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
  map.on("mousemove", "cells-fill", (e: maplibregl.MapLayerMouseEvent) => {
    map.getCanvas().style.cursor = "pointer";
    const f = e.features?.[0];
    if (!f) return;
    const p = f.properties as { slope_per_year: number; p_value: number; significant: boolean };
    popup
      .setLngLat(e.lngLat)
      .setHTML(
        `<div style="font: 12px sans-serif;">slope: ${p.slope_per_year.toFixed(4)}/yr<br/>p = ${p.p_value.toFixed(4)}<br/>${p.significant ? "significant" : "not significant"}</div>`
      )
      .addTo(map);
  });
  map.on("mouseleave", "cells-fill", () => {
    map.getCanvas().style.cursor = "";
    popup.remove();
  });
}

export function SpatialMap({ data }: { data: SpatialMapChartData }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const dataRef = useRef(data);
  useLayoutEffect(() => {
    dataRef.current = data;
  }, [data]);

  // Mount the map exactly once per container. Recreating a MapLibre
  // instance on every prop change is expensive and, worse, is not safe
  // under React Strict Mode's dev-only double-invoke (the first instance's
  // in-flight style.json fetch gets aborted by cleanup while the second
  // instance is still initializing, leaving the style permanently
  // unloaded). Data updates instead flow through the effect below via
  // GeoJSONSource.setData.
  useEffect(() => {
    if (!containerRef.current) return;
    const isDark = document.documentElement.getAttribute("data-theme") !== "light";

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: isDark ? DARK_STYLE : LIGHT_STYLE,
      center: [0, 20],
      zoom: 1,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.on("error", (e) => console.error("MapLibre error:", e.error?.message));
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(containerRef.current);

    map.on("load", () => {
      const d = dataRef.current;
      if (d.features.length === 0) return;
      const lons = d.features.map((f) => f.geometry.coordinates[0]);
      const lats = d.features.map((f) => f.geometry.coordinates[1]);
      map.jumpTo({
        center: [(Math.min(...lons) + Math.max(...lons)) / 2, (Math.min(...lats) + Math.max(...lats)) / 2],
        zoom: 3.5,
      });
      addCellsLayer(map, d, isDark);
    });

    return () => {
      resizeObserver.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Data (or a finding switch) after the initial mount: update the source
  // in place once the map/style is ready.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => addCellsLayer(map, data, document.documentElement.getAttribute("data-theme") !== "light");
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [data]);

  return (
    <div className="viz-root">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--chart-ink-secondary)]">
        <span>{data.variable_name} spatial trend by grid cell</span>
        <span className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-full" style={{ background: COLOR_INCREASING }} /> increasing
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-full" style={{ background: COLOR_DECREASING }} /> decreasing
          </span>
          <span>faint = not statistically significant</span>
        </span>
      </div>
      <div ref={containerRef} className="h-[380px] w-full rounded-sm border-2 border-[var(--app-border)]/40" />
    </div>
  );
}
