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
    chip: "Thermique",
    legend: "Surface thermique de la maille. La couleur est la moyenne, pas un feu.",
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
    chip: "Sol profond",
    legend: "Même maille, teinte plus sourde : le sol profond change moins vite.",
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
    chip: "Humidité",
    legend: "Eau contenue dans le sol. Ce n'est pas de la pluie.",
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
    chip: "Humidité profonde",
    legend: "Humidité profonde, plus dense, sur la même emprise.",
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
    chip: "Ruissellement",
    legend: "Intensité du ruissellement. Aucune direction n'est mesurée.",
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
    chip: "Vapeur",
    legend: "Vapeur qui s'élève au-dessus de la maille. La densité suit la mesure.",
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
    chip: "Aérosols",
    legend: "Voile d'aérosols limité à la maille, du ciel clair à la poussière dense.",
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
    chip: "Pluie",
    legend: "Précipitation sur la maille. Inactive tant que le catalogue ne la publie pas.",
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
    chip: "Mesure",
    legend: "Moyenne de la maille. Le rôle n'a pas encore de représentation dédiée.",
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
