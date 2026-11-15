/** How a published variable is drawn. The color is always the cell mean. */
export type FieldKind =
  | "thermal"
  | "thermal-deep"
  | "moisture"
  | "moisture-deep"
  | "vapor"
  | "runoff"
  | "haze"
  | "precipitation"
  | "generic";

/** A drawing channel. Several variables stay readable because they do not share one opaque fill. */
export type FieldChannel = "surface" | "halo" | "vapor" | "veil" | "rain";

export type FieldMotion = "still" | "pulse" | "rise" | "drift" | "fall";

export type VisualStrategy = {
  kind: FieldKind;
  channel: FieldChannel;
  /** Meters above the ellipsoid. The same footprint is used at every altitude. */
  altitude: number;
  /** Uniform fill of the whole cell. Never a gradient inside the cell. */
  fillAlpha: number;
  outline: "solid" | "double" | "none";
  motion: FieldMotion;
  /** Short name on a chip. */
  chip: string;
  /** One sentence in the legend. */
  legend: string;
  /** True only when the source contains a vector. None of the current series do. */
  directional: false;
  particles: boolean;
};

const REGISTRY: Record<FieldKind, VisualStrategy> = {
  thermal: {
    kind: "thermal",
    channel: "surface",
    altitude: 2400,
    fillAlpha: 0.56,
    outline: "solid",
    motion: "pulse",
    chip: "Thermal",
    legend: "Thermal surface of the cell. The color is the mean, not a fire.",
    directional: false,
    particles: false,
  },
  "thermal-deep": {
    kind: "thermal-deep",
    channel: "surface",
    altitude: 2480,
    fillAlpha: 0.38,
    outline: "double",
    motion: "still",
    chip: "Deep soil",
    legend: "Same cell, muted shade: deep soil changes more slowly.",
    directional: false,
    particles: false,
  },
  moisture: {
    kind: "moisture",
    channel: "surface",
    altitude: 2400,
    fillAlpha: 0.48,
    outline: "solid",
    motion: "still",
    chip: "Moisture",
    legend: "Water held in the soil. This is not rain.",
    directional: false,
    particles: false,
  },
  "moisture-deep": {
    kind: "moisture-deep",
    channel: "surface",
    altitude: 2480,
    fillAlpha: 0.34,
    outline: "double",
    motion: "still",
    chip: "Deep moisture",
    legend: "Deep moisture, denser, over the same footprint.",
    directional: false,
    particles: false,
  },
  runoff: {
    kind: "runoff",
    channel: "surface",
    altitude: 2400,
    fillAlpha: 0.26,
    outline: "solid",
    motion: "pulse",
    chip: "Runoff",
    legend: "Runoff intensity. No direction is measured.",
    directional: false,
    particles: false,
  },
  vapor: {
    kind: "vapor",
    channel: "vapor",
    altitude: 2400,
    fillAlpha: 0.14,
    outline: "solid",
    motion: "rise",
    chip: "Vapor",
    legend: "Vapor rising above the cell. Density follows the measurement.",
    directional: false,
    particles: true,
  },
  haze: {
    kind: "haze",
    channel: "veil",
    altitude: 4200,
    fillAlpha: 0.32,
    outline: "solid",
    motion: "drift",
    chip: "Aerosols",
    legend: "Aerosol haze limited to the cell, from clear sky to dense dust.",
    directional: false,
    particles: true,
  },
  precipitation: {
    kind: "precipitation",
    channel: "rain",
    altitude: 2400,
    fillAlpha: 0.1,
    outline: "solid",
    motion: "fall",
    chip: "Rain",
    legend: "Precipitation over the cell. Inactive until the catalog publishes it.",
    directional: false,
    particles: true,
  },
  generic: {
    kind: "generic",
    channel: "surface",
    altitude: 2400,
    fillAlpha: 0.46,
    outline: "solid",
    motion: "still",
    chip: "Measurement",
    legend: "Cell mean. This role has no dedicated rendering yet.",
    directional: false,
    particles: false,
  },
};

/** At most two particle systems. Further atmospheric variables become an outline. */
export const PARTICLE_BUDGET = 2;

export function strategyForKind(kind: FieldKind): VisualStrategy {
  return REGISTRY[kind];
}

export function strategies(): VisualStrategy[] {
  return Object.values(REGISTRY);
}
