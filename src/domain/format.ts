import type { Trend } from "./types";

const numberFormat = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 });

export function formatNumber(value: number): string {
  return numberFormat.format(value);
}

export function formatDegrees(value: number): string {
  const abs = Math.abs(value);
  const fixed = abs.toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
  return fixed.replace(".", ",");
}

export function formatLatLon(latitude: number, longitude: number): string {
  const latHemisphere = latitude >= 0 ? "N" : "S";
  const lonHemisphere = longitude >= 0 ? "E" : "O";
  return `${formatDegrees(latitude)}° ${latHemisphere}, ${formatDegrees(longitude)}° ${lonHemisphere}`;
}

export function formatAltitude(meters: number): string {
  if (!Number.isFinite(meters)) return "—";
  if (Math.abs(meters) >= 10000) return `${formatNumber(meters / 1000)} km`;
  return `${formatNumber(meters)} m`;
}

export function niceDistance(meters: number): string {
  if (!Number.isFinite(meters) || meters <= 0) return "—";
  const exponent = Math.floor(Math.log10(meters));
  const candidates = [1, 2, 5, 10].map((base) => base * 10 ** exponent);
  let best = candidates[0];
  for (const candidate of candidates) {
    if (Math.abs(candidate - meters) < Math.abs(best - meters)) best = candidate;
  }
  if (best >= 1000) return `${formatNumber(best / 1000)} km`;
  return `${formatNumber(best)} m`;
}

export function formatDate(date: string): string {
  const [year, month, day] = date.split("-");
  if (!year || !month || !day) return date;
  return `${day}/${month}/${year}`;
}

export function formatTrend(trend: Trend | undefined, unit: string): string {
  if (!trend || trend.direction === "insufficient" || trend.changePerDecade == null) {
    return "Tendance non calculée (données insuffisantes).";
  }
  const signed = new Intl.NumberFormat("fr-FR", {
    maximumFractionDigits: 2,
    signDisplay: "exceptZero",
  }).format(trend.changePerDecade);
  const word = trend.direction === "up" ? "hausse" : trend.direction === "down" ? "baisse" : "stable";
  return `${signed} ${unit} par décennie (${word}).`;
}

export function statusWord(status: "observed" | "missing" | "estimated" | undefined): string {
  if (status === "estimated") return "estimée";
  if (status === "observed") return "mesurée";
  return "indisponible";
}

export function foldText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}
