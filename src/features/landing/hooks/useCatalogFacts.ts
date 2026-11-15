import { useVariableCatalog } from "../../../api/queries";

/**
 * Coverage of the published monthly series, read from /api/v1/variables.
 * The fallback is the same catalog as committed in backend/data (GLDAS/MODIS CSV for Yaoundé,
 * 2002-07 to 2014-11), so the page never shows a figure the data does not support.
 */
export const CATALOG_FALLBACK = { start: "2002-07-01", end: "2014-11-01" };

export function useCatalogFacts() {
  const query = useVariableCatalog();
  const monthly = (query.data?.variables ?? []).filter((variable) => variable.defaultResolution === "month");
  if (monthly.length === 0) return { ...CATALOG_FALLBACK, live: false };
  const starts = monthly.map((variable) => variable.availableDateRange.start).sort();
  const ends = monthly.map((variable) => variable.availableDateRange.end).sort();
  return { start: starts[0], end: ends[ends.length - 1], live: true };
}
