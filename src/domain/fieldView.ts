import { clamp, derivedStops, sampleScale } from "./colorScale";
import type { ColorStop, Variable } from "./types";

/** How a variable is drawn on the Yaoundé cell. The color is the cell mean, not a spatial interpolation. */
export type FieldKind = "thermal" | "thermal-deep" | "moisture" | "moisture-deep" | "vapor" | "runoff" | "haze";

export type Footprint = { west: number; south: number; east: number; north: number };

export const GIOVANNI_FOOTPRINT: Footprint = { west: 11.4, south: 3.75, east: 11.65, north: 3.98 };

export const FIELD_CAPTION: Record<FieldKind, string> = {
  thermal: "Dégradé thermique de la maille, du froid au très chaud.",
  "thermal-deep": "Même dégradé, plus sourd : le sol profond change moins vite.",
  moisture: "Du sol sec au sol saturé.",
  "moisture-deep": "Humidité profonde, dans des bleus plus denses.",
  vapor: "Nappe de vapeur au-dessus de l'emprise.",
  runoff: "Filets d'eau : l'intensité suit le ruissellement mesuré.",
  haze: "Voile d'aérosols, du ciel clair à la poussière dense.",
};

const ALTITUDE: Record<FieldKind, "ground" | "mist" | "haze"> = {
  thermal: "ground",
  "thermal-deep": "ground",
  moisture: "ground",
  "moisture-deep": "ground",
  runoff: "ground",
  vapor: "mist",
  haze: "haze",
};

export type FieldRole = "fill" | "rim" | "mist" | "haze";

export type FieldLayer = {
  variableId: string;
  kind: FieldKind;
  role: FieldRole;
  t: number | null;
  stops: ColorStop[];
  color: string;
};

export type GlobeField = {
  zoneId: string;
  theme: FieldKind | "neutral";
  accent: string;
  caption: string;
  footprint: Footprint;
  layers: FieldLayer[];
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
    default:
      return null;
  }
}

export function footprintOf(zone: { id: string; footprint?: [number, number, number, number] }): Footprint | null {
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
  zone: { id: string; footprint?: [number, number, number, number] };
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
  const ground = prepared.filter((item) => ALTITUDE[item.kind] === "ground");
  const primaryGround = ground.find((item) => item.variable.id === input.primary?.id) ?? ground[0];
  const layers: FieldLayer[] = [];
  if (primaryGround) {
    layers.push({ variableId: primaryGround.variable.id, kind: primaryGround.kind, role: "fill", t: primaryGround.t, stops: primaryGround.stops, color: primaryGround.color });
  }
  for (const item of ground) {
    if (item === primaryGround) continue;
    layers.push({ variableId: item.variable.id, kind: item.kind, role: "rim", t: item.t, stops: item.stops, color: item.color });
  }
  for (const item of prepared) {
    const altitude = ALTITUDE[item.kind];
    if (altitude === "ground") continue;
    layers.push({
      variableId: item.variable.id,
      kind: item.kind,
      role: altitude,
      t: item.t,
      stops: item.stops,
      color: item.color,
    });
  }
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
