import { keepPreviousData, useQuery, useQueries } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { Variable } from "../domain/types";
import { useWorkspace } from "../state/workspaceStore";
import { fetchComparison, fetchLayer, fetchRanking, fetchSeries, fetchVariables, fetchZones } from "./resources";

export function useZoneCatalog(search?: string, remote = false) {
  return useQuery({
    queryKey: remote ? ["zones", search ?? ""] : ["zones"],
    queryFn: ({ signal }) => fetchZones(signal, remote ? search : undefined),
    staleTime: 300_000,
  });
}

export function useVariableCatalog() {
  return useQuery({
    queryKey: ["variables"],
    queryFn: ({ signal }) => fetchVariables(signal),
    staleTime: 300_000,
  });
}

export function useLayerQuery(variable: Variable | null) {
  const date = useWorkspace((state) => state.selectedDate);
  const playback = useWorkspace((state) => state.playback);
  const [debounced, setDebounced] = useState(date);
  useEffect(() => {
    if (playback === "playing") {
      setDebounced(date);
      return;
    }
    const timer = window.setTimeout(() => setDebounced(date), 150);
    return () => window.clearTimeout(timer);
  }, [date, playback]);
  return useQuery({
    queryKey: ["layer", variable?.id, debounced, variable?.datasetVersion],
    enabled: Boolean(variable && debounced),
    queryFn: ({ signal }) => fetchLayer(variable!.id, debounced!, signal),
    staleTime: Infinity,
    placeholderData: keepPreviousData,
  });
}

export function useSeriesQueries(zoneId: string | null, variables: Variable[]) {
  return useQueries({
    queries: variables.map((variable) => ({
      queryKey: ["timeseries", zoneId, variable.id, variable.defaultResolution, variable.datasetVersion],
      enabled: Boolean(zoneId),
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        fetchSeries(zoneId as string, variable.id, variable.defaultResolution, signal),
      staleTime: Infinity,
    })),
  });
}

export function useRankingQuery(variableId: string | null, metric: string | null) {
  return useQuery({
    queryKey: ["ranking", variableId, metric],
    enabled: Boolean(variableId && metric),
    queryFn: ({ signal }) => fetchRanking(variableId as string, metric as string, signal),
    staleTime: Infinity,
  });
}

export function useComparisonQuery(variableId: string | null, zoneIds: string[]) {
  return useQuery({
    queryKey: ["comparison", variableId, zoneIds.join(",")],
    enabled: Boolean(variableId && zoneIds.length >= 2),
    queryFn: ({ signal }) => fetchComparison(variableId as string, zoneIds, signal),
    staleTime: Infinity,
  });
}
