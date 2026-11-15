import { clamp, derivedStops, sampleScale } from "./colorScale";
import type { ColorStop, Variable } from "./types";
import { PARTICLE_BUDGET, strategyForKind, type FieldChannel, type FieldKind, type FieldMotion } from "./visualStrategies";

export type { FieldKind } from "./visualStrategies";

export type Footprint = {
  west: number;
  south: number;
  east: number;
  north: number;
  /** Outer ring of the real boundary, [longitude, latitude]. The rectangle is used only without it. */
  ring?: [number, number][];
};

export const GIOVANNI_FOOTPRINT: Footprint = { west: 11.4, south: 3.75, east: 11.65, north: 3.98 };

export const FIELD_CAPTION: Record<FieldKind, string> = {
  thermal: "One color for the cell, from cold to very hot.",
  "thermal-deep": "Same ramp, more muted: deep soil changes more slowly.",
  moisture: "From dry to saturated soil. One color for the whole cell.",
  "moisture-deep": "Deep moisture, in denser blues, over the same footprint.",
  vapor: "Vapor above the cell. Density follows the measurement, not a wind.",
  runoff: "Runoff intensity. No direction is measured.",
  haze: "Aerosol haze over the cell, from clear sky to dense dust.",
  precipitation: "Precipitation over the cell, only if the catalog publishes it.",
  generic: "Cell mean for a variable without a dedicated rendering.",
};

export type FieldLayer = {
  variableId: string;
  kind: FieldKind;
  channel: FieldChannel;
  t: number | null;
  stops: ColorStop[];
  color: string;
  altitude: number;
  alpha: number;
  outline: "solid" | "double" | "none";
  motion: FieldMotion;
  legend: string;
  chip: string;
  /** Particles are omitted when the month has no measurement, so a gap never becomes a plume. */
  emit: boolean;
  directional: false;
};

export type GlobeField = {
  zoneId: string;
  theme: FieldKind | "neutral";
  accent: string;
  caption: string;
  footprint: Footprint;
  layers: FieldLayer[];
  /** Crossfade length. 0 skips the fade. The renderer does not invent intermediate measurements. */
  transitionMs?: number;
  /** False when the user prefers reduced motion. Pulse and particles stay off. */
  animate?: boolean;
};

export function kindForRole(role: string | undefined): FieldKind | null {
  switch (role) {
    case "soil-temperature":
      return "thermal";
    case "soil-temperature-deep":
      return "thermal-deep";
    case "soil-moisture":
      return "moisture";
    case "soil-moisture-deep":
      return "moisture-deep";
    case "evaporation":
      return "vapor";
    case "runoff":
      return "runoff";
    case "aerosol-optical-depth":
      return "haze";
    case "precipitation":
    case "rain":
      return "precipitation";
    default:
      return role ? "generic" : null;
  }
}

type FootprintSource = { id: string; footprint?: [number, number, number, number]; boundary?: [number, number][] };

export function footprintOf(zone: FootprintSource): Footprint | null {
  if (zone.boundary && zone.boundary.length >= 4) {
    const ring = zone.boundary;
    const lons = ring.map(([lon]) => lon);
    const lats = ring.map(([, lat]) => lat);
    return { west: Math.min(...lons), south: Math.min(...lats), east: Math.max(...lons), north: Math.max(...lats), ring };
  }
  if (zone.footprint?.length === 4) {
    const [west, south, east, north] = zone.footprint;
    return { west, south, east, north };
  }
  if (zone.id === "zone_yaounde") return GIOVANNI_FOOTPRINT;
  return null;
}

export function normalizeValue(value: number | null, scale: { min: number; max: number } | null): number | null {
  if (value == null || !Number.isFinite(value)) return null;
  const min = scale?.min ?? 0;
  const max = scale?.max ?? 1;
  if (max === min) return 0.5;
  return clamp((value - min) / (max - min), 0, 1);
}

const GAP = "#c5ccd1";

export function composeField(input: {
  zone: FootprintSource;
  primary: Variable | null;
  secondaries: Variable[];
  valueOf: (variableId: string) => number | null;
  scaleOf: (variable: Variable) => { min: number; max: number } | null;
}): GlobeField | null {
  const footprint = footprintOf(input.zone);
  if (!footprint || !input.primary) return null;
  const selected = [input.primary, ...input.secondaries];
  const prepared = selected.flatMap((variable) => {
    const kind = kindForRole(variable.role);
    if (!kind) return [];
    const stops = variable.colorScale?.stops?.length ? variable.colorScale.stops : derivedStops(variable.color);
    const t = normalizeValue(input.valueOf(variable.id), input.scaleOf(variable));
    return [{ variable, kind, stops, t, color: t == null ? GAP : sampleScale(stops, t) }];
  });
  if (prepared.length === 0) return null;
  const primaryId = input.primary.id;
  const ordered = [...prepared].sort((a, b) => Number(b.variable.id === primaryId) - Number(a.variable.id === primaryId));
  let particleSlots = 0;
  const layers: FieldLayer[] = ordered.map((item) => {
    const strategy = strategyForKind(item.kind);
    const isPrimary = item.variable.id === primaryId;
    const surfaceSecondary = strategy.channel === "surface" && !isPrimary;
    let channel = surfaceSecondary ? "halo" : strategy.channel;
    const wantsEmit = strategy.particles && item.t != null && channel !== "halo";
    let emit = false;
    if (wantsEmit) {
      if (particleSlots < PARTICLE_BUDGET) {
        particleSlots += 1;
        emit = true;
      } else channel = "halo";
    }
    const alpha = item.t == null ? (channel === "halo" ? 0.35 : 0.16) : channel === "halo" ? 0.55 + item.t * 0.4 : strategy.fillAlpha * (0.62 + 0.38 * item.t);
    return {
      variableId: item.variable.id,
      kind: item.kind,
      channel,
      t: item.t,
      stops: item.stops,
      color: item.color,
      altitude: strategy.altitude,
      alpha,
      outline: channel === "halo" ? "solid" : strategy.outline,
      motion: channel === "halo" ? "still" : strategy.motion,
      legend: strategy.legend,
      chip: strategy.chip,
      emit,
      directional: false as const,
    };
  });
  const theme = kindForRole(input.primary.role) ?? "neutral";
  const lead = prepared.find((item) => item.variable.id === input.primary?.id);
  return {
    zoneId: input.zone.id,
    theme,
    accent: lead?.color ?? input.primary.color,
    caption: theme === "neutral" ? "" : FIELD_CAPTION[theme],
    footprint,
    layers,
  };
}
