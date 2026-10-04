// Small drawing helpers shared by every scene. Scenes are pure functions of
// `level` — no Math.random, no hooks — so the server and client render the
// same markup and the same scene can be rendered to a static string (globe
// popups) as well as mounted as a component.

import type { CSSProperties, ReactNode } from "react";

export const SCENE_W = 64;
export const SCENE_H = 40;

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

/** Linear blend of two #rrggbb colours; t = 0 gives `a`, t = 1 gives `b`. */
export function lerpColor(a: string, b: string, t: number): string {
  const k = Math.min(1, Math.max(0, t));
  const [ar, ag, ab] = hexToRgb(a);
  const [br, bg, bb] = hexToRgb(b);
  const ch = (x: number, y: number) => Math.round(x + (y - x) * k).toString(16).padStart(2, "0");
  return `#${ch(ar, br)}${ch(ag, bg)}${ch(ab, bb)}`;
}

/** 0 below `from`, 1 above `to`, linear between — for "starts appearing at 0.6". */
export function ramp(x: number, from: number, to: number): number {
  return Math.min(1, Math.max(0, (x - from) / (to - from)));
}

export function R({
  x, y, w = 1, h = 1, fill, opacity, className, style,
}: {
  x: number; y: number; w?: number; h?: number; fill: string; opacity?: number; className?: string;
  style?: CSSProperties;
}) {
  return <rect x={x} y={y} width={w} height={h} fill={fill} opacity={opacity} className={className} style={style} />;
}

/** A filled pixel disc, drawn as one rect per scanline. */
export function Disc({
  cx, cy, r, fill, opacity,
}: { cx: number; cy: number; r: number; fill: string; opacity?: number }) {
  const rows: ReactNode[] = [];
  for (let dy = -r; dy <= r; dy++) {
    const half = Math.floor(Math.sqrt(r * r - dy * dy + 0.25));
    rows.push(<rect key={dy} x={cx - half} y={cy + dy} width={half * 2 + 1} height={1} fill={fill} />);
  }
  return <g opacity={opacity}>{rows}</g>;
}

/**
 * A cloud from a fixed set of rows, so its shape is identical everywhere.
 * `x`/`y` is the top-left of the cloud's bounding box (36 wide, 10 tall).
 */
export function Cloud({ x, y, fill, shade }: { x: number; y: number; fill: string; shade: string }) {
  const rows: Array<[number, number]> = [
    [10, 14], // [offset, width] per row, top to bottom
    [6, 22],
    [2, 30],
    [0, 36],
    [0, 36],
    [2, 32],
  ];
  return (
    <g>
      {rows.map(([off, w], i) => (
        <rect key={i} x={x + off} y={y + i * 1.5} width={w} height={1.5} fill={i >= 4 ? shade : fill} />
      ))}
    </g>
  );
}

export function SceneSvg({
  width, label, fluid = false, decorative = false, children,
}: { width: number; label: string; fluid?: boolean; decorative?: boolean; children: ReactNode }) {
  return (
    <svg
      viewBox={`0 0 ${SCENE_W} ${SCENE_H}`}
      width={width}
      height={(width * SCENE_H) / SCENE_W}
      shapeRendering="crispEdges"
      role={decorative ? "presentation" : "img"}
      aria-label={decorative ? undefined : label}
      aria-hidden={decorative ? true : undefined}
      style={{ display: "block", maxWidth: "100%", height: "auto", width: fluid ? "100%" : undefined }}
    >
      {!decorative && <title>{label}</title>}
      {children}
    </svg>
  );
}
