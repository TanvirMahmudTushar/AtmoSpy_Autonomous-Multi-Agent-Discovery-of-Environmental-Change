// Atmosphere scenes: each is a pure function of `level` (0 = the low end of the
// variable's range, 1 = the high end; see lib/changeModel.ts for how a real
// value maps to a level). Coordinates live on a 64x40 pixel grid. Shapes that
// look "random" (rain, snow, droplets) come from fixed tables, never from
// Math.random, so the server and client draw identical markup.

import { Cloud, Disc, R, SCENE_H, SCENE_W, lerpColor, ramp } from "./pixel";
import type { SceneProps } from "./types";

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));

// ---------------------------------------------------------------- temperature

const SNOW = [[20, 7], [30, 12], [40, 5], [47, 17], [24, 18], [36, 21], [14, 14], [56, 10]];

export function TemperatureScene({ level, animated }: SceneProps) {
  const L = clamp01(level);
  const sky = lerpColor("#8ec5ea", "#f2a56b", L);
  const skyTop = lerpColor("#6aa8d8", "#df6a3c", L);
  const cover = lerpColor("#eef5f8", "#6aa84f", ramp(L, 0.05, 0.5));
  const ground = lerpColor(cover, "#cfa860", ramp(L, 0.62, 0.95));
  const groundDark = lerpColor(ground, "#000000", 0.16);
  const canopy = lerpColor(lerpColor("#dfe9ec", "#3f8a3f", ramp(L, 0.1, 0.5)), "#a39a48", ramp(L, 0.65, 0.95));
  const mercury = 3 + Math.round(L * 21);
  const sunR = 2 + Math.round(L * 4);
  const cold = 1 - ramp(L, 0.15, 0.45);
  const heat = ramp(L, 0.55, 0.85);

  return (
    <g>
      <R x={0} y={0} w={SCENE_W} h={16} fill={skyTop} />
      <R x={0} y={16} w={SCENE_W} h={SCENE_H - 16} fill={sky} />

      <Disc cx={50} cy={9} r={sunR + 3} fill="#ffd27a" opacity={0.28 * ramp(L, 0.35, 1)} />
      <Disc cx={50} cy={9} r={sunR} fill={lerpColor("#fff3b5", "#ffb02e", L)} />

      {SNOW.map(([x, y], i) => (
        <R key={i} x={x} y={y} fill="#ffffff" opacity={cold} className={animated ? "scene-anim-twinkle" : undefined} />
      ))}

      {/* hills and ground */}
      <R x={14} y={29} w={20} h={3} fill={groundDark} />
      <R x={17} y={28} w={14} h={1} fill={groundDark} />
      <R x={40} y={30} w={24} h={2} fill={groundDark} />
      <R x={0} y={31} w={SCENE_W} h={9} fill={ground} />
      <R x={0} y={36} w={SCENE_W} h={4} fill={groundDark} opacity={0.35} />

      {/* a tree that greens up and then browns */}
      <R x={25} y={25} w={2} h={6} fill="#6a4a2a" />
      <Disc cx={26} cy={23} r={3} fill={canopy} />

      {/* heat shimmer above the ground */}
      {[27, 25, 23].map((y, i) => (
        <R
          key={y}
          x={36 + i * 2}
          y={y}
          w={7}
          h={1}
          fill="#ffffff"
          opacity={0.45 * heat}
          className={animated ? "scene-anim-shimmer" : undefined}
          style={animated ? { animationDelay: `${i * 0.25}s` } : undefined}
        />
      ))}

      {/* thermometer */}
      <R x={6} y={5} w={6} h={28} fill="#2b2113" />
      <R x={7} y={6} w={4} h={26} fill="#f7fbfd" />
      <R x={8} y={32 - mercury} w={2} h={mercury + 1} fill={lerpColor("#3b82f6", "#e34948", L)} />
      <Disc cx={9} cy={34} r={3} fill="#2b2113" />
      <Disc cx={9} cy={34} r={2} fill={lerpColor("#3b82f6", "#e34948", L)} />
      {[8, 12, 16, 20, 24, 28].map((y) => (
        <R key={y} x={12} y={y} w={2} h={1} fill="#2b2113" />
      ))}
    </g>
  );
}

// -------------------------------------------------------------- precipitation

const RAIN = Array.from({ length: 32 }, (_, i) => ({
  x: 4 + ((i * 37) % 56),
  y: 14 + ((i * 11) % 13),
}));

export function PrecipitationScene({ level, animated }: SceneProps) {
  const L = clamp01(level);
  const sky = lerpColor("#f1e3b6", "#7d94ad", L);
  const soil = lerpColor("#c9a36a", "#5e4126", L);
  const drops = Math.round(2 + L * 30);
  const len = 2 + Math.round(L * 2);
  const water = Math.round(L * 4);

  return (
    <g>
      <R x={0} y={0} w={SCENE_W} h={SCENE_H} fill={sky} />
      <Cloud
        x={14}
        y={4}
        fill={lerpColor("#fff8e6", "#8595a8", L)}
        shade={lerpColor("#efe4c8", "#5e6e82", L)}
      />
      <R x={0} y={34} w={SCENE_W} h={6} fill={soil} />
      <R x={6} y={34 - water} w={52} h={water} fill="#4f8fd1" opacity={0.85} />
      {RAIN.slice(0, drops).map((d, i) => (
        <R
          key={i}
          x={d.x}
          y={d.y}
          w={1}
          h={len}
          fill="#4f8fd1"
          className={animated ? "scene-anim-rain" : undefined}
          style={animated ? { animationDelay: `${(i % 8) * 0.13}s` } : undefined}
        />
      ))}
    </g>
  );
}

// ------------------------------------------------------------------- humidity

const FAR = [4, 4, 5, 6, 6, 7, 7, 6, 5, 5, 4, 3, 3, 4, 4, 5];
const NEAR = [5, 6, 6, 5, 4, 4, 3, 3, 4, 5, 6, 7, 7, 6, 5, 5];
const DROPLETS = Array.from({ length: 24 }, (_, i) => ({ x: 2 + ((i * 29) % 60), y: 4 + ((i * 13) % 26) }));

function Hills({ heights, base, fill }: { heights: number[]; base: number; fill: string }) {
  return (
    <g>
      {heights.map((h, i) => (
        <R key={i} x={i * 4} y={base - h} w={4} h={SCENE_H - (base - h)} fill={fill} />
      ))}
    </g>
  );
}

export function HumidityScene({ level, animated }: SceneProps) {
  const L = clamp01(level);
  const dots = Math.round(2 + L * 22);

  return (
    <g>
      <R x={0} y={0} w={SCENE_W} h={SCENE_H} fill={lerpColor("#a7d8f5", "#cfd6de", L)} />
      <Disc cx={48} cy={8} r={3} fill={lerpColor("#ffe58a", "#f3efe0", L)} opacity={1 - 0.5 * L} />
      <Hills heights={FAR} base={26} fill={lerpColor("#5b8f6b", "#b6c4c2", L * 0.9)} />
      <Hills heights={NEAR} base={33} fill={lerpColor("#3f7a4f", "#9fb3ad", L * 0.85)} />
      <R x={0} y={0} w={SCENE_W} h={SCENE_H} fill="#eef1f3" opacity={0.6 * L} />
      {[29, 32, 35].map((y) => (
        <R key={y} x={0} y={y} w={SCENE_W} h={2} fill="#ffffff" opacity={0.5 * L} />
      ))}
      {DROPLETS.slice(0, dots).map((d, i) => (
        <R
          key={i}
          x={d.x}
          y={d.y}
          w={2}
          h={1}
          fill="#dff1ff"
          opacity={0.9}
          className={animated ? "scene-anim-twinkle" : undefined}
          style={animated ? { animationDelay: `${(i % 6) * 0.3}s` } : undefined}
        />
      ))}
    </g>
  );
}

// --------------------------------------------------------------------- solar

const RAY_ORDER = [0, 6, 3, 9, 1, 7, 4, 10, 2, 8, 5, 11];

export function SolarScene({ level }: SceneProps) {
  const L = clamp01(level);
  const sunR = 2 + Math.round(L * 3);
  const rays = 4 + Math.round(L * 8);
  const rayLen = 1 + Math.round(L * 5);
  const cell = lerpColor("#22315a", "#3f86e0", L);

  return (
    <g>
      <R x={0} y={0} w={SCENE_W} h={SCENE_H} fill={lerpColor("#aeb4be", "#5fb4ee", L)} />
      <g opacity={1 - ramp(L, 0.2, 0.7)}>
        <Cloud x={8} y={3} fill="#cdd2da" shade="#b3b9c4" />
        <Cloud x={30} y={6} fill="#cdd2da" shade="#b3b9c4" />
      </g>
      {RAY_ORDER.slice(0, rays).map((k) => (
        <g key={k} transform={`rotate(${k * 30} 32 11)`}>
          <R x={32} y={11 - (sunR + 2 + rayLen)} w={1} h={rayLen} fill="#ffd94a" />
        </g>
      ))}
      <Disc cx={32} cy={11} r={sunR} fill={lerpColor("#e9e6d6", "#fff2a0", L)} />

      <R x={0} y={38} w={SCENE_W} h={2} fill="#7a6a4a" />
      <R x={31} y={35} w={2} h={3} fill="#4a4f5a" />
      <R x={17} y={27} w={30} h={9} fill="#1c2540" />
      {[0, 1, 2, 3].flatMap((c) =>
        [0, 1].map((r) => (
          <R key={`${c}-${r}`} x={18 + c * 7} y={28 + r * 4} w={6} h={3} fill={cell} />
        )),
      )}
      <R x={19} y={29} w={2} h={1} fill="#ffffff" opacity={0.8 * ramp(L, 0.6, 0.9)} />
    </g>
  );
}

// ----------------------------------------------------------------------- wind

export function WindScene({ level, animated }: SceneProps) {
  const L = clamp01(level);
  const lean = Math.round(L * 3);
  const streaks = Math.round(1 + L * 5);
  const streakLen = 4 + Math.round(L * 10);
  const spin = 6 - 5.3 * L; // seconds per turn: calm is slow, windy is fast
  const STREAKS = [[4, 8], [40, 12], [10, 18], [44, 22], [20, 26], [6, 29]];

  return (
    <g>
      <R x={0} y={0} w={SCENE_W} h={SCENE_H} fill={lerpColor("#d5e6f1", "#9fc1d8", L)} />
      {STREAKS.slice(0, streaks).map(([x, y], i) => (
        <R key={i} x={x} y={y} w={streakLen} h={1} fill="#ffffff" opacity={0.85} />
      ))}
      <R x={0} y={34} w={SCENE_W} h={6} fill="#79ad5c" />
      {Array.from({ length: 12 }, (_, i) => (
        <g key={i} className={animated ? "scene-anim-sway" : undefined} style={animated ? { animationDelay: `${(i % 5) * 0.2}s` } : undefined}>
          <R x={4 + i * 5} y={32} w={1} h={2} fill="#4f8a3a" />
          <R x={4 + i * 5 + lean} y={31} w={1} h={1} fill="#4f8a3a" />
        </g>
      ))}
      <R x={31} y={15} w={2} h={19} fill="#e8ecef" />
      <R x={29} y={33} w={6} h={1} fill="#b8c2c8" />
      <g transform={`rotate(${20 + L * 70} 32 14)`}>
        <g
          className={animated ? "scene-anim-spin" : undefined}
          style={animated ? { transformOrigin: "32px 14px", animationDuration: `${spin}s` } : undefined}
        >
          {[0, 120, 240].map((a) => (
            <g key={a} transform={`rotate(${a} 32 14)`}>
              <R x={31.5} y={3} w={1.5} h={10} fill="#f5f7f8" />
            </g>
          ))}
        </g>
      </g>
      <Disc cx={32} cy={14} r={2} fill="#c9d3d9" />
    </g>
  );
}
