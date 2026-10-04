import type { ComponentType } from "react";
import type { SceneId } from "@/lib/variableMeta";
import { HumidityScene, PrecipitationScene, SolarScene, TemperatureScene, WindScene } from "./climate";
import { GenericScene, SoilScene, WaterMassScene } from "./land";
import { SceneSvg } from "./pixel";
import type { SceneProps } from "./types";

const SCENES: Record<SceneId, ComponentType<SceneProps>> = {
  temperature: TemperatureScene,
  precipitation: PrecipitationScene,
  soil: SoilScene,
  humidity: HumidityScene,
  solar: SolarScene,
  wind: WindScene,
  waterMass: WaterMassScene,
  generic: GenericScene,
};

/**
 * One framed scene at a given level. Has no hooks, so it renders on the server
 * too (and to a static string for the globe's popups). `decorative` hides it
 * from assistive tech when a caller already describes the change in text.
 */
export function SceneFigure({
  scene,
  level,
  width = 192,
  fluid = false,
  animated = false,
  decorative = false,
  label,
}: {
  scene: SceneId;
  level: number;
  width?: number;
  fluid?: boolean;
  animated?: boolean;
  decorative?: boolean;
  label: string;
}) {
  const Art = SCENES[scene] ?? GenericScene;
  return (
    <SceneSvg width={width} label={label} fluid={fluid} decorative={decorative}>
      <Art level={level} animated={animated} />
    </SceneSvg>
  );
}
