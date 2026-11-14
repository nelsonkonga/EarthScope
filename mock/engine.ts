/**
 * Local stand-in for the EarthScope API.
 * Every number below is synthetic. datasetVersion "fixture-1" must never be read as an observation.
 */
import type {
  AssistantAction,
  ChatMessage,
  MapLayer,
  Observation,
  RankingEntry,
  TimeSeries,
  Trend,
  Variable,
  Zone,
} from "../src/domain/types.js";

const activateFor = (variable: Variable | undefined): AssistantAction[] =>
  variable ? [{ type: "ACTIVATE_VARIABLES", variableIds: [variable.id], mode: "replace" }] : [];

export const DATASET = "fixture-1";
const START_YEAR = 2000;
const END_YEAR = 2020;

type Profile = {
  id: string;
  name: string;
  country: string;
  countryCode: string;
  latitude: number;
  longitude: number;
  aliases: string[];
  temperature: { base: number; slope: number } | null;
  precipitation: { base: number; slope: number } | null;
};

const PROFILES: Profile[] = [
  { id: "zone_yaounde", name: "Yaoundé", country: "Cameroun", countryCode: "CM", latitude: 3.8667, longitude: 11.5167, aliases: ["yaounde"], temperature: { base: 23.5, slope: 0.04 }, precipitation: { base: 1500, slope: -8 } },
  { id: "zone_douala", name: "Douala", country: "Cameroun", countryCode: "CM", latitude: 4.0511, longitude: 9.7679, aliases: ["douala"], temperature: { base: 26.2, slope: 0.03 }, precipitation: { base: 3800, slope: -5 } },
  { id: "zone_lagos", name: "Lagos", country: "Nigéria", countryCode: "NG", latitude: 6.5244, longitude: 3.3792, aliases: ["lagos"], temperature: { base: 27.1, slope: 0.055 }, precipitation: { base: 1600, slope: -12 } },
  { id: "zone_nairobi", name: "Nairobi", country: "Kenya", countryCode: "KE", latitude: -1.2921, longitude: 36.8219, aliases: ["nairobi"], temperature: { base: 19.4, slope: 0.02 }, precipitation: { base: 900, slope: -3 } },
  { id: "zone_dakar", name: "Dakar", country: "Sénégal", countryCode: "SN", latitude: 14.7167, longitude: -17.4677, aliases: ["dakar"], temperature: { base: 24.8, slope: 0.045 }, precipitation: { base: 500, slope: -6 } },
  { id: "zone_accra", name: "Accra", country: "Ghana", countryCode: "GH", latitude: 5.6037, longitude: -0.187, aliases: ["accra"], temperature: { base: 26.6, slope: 0.035 }, precipitation: null },
  { id: "zone_addis", name: "Addis-Abeba", country: "Éthiopie", countryCode: "ET", latitude: 9.03, longitude: 38.74, aliases: ["addis", "addis-abeba", "addis abeba"], temperature: { base: 16.2, slope: 0.025 }, precipitation: { base: 1100, slope: -4 } },
  { id: "zone_cap", name: "Le Cap", country: "Afrique du Sud", countryCode: "ZA", latitude: -33.9249, longitude: 18.4241, aliases: ["le cap", "cap", "cape town"], temperature: { base: 16.8, slope: 0.015 }, precipitation: { base: 600, slope: -2 } },
];

const TEMP_ID = "var_surface_temperature";
const PRECIP_ID = "var_precipitation";

export const SUGGESTED_PROMPTS = [
  "Quelles villes se réchauffent le plus rapidement ?",
  "Comment évolue la température à Yaoundé ?",
  "Compare les tendances de température de Yaoundé et de Douala.",
  "Montre-moi les zones où les précipitations diminuent.",
  "Comment cette variable a-t-elle évolué au cours des dernières décennies ?",
];

function yearDate(year: number): string {
  return `${year}-01-01`;
}

export function variables(): Variable[] {
  return [
    {
      id: TEMP_ID,
      name: "Température de surface",
      description: "Série synthétique du jeu d'essai. Ce n'est pas une observation de la Terre.",
      categoryId: "cat_climate",
      unit: "°C",
      color: "#C4553A",
      colorScale: {
        stops: [
          { at: 0, color: "#F6E3D4" },
          { at: 0.5, color: "#E08A5A" },
          { at: 1, color: "#8C2F1B" },
        ],
      },
      scaleMode: "relative",
      displayScale: { min: 16, max: 30 },
      visualizationType: "zone-symbols",
      supportedTemporalResolutions: ["year"],
      defaultResolution: "year",
      availableDateRange: { start: yearDate(START_YEAR), end: yearDate(END_YEAR) },
      aggregationMethod: "valeur annuelle synthétique",
      role: "surface-temperature",
      datasetVersion: DATASET,
    },
    {
      id: PRECIP_ID,
      name: "Précipitations",
      description: "Série synthétique du jeu d'essai. Ce n'est pas une observation de la Terre.",
      categoryId: "cat_climate",
      unit: "mm",
      color: "#2F6F8F",
      colorScale: {
        stops: [
          { at: 0, color: "#E5F0F4" },
          { at: 0.5, color: "#5E9BB3" },
          { at: 1, color: "#1C4558" },
        ],
      },
      scaleMode: "relative",
      displayScale: { min: 200, max: 4000 },
      visualizationType: "zone-symbols",
      supportedTemporalResolutions: ["year"],
      defaultResolution: "year",
      availableDateRange: { start: yearDate(START_YEAR), end: yearDate(END_YEAR) },
      aggregationMethod: "cumul annuel synthétique",
      role: "precipitation",
      datasetVersion: DATASET,
    },
  ];
}

export function categories() {
  return [{ id: "cat_climate", name: "Climat", order: 1 }];
}

function availableIds(profile: Profile): string[] {
  const ids: string[] = [];
  if (profile.temperature) ids.push(TEMP_ID);
  if (profile.precipitation) ids.push(PRECIP_ID);
  return ids;
}

export function zones(): Zone[] {
  return PROFILES.map((profile) => ({
    id: profile.id,
    name: profile.name,
    country: profile.country,
    countryCode: profile.countryCode,
    latitude: profile.latitude,
    longitude: profile.longitude,
    description: "Zone du jeu d'essai. Les coordonnées servent à la navigation, pas de mesure n'y est attachée en dehors des séries synthétiques.",
    aliases: profile.aliases,
    availableVariableIds: availableIds(profile),
  }));
}

function profileOf(zoneId: string): Profile | undefined {
  return PROFILES.find((profile) => profile.id === zoneId);
}

function variableOf(variableId: string): Variable | undefined {
  return variables().find((variable) => variable.id === variableId);
}

function sample(profile: Profile, variableId: string, year: number): Observation | null {
  const variable = variableOf(variableId);
  if (!variable) return null;
  const model = variableId === TEMP_ID ? profile.temperature : profile.precipitation;
  if (!model) return null;
  const unit = variable.unit;
  if (variableId === TEMP_ID && profile.id === "zone_lagos" && year === 2011) {
    return { date: yearDate(year), value: null, status: "missing", unit };
  }
  const value = round(model.base + model.slope * (year - START_YEAR));
  const estimated = variableId === TEMP_ID && profile.id === "zone_dakar" && year === 2015;
  return { date: yearDate(year), value, status: estimated ? "estimated" : "observed", unit };
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}

function regress(points: { year: number; value: number }[]): Trend {
  const unit = "";
  if (points.length < 2) {
    return {
      method: "régression linéaire sur le jeu d'essai",
      periodStart: yearDate(START_YEAR),
      periodEnd: yearDate(END_YEAR),
      sampleCount: points.length,
      direction: "insufficient",
      unit,
    };
  }
  const meanX = points.reduce((sum, point) => sum + point.year, 0) / points.length;
  const meanY = points.reduce((sum, point) => sum + point.value, 0) / points.length;
  let numerator = 0;
  let denominator = 0;
  for (const point of points) {
    numerator += (point.year - meanX) * (point.value - meanY);
    denominator += (point.year - meanX) ** 2;
  }
  const slope = denominator === 0 ? 0 : numerator / denominator;
  const intercept = meanY - slope * meanX;
  const first = points[0].year;
  const last = points[points.length - 1].year;
  const perDecade = slope * 10;
  const direction = Math.abs(perDecade) < 0.05 ? "flat" : perDecade > 0 ? "up" : "down";
  return {
    method: "régression linéaire sur le jeu d'essai",
    periodStart: yearDate(first),
    periodEnd: yearDate(last),
    sampleCount: points.length,
    direction,
    changeOverPeriod: round(slope * (last - first)),
    changePerDecade: round(perDecade),
    unit,
    startValue: round(intercept + slope * first),
    endValue: round(intercept + slope * last),
  };
}

export function seriesFor(zoneId: string, variableId: string, resolution = "year"): TimeSeries | "zone" | "variable" | "resolution" {
  const profile = profileOf(zoneId);
  const variable = variableOf(variableId);
  if (!profile) return "zone";
  if (!variable) return "variable";
  if (!variable.supportedTemporalResolutions.includes(resolution as "year")) return "resolution";
  const observations: Observation[] = [];
  for (let year = START_YEAR; year <= END_YEAR; year += 1) {
    const observation = sample(profile, variableId, year);
    if (observation) observations.push(observation);
  }
  const points = observations
    .filter((observation) => observation.status !== "missing" && observation.value != null)
    .map((observation) => ({ year: Number(observation.date.slice(0, 4)), value: observation.value as number }));
  const trend = regress(points);
  trend.unit = variable.unit;
  return {
    zoneId,
    variableId,
    resolution: "year",
    unit: variable.unit,
    datasetVersion: DATASET,
    observations,
    trend,
  };
}

export function layerFor(variableId: string, date: string): MapLayer | "variable" | "date" {
  const variable = variableOf(variableId);
  if (!variable) return "variable";
  const snapped = `${date.slice(0, 4)}-01-01`;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || snapped < variable.availableDateRange.start || snapped > variable.availableDateRange.end) {
    return "date";
  }
  const year = Number(snapped.slice(0, 4));
  const zoneValues = PROFILES.flatMap((profile) => {
    const observation = sample(profile, variableId, year);
    if (!observation) return [];
    return [{ zoneId: profile.id, value: observation.value, status: observation.status }];
  });
  return {
    variableId,
    date: snapped,
    mode: "zone-symbols",
    unit: variable.unit,
    scale: variable.displayScale ? { ...variable.displayScale, source: "display" } : null,
    zoneValues,
  };
}

export function rank(variableId: string, metric: "changePerDecade" | "changeOverPeriod" = "changePerDecade"): RankingEntry[] | "variable" {
  if (!variableOf(variableId)) return "variable";
  const rows = PROFILES.flatMap((profile) => {
    const series = seriesFor(profile.id, variableId);
    if (typeof series !== "object" || series.observations.length === 0) return [];
    const trend = series.trend;
    if (!trend || trend.direction === "insufficient") return [];
    return [{
      zoneId: profile.id,
      direction: trend.direction,
      changePerDecade: trend.changePerDecade ?? null,
      changeOverPeriod: trend.changeOverPeriod ?? null,
    }];
  });
  rows.sort((a, b) => (b[metric] ?? 0) - (a[metric] ?? 0));
  return rows.map((row, index) => ({ rank: index + 1, ...row }));
}

function fold(value: string): string {
  return value.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
}

const STOP = new Set(["temperature", "surface", "precipitations", "precipitation", "donnees", "tendance", "tendances", "variable", "variables", "prototype", "villes", "ville", "dernieres", "decennies", "decennie", "cours", "rapide", "rapidement", "essai", "jeu", "ans", "annees"]);

function findZones(text: string): { matched: Profile[]; unknown: string[] } {
  const folded = fold(text);
  const matched = PROFILES.filter((profile) => {
    const names = [fold(profile.name), ...profile.aliases.map(fold)];
    return names.some((name) => folded.includes(name));
  });
  const unknown: string[] = [];
  const pattern = /(?:\ba|\bà|\bde|\bet)\s+([a-z][a-z' -]{2,})/gi;
  const source = fold(text);
  for (const match of source.matchAll(pattern)) {
    const token = match[1].trim();
    const word = token.split(/\s+/)[0];
    if (STOP.has(word)) continue;
    const known = PROFILES.some((profile) => [fold(profile.name), ...profile.aliases.map(fold)].some((name) => name === word || name === token));
    if (!known && !unknown.includes(word)) unknown.push(word);
  }
  return { matched, unknown };
}

function byRole(role: string): Variable | undefined {
  return variables().find((variable) => variable.role === role);
}

function formatNum(value: number): string {
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2, signDisplay: "exceptZero" }).format(value);
}

export function answer(text: string, context: {
  selectedZoneId: string | null;
  activeVariableIds: string[];
  primaryVariableId: string | null;
  selectedDate: string | null;
}): { text: string; actions: AssistantAction[]; dataReferences: ChatMessage["dataReferences"]; suggestedFollowUps: string[] } {
  const folded = fold(text);
  const places = findZones(text);
  let variable: Variable | undefined;
  if (folded.includes("precip")) variable = byRole("precipitation");
  else if (folded.includes("rechauff") || folded.includes("temperature")) variable = byRole("surface-temperature");
  else if (folded.includes("cette variable")) {
    const id = context.primaryVariableId ?? context.activeVariableIds[0];
    variable = id ? variableOf(id) : undefined;
  }

  const references: NonNullable<ChatMessage["dataReferences"]> = [];
  if (variable) references.push({ kind: "variable", id: variable.id });

  if (places.unknown.length > 0 && places.matched.length === 0) {
    const label = places.unknown[0];
    return {
      text: `${capitalize(label)} n'est pas dans les zones du prototype.`,
      actions: [],
      dataReferences: references,
      suggestedFollowUps: SUGGESTED_PROMPTS.slice(0, 2),
    };
  }

  if (places.unknown.length > 0 && folded.includes("compar")) {
    const missing = capitalize(places.unknown[0]);
    const present = places.matched.map((profile) => profile.name).join(", ");
    return {
      text: `${missing} n'est pas dans les zones du prototype. ${present ? `${present} y est.` : ""}`.trim(),
      actions: [],
      dataReferences: references,
      suggestedFollowUps: [],
    };
  }

  if (!variable && (folded.includes("rechauff") || folded.includes("temperature") || folded.includes("precip"))) {
    return {
      text: `Aucune variable du catalogue ne correspond. Variables publiées : ${variables().map((item) => item.name).join(", ")}.`,
      actions: [],
      dataReferences: [],
      suggestedFollowUps: [],
    };
  }

  const activate = activateFor(variable);

  if (folded.includes("compar") && variable) {
    if (places.matched.length >= 2) {
      const ids = places.matched.slice(0, 6).map((profile) => profile.id);
      ids.forEach((id) => references.push({ kind: "zone", id }));
      return {
        text: `Dans le jeu d'essai, comparaison de ${variable.name} pour ${places.matched.map((profile) => profile.name).join(" et ")}.`,
        actions: [...activate, { type: "SHOW_COMPARISON", variableId: variable.id, zoneIds: ids }, { type: "OPEN_PANEL", panel: "zoneCard" }],
        dataReferences: references,
        suggestedFollowUps: [],
      };
    }
    return {
      text: "La comparaison demande deux zones présentes dans le prototype.",
      actions: [],
      dataReferences: references,
      suggestedFollowUps: [],
    };
  }

  if (places.matched.length === 1 && variable) {
    const profile = places.matched[0];
    const series = seriesFor(profile.id, variable.id);
    references.push({ kind: "zone", id: profile.id });
    const trend = typeof series === "object" ? series.trend : undefined;
    const sentence = trend?.changePerDecade == null
      ? "La tendance n'est pas calculée."
      : `La variation synthétique est ${formatNum(trend.changePerDecade)} ${variable.unit} par décennie.`;
    return {
      text: `Dans le jeu d'essai, ${variable.name} à ${profile.name}. ${sentence}`,
      actions: [...activate, { type: "SELECT_ZONE", zoneId: profile.id }, { type: "OPEN_PANEL", panel: "zoneCard" }],
      dataReferences: references,
      suggestedFollowUps: [],
    };
  }

  const wantsRanking = folded.includes("villes") || folded.includes("zones") || folded.includes("plus") || folded.includes("diminu");
  if (wantsRanking && variable) {
    const table = rank(variable.id);
    if (table === "variable") {
      return { text: "Cette variable est absente du catalogue.", actions: [], dataReferences: references, suggestedFollowUps: [] };
    }
    const decreasing = folded.includes("diminu");
    const rows = decreasing ? [...table].reverse().filter((row) => row.direction === "down") : table.slice(0, 3);
    const sentence = rows.slice(0, 3).map((row) => {
      const name = profileOf(row.zoneId)?.name ?? row.zoneId;
      references.push({ kind: "zone", id: row.zoneId, variableId: variable.id });
      return `${name} (${formatNum(row.changePerDecade ?? 0)} ${variable.unit})`;
    }).join(", ");
    return {
      text: decreasing
        ? `Dans le jeu d'essai, les baisses de ${variable.name} concernent : ${sentence}.`
        : `Dans le jeu d'essai, les plus fortes variations de ${variable.name} par décennie sont : ${sentence}.`,
      actions: [...activate, { type: "SHOW_RANKING", variableId: variable.id, metric: "changePerDecade" }, { type: "OPEN_PANEL", panel: "assistant" }],
      dataReferences: references,
      suggestedFollowUps: ["Comment évolue cette variable sur une zone du catalogue ?"],
    };
  }

  if (folded.includes("evolu") || folded.includes("decenn")) {
    const zoneId = context.selectedZoneId;
    const chosen = variable;
    if (!chosen || !zoneId) {
      return {
        text: "Choisissez une zone et une variable du prototype pour lire une évolution. Aucune variable n'a été activée au hasard.",
        actions: [],
        dataReferences: references,
        suggestedFollowUps: SUGGESTED_PROMPTS.slice(0, 1),
      };
    }
    const series = seriesFor(zoneId, chosen.id);
    const name = profileOf(zoneId)?.name ?? zoneId;
    const trend = typeof series === "object" ? series.trend : undefined;
    const sentence = trend?.changePerDecade == null
      ? "La tendance n'est pas calculée."
      : `Sur la période du jeu d'essai, la variation est ${formatNum(trend.changePerDecade)} ${chosen.unit} par décennie.`;
    references.push({ kind: "zone", id: zoneId, variableId: chosen.id });
    return {
      text: `${chosen.name} à ${name}. ${sentence}`,
      actions: [{ type: "OPEN_PANEL", panel: "zoneCard" }],
      dataReferences: references,
      suggestedFollowUps: [],
    };
  }

  return {
    text: `Je peux agir sur les zones et variables publiées : ${zones().map((zone) => zone.name).join(", ")}. Variables : ${variables().map((item) => item.name).join(", ")}.`,
    actions: [],
    dataReferences: [],
    suggestedFollowUps: SUGGESTED_PROMPTS.slice(0, 3),
  };
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
