import type {
  ChatMessage,
  ChatSession,
  MapLayer,
  RankingEntry,
  TimeSeries,
  Variable,
  VariableCategory,
  Zone,
} from "../domain/types";
import { request } from "./http";

type ZonesResponse = { meta: { complete: boolean; datasetVersion: string }; zones: Zone[] };
type VariablesResponse = { meta: { datasetVersion: string }; categories: VariableCategory[]; variables: Variable[] };

export function fetchZones(signal?: AbortSignal, q?: string) {
  const query = q ? `?q=${encodeURIComponent(q)}` : "";
  return request<ZonesResponse>(`/api/v1/zones${query}`, { signal });
}

export function fetchVariables(signal?: AbortSignal) {
  return request<VariablesResponse>("/api/v1/variables", { signal });
}

export function fetchSeries(zoneId: string, variableId: string, resolution: string, signal?: AbortSignal) {
  const params = new URLSearchParams({ zoneId, variableId, resolution });
  return request<{ series: TimeSeries }>(`/api/v1/timeseries?${params}`, { signal }).then((body) => body.series);
}

export function fetchLayer(variableId: string, date: string, signal?: AbortSignal) {
  const params = new URLSearchParams({ variableId, date });
  return request<{ layer: MapLayer }>(`/api/v1/layers?${params}`, { signal }).then((body) => body.layer);
}

export function fetchRanking(variableId: string, metric: string, signal?: AbortSignal) {
  const params = new URLSearchParams({ variableId, metric });
  return request<{ ranking: { unit: string; entries: RankingEntry[] } }>(`/api/v1/rankings?${params}`, { signal }).then(
    (body) => body.ranking,
  );
}

export function fetchComparison(variableId: string, zoneIds: string[], signal?: AbortSignal) {
  const params = new URLSearchParams({ variableId });
  zoneIds.forEach((zoneId) => params.append("zoneId", zoneId));
  return request<{ comparison: { series: TimeSeries[] } }>(`/api/v1/comparisons?${params}`, { signal }).then(
    (body) => body.comparison,
  );
}

export function createAssistantSession(signal?: AbortSignal) {
  return request<ChatSession>("/api/v1/assistant/sessions", { method: "POST", signal });
}

export function fetchAssistantSession(id: string, signal?: AbortSignal) {
  return request<ChatSession>(`/api/v1/assistant/sessions/${id}`, { signal });
}

export function postAssistantMessage(
  id: string,
  text: string,
  clientContext: {
    selectedZoneId: string | null;
    activeVariableIds: string[];
    primaryVariableId: string | null;
    selectedDate: string | null;
  },
  signal?: AbortSignal,
) {
  return request<{ message: ChatMessage }>(`/api/v1/assistant/sessions/${id}/messages`, {
    method: "POST",
    body: JSON.stringify({ text, clientContext }),
    signal,
  }).then((body) => body.message);
}
