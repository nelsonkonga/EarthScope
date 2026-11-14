export type Resolution = "hour" | "day" | "month" | "year" | "irregular";

export type ValueStatus = "observed" | "missing" | "estimated";

export type DataCoverage = {
  variableId: string;
  start: string;
  end: string;
  resolution: Resolution;
  missingDates?: string[];
};

export type Zone = {
  id: string;
  name: string;
  country: string;
  countryCode?: string;
  latitude: number;
  longitude: number;
  description?: string;
  aliases?: string[];
  availableVariableIds: string[];
  coverage?: DataCoverage[];
};

export type VariableCategory = {
  id: string;
  name: string;
  order: number;
};

export type ColorStop = { at: number; color: string };

export type Variable = {
  id: string;
  name: string;
  description: string;
  categoryId: string;
  unit: string;
  color: string;
  colorScale?: { stops: ColorStop[] };
  scaleMode?: "relative" | "absolute";
  displayScale?: { min: number; max: number };
  visualizationType: "zone-symbols" | "raster-tiles";
  supportedTemporalResolutions: Resolution[];
  defaultResolution: Resolution;
  availableDateRange: { start: string; end: string };
  aggregationMethod?: string;
  exclusiveGroup?: string;
  role?: string;
  datasetVersion: string;
};

export type Observation = {
  date: string;
  value: number | null;
  status: ValueStatus;
  unit: string;
};

export type Trend = {
  method: string;
  periodStart: string;
  periodEnd: string;
  sampleCount: number;
  direction: "up" | "down" | "flat" | "insufficient";
  changeOverPeriod?: number;
  changePerDecade?: number;
  unit: string;
  /** Optional line endpoints so the chart can draw the server trend without refitting it. */
  startValue?: number;
  endValue?: number;
};

export type TimeSeries = {
  zoneId: string;
  variableId: string;
  resolution: Resolution;
  unit: string;
  datasetVersion: string;
  observations: Observation[];
  trend?: Trend;
};

export type ZoneValue = {
  zoneId: string;
  value: number | null;
  status: ValueStatus;
};

export type MapLayer = {
  variableId: string;
  date: string;
  mode: "zone-symbols" | "raster-tiles";
  unit: string;
  scale: { min: number; max: number; source: "display" | "data" } | null;
  zoneValues: ZoneValue[];
  tileUrlTemplate?: string;
  coverageBBox?: [number, number, number, number];
};

export type PanelId = "variables" | "zones" | "assistant";

export type Comparison = {
  variableId: string;
  zoneIds: string[];
  mode: "rank" | "compare";
  metric: "changePerDecade" | "changeOverPeriod";
};

export type AssistantAction =
  | { type: "SELECT_ZONE"; zoneId: string }
  | { type: "CLEAR_ZONE" }
  | { type: "ACTIVATE_VARIABLES"; variableIds: string[]; mode: "replace" | "add" }
  | { type: "DEACTIVATE_VARIABLES"; variableIds: string[] }
  | { type: "CLEAR_VARIABLES" }
  | { type: "SET_PRIMARY_VARIABLE"; variableId: string }
  | { type: "SET_DATE"; date: string }
  | { type: "OPEN_PANEL"; panel: PanelId | "zoneCard" }
  | { type: "SHOW_RANKING"; variableId: string; metric: "changePerDecade" | "changeOverPeriod" }
  | { type: "SHOW_COMPARISON"; variableId: string; zoneIds: string[] };

export type ActionResult = {
  action: AssistantAction;
  status: "applied" | "rejected";
  reason?: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  createdAt: string;
  actions?: AssistantAction[];
  actionResults?: ActionResult[];
  dataReferences?: { kind: string; id: string; zoneId?: string; variableId?: string; date?: string }[];
  suggestedFollowUps?: string[];
};

export type ChatSession = {
  id: string;
  createdAt: string;
  suggestedPrompts: string[];
  messages: ChatMessage[];
};

export type RankingEntry = {
  rank: number;
  zoneId: string;
  direction: Trend["direction"];
  changePerDecade: number | null;
  changeOverPeriod: number | null;
};

export type ApiErrorBody = {
  error: { code: string; message: string; details?: Record<string, unknown> };
};
