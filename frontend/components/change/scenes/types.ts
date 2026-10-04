export interface SceneProps {
  /** 0 = low end of the variable's range, 1 = high end (see lib/changeModel.ts). */
  level: number;
  /** Turn on ambient loops (rain, turbine, shimmer). Static renders leave it off. */
  animated?: boolean;
}
