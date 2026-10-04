// Maps a NASA variable to the scene that illustrates it and the neutral
// words used to describe its change. Keyed on code first, then on keywords in
// the name/units so a newly registered variable still gets a sensible scene
// instead of nothing. Deliberately dependency-free (no "@/" imports) so it can
// be exercised by plain `node --test`.

export type SceneId =
  | "temperature"
  | "precipitation"
  | "soil"
  | "humidity"
  | "solar"
  | "wind"
  | "waterMass"
  | "generic";

export interface VariableMeta {
  scene: SceneId;
  /** Neutral word for the value going up ("warmer") and down ("cooler"). */
  upWord: string;
  downWord: string;
  /** Decimal places that make sense when quoting a change in this variable. */
  decimals: number;
  /** Units as shown to a reader ("°C", "mm/day"). */
  unitLabel: string;
}

const BY_CODE: Record<string, Omit<VariableMeta, "unitLabel">> = {
  T2M: { scene: "temperature", upWord: "warmer", downWord: "cooler", decimals: 2 },
  T2M_MAX: { scene: "temperature", upWord: "warmer", downWord: "cooler", decimals: 2 },
  T2M_MIN: { scene: "temperature", upWord: "warmer", downWord: "cooler", decimals: 2 },
  TS: { scene: "temperature", upWord: "warmer", downWord: "cooler", decimals: 2 },
  PRECTOTCORR: { scene: "precipitation", upWord: "wetter", downWord: "drier", decimals: 2 },
  GWETROOT: { scene: "soil", upWord: "wetter", downWord: "drier", decimals: 3 },
  GWETTOP: { scene: "soil", upWord: "wetter", downWord: "drier", decimals: 3 },
  GWETPROF: { scene: "soil", upWord: "wetter", downWord: "drier", decimals: 3 },
  soil_moisture: { scene: "soil", upWord: "wetter", downWord: "drier", decimals: 3 },
  RH2M: { scene: "humidity", upWord: "more humid", downWord: "less humid", decimals: 1 },
  ALLSKY_SFC_SW_DWN: { scene: "solar", upWord: "sunnier", downWord: "dimmer", decimals: 2 },
  WS2M: { scene: "wind", upWord: "windier", downWord: "calmer", decimals: 2 },
  lwe_thickness: { scene: "waterMass", upWord: "more water mass", downWord: "less water mass", decimals: 1 },
};

const FROM_NAME: Array<[RegExp, Omit<VariableMeta, "unitLabel">]> = [
  [/temperature|thermal|heat/i, BY_CODE.T2M],
  [/precip|rain/i, BY_CODE.PRECTOTCORR],
  [/soil|wetness|moisture/i, BY_CODE.GWETROOT],
  [/humid/i, BY_CODE.RH2M],
  [/irradiance|solar|shortwave|sunlight/i, BY_CODE.ALLSKY_SFC_SW_DWN],
  [/wind/i, BY_CODE.WS2M],
  [/water storage|ice|mass|lwe/i, BY_CODE.lwe_thickness],
];

const GENERIC: Omit<VariableMeta, "unitLabel"> = {
  scene: "generic",
  upWord: "higher",
  downWord: "lower",
  decimals: 2,
};

export function prettyUnits(units: string | null | undefined): string {
  if (!units) return "";
  const u = units.trim();
  if (/^degc$/i.test(u)) return "°C";
  if (/^fraction/i.test(u)) return "(0–1)";
  return u.replace(/\^2/g, "²").replace(/\^3/g, "³").replace(/kw-hr/i, "kWh");
}

export function variableMeta(
  code: string | null | undefined,
  units?: string | null,
  name?: string | null,
): VariableMeta {
  const unitLabel = prettyUnits(units);
  if (code && BY_CODE[code]) return { ...BY_CODE[code], unitLabel };
  const haystack = `${name ?? ""} ${units ?? ""}`;
  for (const [pattern, meta] of FROM_NAME) {
    if (pattern.test(haystack)) return { ...meta, unitLabel };
  }
  return { ...GENERIC, unitLabel };
}
