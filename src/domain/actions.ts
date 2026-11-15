import { dateInRange, isDate, snapToResolution } from "./time";
import type { ActionResult, AnalyticsView, AssistantAction, Comparison, PanelId, Variable, Zone } from "./types";

export type SessionSlice = {
  selectedZoneId: string | null;
  activeVariableIds: string[];
  primaryVariableId: string | null;
  selectedDate: string | null;
  playback: "paused" | "playing";
  activePanel: PanelId | null;
  zoneCardOpen: boolean;
  comparison: Comparison | null;
  analyticsView: AnalyticsView;
};

export type CatalogIndex = {
  zones: Zone[];
  variables: Variable[];
};

const KNOWN = new Set<AssistantAction["type"]>([
  "SELECT_ZONE",
  "CLEAR_ZONE",
  "ACTIVATE_VARIABLES",
  "DEACTIVATE_VARIABLES",
  "CLEAR_VARIABLES",
  "SET_PRIMARY_VARIABLE",
  "SET_DATE",
  "OPEN_PANEL",
  "SHOW_RANKING",
  "SHOW_COMPARISON",
  "SET_VIEW_MODE",
]);

function isAction(value: unknown): value is AssistantAction {
  if (!value || typeof value !== "object") return false;
  const type = (value as { type?: unknown }).type;
  return typeof type === "string" && KNOWN.has(type as AssistantAction["type"]);
}

function clone(session: SessionSlice): SessionSlice {
  return {
    ...session,
    activeVariableIds: [...session.activeVariableIds],
    comparison: session.comparison ? { ...session.comparison, zoneIds: [...session.comparison.zoneIds] } : null,
  };
}

export function reduceAssistantActions(
  actions: unknown[],
  session: SessionSlice,
  catalog: CatalogIndex,
): { session: SessionSlice; results: ActionResult[] } {
  const draft = clone(session);
  const results: ActionResult[] = [];
  const zoneIds = new Set(catalog.zones.map((zone) => zone.id));
  const variables = new Map(catalog.variables.map((variable) => [variable.id, variable]));
  const limited = actions.slice(0, 10);
  const dates: { action: Extract<AssistantAction, { type: "SET_DATE" }>; index: number }[] = [];

  const reject = (action: AssistantAction, reason: string, index: number) => {
    results[index] = { action, status: "rejected", reason };
  };
  const accept = (action: AssistantAction, index: number) => {
    results[index] = { action, status: "applied" };
  };

  limited.forEach((raw, index) => {
    if (!isAction(raw)) {
      results[index] = {
        action: { type: "CLEAR_ZONE" },
        status: "rejected",
        reason: "unknown_action",
      };
      return;
    }
    if (raw.type === "SET_DATE") {
      dates.push({ action: raw, index });
      return;
    }
    applyStructural(raw, index);
  });

  for (let index = 10; index < actions.length; index += 1) {
    const raw = actions[index];
    results[index] = {
      action: isAction(raw) ? raw : { type: "CLEAR_ZONE" },
      status: "rejected",
      reason: "too_many",
    };
  }

  const primary = draft.primaryVariableId ? variables.get(draft.primaryVariableId) : undefined;
  for (const entry of dates) {
    const snapped = snapToResolution(entry.action.date, primary?.defaultResolution ?? "year");
    if (!primary) {
      reject(entry.action, "no_primary", entry.index);
      continue;
    }
    if (!snapped || !isDate(entry.action.date) || !dateInRange(snapped, primary.availableDateRange)) {
      reject(entry.action, "date_out_of_range", entry.index);
      continue;
    }
    draft.selectedDate = snapped;
    draft.playback = "paused";
    accept({ ...entry.action, date: snapped }, entry.index);
  }

  return { session: draft, results: results.filter(Boolean) };

  function applyStructural(action: AssistantAction, index: number) {
    if (action.type === "SELECT_ZONE") {
      if (!zoneIds.has(action.zoneId)) return reject(action, "unknown_zone", index);
      draft.selectedZoneId = action.zoneId;
      draft.zoneCardOpen = true;
      return accept(action, index);
    }
    if (action.type === "CLEAR_ZONE") {
      draft.selectedZoneId = null;
      draft.zoneCardOpen = false;
      return accept(action, index);
    }
    if (action.type === "ACTIVATE_VARIABLES") {
      if (action.variableIds.length === 0 || action.variableIds.some((id) => !variables.has(id))) {
        return reject(action, "unknown_variable", index);
      }
      const next = action.mode === "replace" ? [] : [...draft.activeVariableIds];
      for (const id of action.variableIds) {
        if (!next.includes(id)) next.push(id);
      }
      draft.activeVariableIds = next;
      if (!draft.primaryVariableId || !next.includes(draft.primaryVariableId)) draft.primaryVariableId = next[0] ?? null;
      draft.playback = "paused";
      return accept(action, index);
    }
    if (action.type === "DEACTIVATE_VARIABLES") {
      if (action.variableIds.some((id) => !variables.has(id))) return reject(action, "unknown_variable", index);
      draft.activeVariableIds = draft.activeVariableIds.filter((id) => !action.variableIds.includes(id));
      if (!draft.primaryVariableId || !draft.activeVariableIds.includes(draft.primaryVariableId)) {
        draft.primaryVariableId = draft.activeVariableIds[0] ?? null;
      }
      draft.playback = "paused";
      return accept(action, index);
    }
    if (action.type === "CLEAR_VARIABLES") {
      draft.activeVariableIds = [];
      draft.primaryVariableId = null;
      draft.playback = "paused";
      return accept(action, index);
    }
    if (action.type === "SET_PRIMARY_VARIABLE") {
      if (!draft.activeVariableIds.includes(action.variableId)) return reject(action, "primary_not_active", index);
      draft.primaryVariableId = action.variableId;
      return accept(action, index);
    }
    if (action.type === "OPEN_PANEL") {
      if (action.panel === "zoneCard") draft.zoneCardOpen = true;
      else draft.activePanel = action.panel;
      return accept(action, index);
    }
    if (action.type === "SHOW_RANKING") {
      if (!variables.has(action.variableId)) return reject(action, "unknown_variable", index);
      draft.comparison = { variableId: action.variableId, zoneIds: [], mode: "rank", metric: action.metric };
      return accept(action, index);
    }
    if (action.type === "SET_VIEW_MODE") {
      const modes: AnalyticsView[] = ["single", "superposition", "normalized"];
      if (!modes.includes(action.mode)) return reject(action, "invalid", index);
      draft.analyticsView = action.mode;
      return accept(action, index);
    }
    if (action.type === "SHOW_COMPARISON") {
      const unique = [...new Set(action.zoneIds)];
      if (unique.length < 2 || unique.length > 6) return reject(action, "comparison_size", index);
      if (unique.some((id) => !zoneIds.has(id))) return reject(action, "unknown_zone", index);
      if (!variables.has(action.variableId)) return reject(action, "unknown_variable", index);
      draft.comparison = {
        variableId: action.variableId,
        zoneIds: unique,
        mode: "compare",
        metric: "changePerDecade",
      };
      return accept(action, index);
    }
    return reject(action, "unknown_action", index);
  }
}

export function selectionSummary(
  results: ActionResult[],
  catalog: CatalogIndex,
): string | null {
  const names: string[] = [];
  let view: string | null = null;
  const viewLabel: Record<string, string> = {
    single: "variable unique",
    superposition: "superposition",
    normalized: "indice normalisé",
  };
  for (const result of results) {
    if (result.status !== "applied") continue;
    const action = result.action;
    if (action.type === "SET_VIEW_MODE") view = viewLabel[action.mode] ?? null;
    if (action.type === "ACTIVATE_VARIABLES") {
      for (const id of action.variableIds) {
        const name = catalog.variables.find((variable) => variable.id === id)?.name;
        if (name && !names.includes(name)) names.push(name);
      }
    }
    if (action.type === "SELECT_ZONE") {
      const name = catalog.zones.find((zone) => zone.id === action.zoneId)?.name;
      if (name && !names.includes(name)) names.push(name);
    }
  }
  const selection = names.length ? `J'ai sélectionné : ${names.join(", ")}.` : null;
  const display = view ? `Affichage : ${view}.` : null;
  const line = [selection, display].filter(Boolean).join(" ");
  return line || null;
}

export const rejectionLabel: Record<string, string> = {
  unknown_action: "action inconnue",
  too_many: "trop d'actions",
  unknown_zone: "zone inconnue",
  unknown_variable: "variable inconnue",
  date_out_of_range: "date hors couverture",
  no_primary: "aucune variable active",
  primary_not_active: "variable non active",
  comparison_size: "comparaison de 2 à 6 zones",
  invalid: "action invalide",
};
