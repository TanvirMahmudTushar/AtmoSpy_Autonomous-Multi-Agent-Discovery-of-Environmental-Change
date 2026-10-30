"use client";

import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { BBox, PlaceType, RegionInfo } from "@/lib/types";

const LIGHT_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";
const DARK_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
// Same worker workaround as components/charts/SpatialMap.tsx.
if (typeof window !== "undefined") {
  maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
}

const MIN_SIDE = 0.5; // degrees: smaller than one data cell is not a region
const MAX_SIDE = 60; // degrees: the cube adapter's limit

export type Where = { region_code: string; bbox?: undefined } | { bbox: BBox; region_code?: undefined };

function boxPolygon(b: BBox): GeoJSON.Polygon {
  return {
    type: "Polygon",
    coordinates: [[
      [b.min_lon, b.min_lat], [b.max_lon, b.min_lat], [b.max_lon, b.max_lat], [b.min_lon, b.max_lat], [b.min_lon, b.min_lat],
    ]],
  };
}

function presetsGeoJSON(regions: RegionInfo[], tags: PlaceType[], selected?: string): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: regions.map((r) => ({
      type: "Feature",
      id: r.code,
      geometry: boxPolygon(r),
      properties: {
        code: r.code,
        name: r.name,
        match: tags.length === 0 || (r.place_tags ?? []).some((t) => tags.includes(t)),
        selected: r.code === selected,
      },
    })),
  };
}

export function validateBox(b: BBox): string | null {
  if (b.min_lat >= b.max_lat || b.min_lon >= b.max_lon) return "Each minimum must be smaller than its maximum.";
  if (b.min_lat < -90 || b.max_lat > 90 || b.min_lon < -180 || b.max_lon > 180) return "Latitude must be within ±90 and longitude within ±180.";
  const h = b.max_lat - b.min_lat;
  const w = b.max_lon - b.min_lon;
  if (h < MIN_SIDE || w < MIN_SIDE) return `Make the box at least ${MIN_SIDE}° on each side (about 55 km).`;
  if (h > MAX_SIDE || w > MAX_SIDE) return `Keep the box under ${MAX_SIDE}° on each side.`;
  return null;
}

const round = (v: number) => Math.round(v * 100) / 100;

export function RegionPicker({
  regions,
  tags,
  value,
  onChange,
}: {
  regions: RegionInfo[];
  tags: PlaceType[];
  value: Where | null;
  onChange: (w: Where) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [boxError, setBoxError] = useState<string | null>(null);
  const latest = useRef({ regions, tags, value, onChange, drawing });
  useLayoutEffect(() => {
    latest.current = { regions, tags, value, onChange, drawing };
  });

  // Mount once (see SpatialMap for why the map is never recreated).
  useEffect(() => {
    if (!containerRef.current) return;
    const isDark = document.documentElement.getAttribute("data-theme") !== "light";
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: isDark ? DARK_STYLE : LIGHT_STYLE,
      center: [20, 15],
      zoom: 0.8,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    const ro = new ResizeObserver(() => map.resize());
    ro.observe(containerRef.current);

    map.on("load", () => {
      const { regions: rs, tags: ts, value: v } = latest.current;
      map.addSource("presets", { type: "geojson", data: presetsGeoJSON(rs, ts, v?.region_code) });
      map.addSource("drawn", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({
        id: "presets-fill", type: "fill", source: "presets",
        paint: {
          "fill-color": ["case", ["get", "selected"], "#1baf7a", ["get", "match"], "#2a78d6", "#898781"],
          "fill-opacity": ["case", ["get", "selected"], 0.45, ["get", "match"], 0.28, 0.08],
        },
      });
      map.addLayer({
        id: "presets-line", type: "line", source: "presets",
        paint: {
          "line-color": ["case", ["get", "selected"], "#1baf7a", ["get", "match"], "#2a78d6", "#898781"],
          "line-width": ["case", ["get", "selected"], 3, 1],
        },
      });
      map.addLayer({ id: "drawn-fill", type: "fill", source: "drawn", paint: { "fill-color": "#1baf7a", "fill-opacity": 0.35 } });
      map.addLayer({ id: "drawn-line", type: "line", source: "drawn", paint: { "line-color": "#1baf7a", "line-width": 3 } });
      if (v?.bbox) setDrawn(map, v.bbox);
    });

    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
    map.on("mousemove", "presets-fill", (e) => {
      if (latest.current.drawing) return;
      map.getCanvas().style.cursor = "pointer";
      const p = e.features?.[0]?.properties as { name: string } | undefined;
      if (p) popup.setLngLat(e.lngLat).setHTML(`<div style="font:12px sans-serif">${p.name}</div>`).addTo(map);
    });
    map.on("mouseleave", "presets-fill", () => {
      map.getCanvas().style.cursor = "";
      popup.remove();
    });
    map.on("click", "presets-fill", (e) => {
      if (latest.current.drawing) return;
      const code = (e.features?.[0]?.properties as { code: string } | undefined)?.code;
      if (code) latest.current.onChange({ region_code: code });
    });

    // Drag to draw a box.
    let start: maplibregl.LngLat | null = null;
    map.on("mousedown", (e) => {
      if (!latest.current.drawing) return;
      e.preventDefault();
      start = e.lngLat;
    });
    map.on("mousemove", (e) => {
      if (!start) return;
      setDrawn(map, cornersToBox(start, e.lngLat));
    });
    map.on("mouseup", (e) => {
      if (!start) return;
      const box = cornersToBox(start, e.lngLat);
      start = null;
      const err = validateBox(box);
      setBoxError(err);
      if (!err) {
        latest.current.onChange({ bbox: box });
        setDrawing(false);
      }
    });

    return () => {
      ro.disconnect();
      popup.remove();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Keep layers in sync with the place type, the selection and draw mode.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      (map.getSource("presets") as maplibregl.GeoJSONSource | undefined)?.setData(
        presetsGeoJSON(regions, tags, value?.region_code),
      );
      if (value?.bbox) setDrawn(map, value.bbox);
      else (map.getSource("drawn") as maplibregl.GeoJSONSource | undefined)?.setData({ type: "FeatureCollection", features: [] });
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
  }, [regions, tags, value]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (drawing) {
      map.dragPan.disable();
      map.getCanvas().style.cursor = "crosshair";
    } else {
      map.dragPan.enable();
      map.getCanvas().style.cursor = "";
    }
  }, [drawing]);

  const matching = regions.filter((r) => tags.length === 0 || (r.place_tags ?? []).some((t) => tags.includes(t)));

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--app-ink-soft)]">
        <button
          type="button"
          onClick={() => setDrawing((d) => !d)}
          aria-pressed={drawing}
          className={`border-2 px-2.5 py-1 font-display text-[8px] ${
            drawing
              ? "border-[var(--app-accent-green)] text-[var(--app-accent-green)]"
              : "border-[var(--app-border)] text-[var(--app-ink)] hover:bg-[var(--app-panel-alt)]"
          }`}
        >
          {drawing ? "Drag on the map to draw…" : "Draw my own box"}
        </button>
        <span>
          or click a <span className="font-semibold text-[#2a78d6]">highlighted</span> region.
        </span>
      </div>
      <div ref={containerRef} className="h-[380px] w-full rounded-sm border-2 border-[var(--app-border)]/40" />
      {boxError && <p className="text-xs text-[var(--text-critical)]">{boxError}</p>}

      <details className="text-xs text-[var(--app-ink-soft)]" open={matching.length > 0 && matching.length <= 12}>
        <summary className="cursor-pointer select-none">Choose from a list instead</summary>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {matching.map((r) => (
            <button
              key={r.code}
              type="button"
              onClick={() => onChange({ region_code: r.code })}
              aria-pressed={value?.region_code === r.code}
              className={`rounded-sm border px-2 py-1 ${
                value?.region_code === r.code
                  ? "border-[var(--app-accent-green)] bg-[var(--app-panel-alt)] text-[var(--app-ink)]"
                  : "border-[var(--app-border)]/30 hover:bg-[var(--app-panel-alt)]"
              }`}
            >
              {r.name}
            </button>
          ))}
        </div>
        <BoxInputs value={value?.bbox} onSubmit={(b) => onChange({ bbox: b })} />
      </details>
    </div>
  );
}

function cornersToBox(a: maplibregl.LngLat, b: maplibregl.LngLat): BBox {
  return {
    min_lat: round(Math.max(-90, Math.min(a.lat, b.lat))),
    max_lat: round(Math.min(90, Math.max(a.lat, b.lat))),
    min_lon: round(Math.max(-180, Math.min(a.lng, b.lng))),
    max_lon: round(Math.min(180, Math.max(a.lng, b.lng))),
  };
}

function setDrawn(map: maplibregl.Map, b: BBox) {
  (map.getSource("drawn") as maplibregl.GeoJSONSource | undefined)?.setData({
    type: "FeatureCollection",
    features: [{ type: "Feature", geometry: boxPolygon(b), properties: {} }],
  });
}

function BoxInputs({ value, onSubmit }: { value?: BBox; onSubmit: (b: BBox) => void }) {
  const [box, setBox] = useState<BBox>(value ?? { min_lat: 10, max_lat: 15, min_lon: 0, max_lon: 5 });
  const [err, setErr] = useState<string | null>(null);
  const field = (k: keyof BBox, label: string) => (
    <label className="flex flex-col gap-0.5">
      <span>{label}</span>
      <input
        type="number"
        step="0.5"
        value={box[k]}
        onChange={(e) => setBox({ ...box, [k]: Number(e.target.value) })}
        className="w-24 rounded-sm border border-[var(--app-border)]/40 bg-[var(--app-panel-alt)] px-1.5 py-1 text-[var(--app-ink)]"
      />
    </label>
  );
  return (
    <form
      className="mt-3 flex flex-wrap items-end gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        const problem = validateBox(box);
        setErr(problem);
        if (!problem) onSubmit(box);
      }}
    >
      {field("min_lat", "South (lat)")}
      {field("max_lat", "North (lat)")}
      {field("min_lon", "West (lon)")}
      {field("max_lon", "East (lon)")}
      <button type="submit" className="rounded-sm border border-[var(--app-border)]/40 px-2 py-1 hover:bg-[var(--app-panel-alt)]">
        Use this box
      </button>
      {err && <span className="w-full text-[var(--text-critical)]">{err}</span>}
    </form>
  );
}
