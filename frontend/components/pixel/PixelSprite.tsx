import { ICONS, PIXEL_COLOR_VARS } from "./icons";

export function PixelSprite({
  name,
  size = 48,
  className,
}: {
  name: keyof typeof ICONS;
  size?: number;
  className?: string;
}) {
  const grid = ICONS[name];
  if (!grid) return null;
  const rows = grid.length;
  const cols = grid[0].length;

  return (
    <svg
      viewBox={`0 0 ${cols} ${rows}`}
      width={size}
      height={(size * rows) / cols}
      className={className}
      shapeRendering="crispEdges"
      role="img"
      aria-label={`${name} pixel icon`}
    >
      {grid.map((row, y) =>
        [...row].map((ch, x) => {
          if (ch === "." || ch === " ") return null;
          const color = PIXEL_COLOR_VARS[ch];
          if (!color) return null;
          return <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill={color} />;
        })
      )}
    </svg>
  );
}
