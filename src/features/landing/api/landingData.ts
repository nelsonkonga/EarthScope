import { useAnalyticsQuery, useSeriesQueries, useVariableCatalog, useZoneCatalog } from '../../../api/queries';
import type { Observation } from '../../../domain/types';

export type LandingObservation = Pick<Observation, 'date' | 'value' | 'status'>;

/** The series the landing preview shows when the catalog publishes it: deep soil moisture over Yaoundé. */
const PREFERRED_VARIABLE = 'var_soil_moisture_deep';
const SOIL_PATTERN = /soil[-_ ]?moisture|moisture/i;

/**
 * Adapter over the application's existing queries (src/api/queries.ts): the same cache, the same
 * /api/v1 endpoints as the workspace. Nothing is synthesized: when the API is unavailable the
 * components receive empty arrays and error flags and say so.
 */
export function useLandingCatalog() {
  const zonesQuery = useZoneCatalog();
  const variablesQuery = useVariableCatalog();
  const zones = zonesQuery.data?.zones ?? [];
  const variables = variablesQuery.data?.variables ?? [];
  const selectedZone = zones[0];
  const compatible = variables.filter((variable) => !selectedZone || selectedZone.availableVariableIds.includes(variable.id));
  const selectedVariable =
    compatible.find((variable) => variable.id === PREFERRED_VARIABLE) ??
    compatible.find((variable) => SOIL_PATTERN.test(`${variable.role ?? ''} ${variable.id} ${variable.name}`)) ??
    compatible[0];
  const [series] = useSeriesQueries(selectedZone && selectedVariable ? selectedZone.id : null, selectedVariable ? [selectedVariable] : []);
  const analytics = useAnalyticsQuery(selectedZone?.id ?? null, selectedVariable?.id ?? null, null, null);
  const dateBounds = variables
    .flatMap((variable) => [variable.availableDateRange?.start, variable.availableDateRange?.end])
    .filter((value): value is string => Boolean(value))
    .sort();

  return {
    zones,
    variables,
    observations: (series?.data?.observations ?? []) as LandingObservation[],
    isCatalogLoading: zonesQuery.isLoading || variablesQuery.isLoading,
    isCatalogError: zonesQuery.isError || variablesQuery.isError,
    isSeriesLoading: Boolean(series?.isLoading) || (!series && (zonesQuery.isLoading || variablesQuery.isLoading)),
    isSeriesError: Boolean(series?.isError) || zonesQuery.isError || variablesQuery.isError,
    periodStart: dateBounds[0],
    periodEnd: dateBounds[dateBounds.length - 1],
    selectedZone,
    selectedVariable,
    trend: analytics.data ? { theilSen: analytics.data.theilSen, mannKendall: analytics.data.mannKendall } : null,
  };
}

export type LandingCatalog = ReturnType<typeof useLandingCatalog>;
