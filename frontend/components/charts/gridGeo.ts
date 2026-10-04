// Shared geometry helpers for turning NASA POWER's point-sampled grid into
// filled tiles (a real heatmap surface) instead of dots floating at each
// sample's centroid. NASA POWER's native regional-grid resolution is
// ~0.5° lat x 0.625° lon, used as a fallback when a grid has too few
// distinct points to infer spacing from the data itself.
const FALLBACK_D_LON = 0.625;
const FALLBACK_D_LAT = 0.5;

export function cellSpacing(lons: number[], lats: number[]): { dLon: number; dLat: number } {
  const gaps = (values: number[]) => {
    const sorted = Array.from(new Set(values.map((v) => Math.round(v * 1e4) / 1e4))).sort((a, b) => a - b);
    const out: number[] = [];
    for (let i = 1; i < sorted.length; i++) out.push(sorted[i] - sorted[i - 1]);
    return out;
  };
  const lonGaps = gaps(lons);
  const latGaps = gaps(lats);
  return {
    dLon: lonGaps.length ? Math.min(...lonGaps) : FALLBACK_D_LON,
    dLat: latGaps.length ? Math.min(...latGaps) : FALLBACK_D_LAT,
  };
}

export function cellSquare(lon: number, lat: number, dLon: number, dLat: number): GeoJSON.Polygon {
  const hLon = dLon / 2;
  const hLat = dLat / 2;
  return {
    type: "Polygon",
    coordinates: [
      [
        [lon - hLon, lat - hLat],
        [lon + hLon, lat - hLat],
        [lon + hLon, lat + hLat],
        [lon - hLon, lat + hLat],
        [lon - hLon, lat - hLat],
      ],
    ],
  };
}
