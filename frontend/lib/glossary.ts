/**
 * Plain-language definitions of the science terms used across the app, for
 * students and the public. Shown by <Term> popovers and on /learn.
 * Keep each `short` to one or two sentences; `more` is optional depth.
 */
export interface GlossaryEntry {
  term: string;
  short: string;
  more?: string;
  group: "Data" | "Change" | "Statistics";
}

export const GLOSSARY = {
  // ------------------------------------------------------------- data
  variable: {
    term: "Variable",
    group: "Data",
    short: "One measurable property of the Earth system, such as air temperature, rainfall or soil moisture.",
  },
  satellite_mission: {
    term: "Satellite mission",
    group: "Data",
    short: "A spacecraft and its instruments that measure the Earth from orbit, like GPM (rain), OMI (air pollution) or AIRS (temperature).",
  },
  reanalysis: {
    term: "Reanalysis (model)",
    group: "Data",
    short: "A computer model of the atmosphere that is constantly corrected with real observations, giving a complete, gap-free record.",
    more: "MERRA-2 and GLDAS are models of this kind. They fill in places with no instruments, but they can inherit errors from the model or from changes in which observations were fed in.",
  },
  level3: {
    term: "Level-3 data",
    group: "Data",
    short: "Satellite measurements already placed onto a regular map grid and averaged over a day or a month — ready for analysis.",
  },
  grid_cell: {
    term: "Grid cell",
    group: "Data",
    short: "One square of the map grid the data is stored on, for example 1° by 1° (about 110 km across at the equator).",
  },
  area_mean: {
    term: "Area-weighted average",
    group: "Data",
    short: "The average over all grid cells in a region, giving each cell weight for its true area (cells shrink toward the poles).",
  },
  pressure_level: {
    term: "Pressure level",
    group: "Data",
    short: "A height in the atmosphere named by its air pressure: 850 hPa is about 1.5 km up, 500 hPa about 5.5 km, 30 hPa about 24 km (the stratosphere).",
  },
  stratosphere: {
    term: "Stratosphere",
    group: "Data",
    short: "The layer of the atmosphere above the weather, roughly 12 to 50 km up, which holds the ozone layer.",
  },
  aod: {
    term: "Aerosol optical depth",
    group: "Data",
    short: "How much sunlight is blocked by particles such as haze, smoke and dust. 0 is perfectly clear; above 1 is very hazy.",
  },
  no2_column: {
    term: "NO₂ column",
    group: "Data",
    short: "The number of nitrogen dioxide molecules in a column of air above a spot on the ground, a pollutant mostly from traffic and industry.",
  },
  known_break: {
    term: "Known break",
    group: "Data",
    short: "A date when an instrument or the data feeding a model changed. It can create a sudden step that looks like a trend but isn't one.",
  },

  // ----------------------------------------------------------- change
  trend: {
    term: "Trend",
    group: "Change",
    short: "A steady change in one direction over many years, rising or falling, underneath the ups and downs.",
  },
  seasonal_cycle: {
    term: "Seasonal cycle",
    group: "Change",
    short: "The regular pattern that repeats every year, like hot summers and cold winters. It is usually much bigger than any long-term trend.",
  },
  climatology: {
    term: "Climatology (the normal year)",
    group: "Change",
    short: "The average value for each calendar month over the whole record: what a 'normal' January, February, and so on look like.",
  },
  anomaly: {
    term: "Anomaly",
    group: "Change",
    short: "How far a value is from normal for that time of year. Subtracting the seasonal cycle leaves anomalies, where slow trends are easier to see.",
  },
  change_point: {
    term: "Change point",
    group: "Change",
    short: "A moment where the average level jumps up or down suddenly, rather than changing gradually.",
  },
  effect_size: {
    term: "Effect size",
    group: "Change",
    short: "How big the total change is compared with normal year-to-year variation. Above about 0.8 is a large change; below 0.2 is small.",
  },
  opposite_trends: {
    term: "Opposite trends",
    group: "Change",
    short: "The same variable rising in one place and falling in another, sometimes because of the same underlying cause.",
  },

  // ------------------------------------------------------ statistics
  significant: {
    term: "Statistically significant",
    group: "Statistics",
    short: "Unlikely to be produced by random ups and downs alone. Here that means p < 0.05. It does not mean large or important.",
  },
  p_value: {
    term: "p-value",
    group: "Statistics",
    short: "If there were really no trend, the chance of seeing one at least this strong just by luck. Small p (below 0.05) means luck is an unlikely explanation.",
  },
  mann_kendall: {
    term: "Mann-Kendall test",
    group: "Statistics",
    short: "A trend test that counts how often later values are higher than earlier ones. It doesn't need a straight line and isn't fooled by a few extreme values.",
  },
  sens_slope: {
    term: "Sen's slope",
    group: "Statistics",
    short: "The rate of change: the median of the slopes between every pair of points. Robust to outliers, so one extreme year can't drag it.",
  },
  t_test: {
    term: "t-test on the slope",
    group: "Statistics",
    short: "Fits a straight line and asks whether its slope could plausibly be zero, given how scattered the points are.",
  },
  confidence_interval: {
    term: "95% confidence interval",
    group: "Statistics",
    short: "The range the true rate of change most likely lies in. If it doesn't include zero, the trend is significant.",
  },
  autocorrelation: {
    term: "Autocorrelation",
    group: "Statistics",
    short: "When each value resembles the one before it (a warm month is often followed by another warm month). Ignoring it makes trends look more certain than they are.",
  },
  effective_sample_size: {
    term: "Effective sample size",
    group: "Statistics",
    short: "How many truly independent values the data is worth after accounting for autocorrelation, usually fewer than the number of data points.",
  },
  false_discovery_rate: {
    term: "False discovery rate",
    group: "Statistics",
    short: "A correction for testing many things at once. Test 100 places with no real trend and about 5 will look 'significant' by chance; this correction removes most of those.",
  },
  detectability: {
    term: "Years to detect",
    group: "Statistics",
    short: "How many years of data a trend this size typically needs before it stands out from natural variability. A trend can be real but not yet detectable.",
  },
} satisfies Record<string, GlossaryEntry>;

export type GlossaryKey = keyof typeof GLOSSARY;
