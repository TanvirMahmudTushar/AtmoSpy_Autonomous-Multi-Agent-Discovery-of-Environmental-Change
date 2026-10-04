import { cn } from "@/lib/utils";
import { FARM_TILES, TILE_SHEET, type FarmTileName } from "./tinyFarmTiles";

/** Renders one 16x16 tile from the Kenney "Tiny Farm" CC0 spritesheet
 * (public/assets/tiny-farm/tilemap_packed.png — see LICENSE.txt alongside
 * it) at a crisp, scaled-up pixel size via CSS background-position. */
export function TileSprite({
  tile,
  size = 32,
  className,
  title,
}: {
  tile: FarmTileName;
  size?: number;
  className?: string;
  title?: string;
}) {
  const index = FARM_TILES[tile];
  const col = index % TILE_SHEET.cols;
  const row = Math.floor(index / TILE_SHEET.cols);
  const scale = size / TILE_SHEET.tileSize;

  return (
    <div
      role={title ? "img" : undefined}
      aria-label={title}
      title={title}
      className={cn("shrink-0", className)}
      style={{
        width: size,
        height: size,
        backgroundImage: `url(${TILE_SHEET.src})`,
        backgroundPosition: `-${col * TILE_SHEET.tileSize * scale}px -${row * TILE_SHEET.tileSize * scale}px`,
        backgroundSize: `${TILE_SHEET.cols * TILE_SHEET.tileSize * scale}px ${TILE_SHEET.rows * TILE_SHEET.tileSize * scale}px`,
        imageRendering: "pixelated",
      }}
    />
  );
}
