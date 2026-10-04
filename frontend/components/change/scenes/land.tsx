// Ground and water scenes, plus the generic gauge used for any variable that
// has no scene of its own. Same rules as climate.tsx: pure functions of
// `level`, fixed tables instead of randomness.

import { Disc, R, SCENE_H, SCENE_W, lerpColor, ramp } from "./pixel";
import type { SceneProps } from "./types";

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));

// ----------------------------------------------------------------------- soil

const CRACKS = [6, 46, 26, 60, 16, 36, 54];
const MOIST = Array.from({ length: 10 }, (_, i) => ({ x: 3 + ((i * 23) % 58), y: 20 + ((i * 7) % 14) }));

export function SoilScene({ level, animated }: SceneProps) {
  const L = clamp01(level);
  const soil = lerpColor("#dcb878", "#5a3d24", L);
  const stalk = lerpColor("#c9a23a", "#3f9a4a", L);
  const height = 3 + Math.round(L * 9);
  const cracks = Math.round((1 - L) * 7);
  const moist = Math.round(L * 10);
  const water = 2 + Math.round(L * 10);

  return (
    <g>
      <R x={0} y={0} w={SCENE_W} h={16} fill={lerpColor("#f2d58f", "#a9d3ee", L)} />
      <Disc cx={54} cy={7} r={3} fill="#ffcf4a" opacity={1 - ramp(L, 0.3, 0.8)} />

      <R x={0} y={16} w={SCENE_W} h={SCENE_H - 16} fill={soil} />
      <R x={0} y={28} w={SCENE_W} h={SCENE_H - 28} fill={lerpColor(soil, "#000000", 0.12)} />

      {CRACKS.slice(0, cracks).map((x) => (
        <g key={x} opacity={ramp(1 - L, 0.1, 0.6)}>
          <R x={x} y={16} w={1} h={3} fill="#6b4a22" />
          <R x={x + 1} y={19} w={1} h={3} fill="#6b4a22" />
          <R x={x} y={22} w={1} h={2} fill="#6b4a22" />
          <R x={x + 1} y={24} w={1} h={2} fill="#6b4a22" />
        </g>
      ))}

      {MOIST.slice(0, moist).map((d, i) => (
        <R key={i} x={d.x} y={d.y} w={2} h={1} fill="#2d4e7a" opacity={0.7} />
      ))}

      <R x={0} y={SCENE_H - water} w={SCENE_W} h={water} fill="#3b82f6" opacity={0.65} />
      <R x={0} y={SCENE_H - water} w={SCENE_W} h={1} fill="#7db5ff" opacity={0.8} />

      {Array.from({ length: 7 }, (_, i) => {
        const x = 5 + i * 9;
        return (
          <g key={i} className={animated ? "scene-anim-sway" : undefined}>
            <R x={x} y={16 - height} w={2} h={height} fill={stalk} />
            <R x={x - 1} y={16 - height + 2} w={1} h={1} fill={stalk} />
            <R x={x + 2} y={16 - height + 3} w={1} h={1} fill={stalk} />
            <R x={x - 1} y={16 - height} w={4} h={1} fill={lerpColor(stalk, "#ffffff", 0.18)} />
          </g>
        );
      })}
    </g>
  );
}

// ------------------------------------------------------------------ water mass

export function WaterMassScene({ level }: SceneProps) {
  const L = clamp01(level);
  const h = Math.round(L * 28);
  const top = 35 - h;

  return (
    <g>
      <R x={0} y={0} w={SCENE_W} h={SCENE_H} fill={lerpColor("#e8dec4", "#cfe6f4", L)} />
      <R x={0} y={34} w={SCENE_W} h={6} fill="#8f7b55" />
      <R x={20} y={5} w={24} h={31} fill="#2b2113" />
      <R x={21} y={6} w={22} h={29} fill="#f4f9fc" />
      <R x={21} y={top} w={22} h={h} fill={lerpColor("#7fb2dd", "#2b68b0", L)} />
      <R x={21} y={top} w={22} h={1} fill="#c8e2f7" />
      {[10, 15, 20, 25, 30].map((y) => (
        <R key={y} x={16} y={y} w={3} h={1} fill="#2b2113" />
      ))}
      <R x={46} y={top - 1} w={1} h={3} fill="#e34948" />
      <R x={47} y={top} w={1} h={1} fill="#e34948" />
    </g>
  );
}

// -------------------------------------------------------------------- generic

const ARC: Array<[number, number]> = [
  [12, 32], [13, 27], [15, 22], [18, 18], [22, 15], [27, 13], [32, 12],
  [37, 13], [42, 15], [46, 18], [49, 22], [51, 27], [52, 32],
];

export function GenericScene({ level }: SceneProps) {
  const L = clamp01(level);
  return (
    <g>
      <R x={0} y={0} w={SCENE_W} h={SCENE_H} fill="#e6eef4" />
      {ARC.map(([x, y], i) => (
        <R key={i} x={x - 1} y={y - 1} w={2} h={2} fill={lerpColor("#3b82f6", "#e34948", i / (ARC.length - 1))} />
      ))}
      <g transform={`rotate(${-90 + 180 * L} 32 32)`}>
        <R x={31.5} y={15} w={1.5} h={17} fill="#2b2113" />
      </g>
      <Disc cx={32} cy={32} r={2} fill="#2b2113" />
    </g>
  );
}
