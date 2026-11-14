import type { Resolution, Variable } from "./types";

const DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

export function isDate(value: string): boolean {
  if (!DATE.test(value)) return false;
  const time = Date.parse(`${value}T00:00:00Z`);
  if (Number.isNaN(time)) return false;
  return new Date(time).toISOString().slice(0, 10) === value;
}

export function unionRange(variables: Pick<Variable, "availableDateRange">[]): { start: string; end: string } | null {
  if (variables.length === 0) return null;
  let start = variables[0].availableDateRange.start;
  let end = variables[0].availableDateRange.end;
  for (const variable of variables) {
    if (variable.availableDateRange.start < start) start = variable.availableDateRange.start;
    if (variable.availableDateRange.end > end) end = variable.availableDateRange.end;
  }
  return { start, end };
}

export function maxEnd(variables: Pick<Variable, "availableDateRange">[]): string | null {
  return unionRange(variables)?.end ?? null;
}

export function snapToResolution(date: string, resolution: Resolution): string | null {
  if (!isDate(date)) return null;
  if (resolution === "year" || resolution === "irregular") return `${date.slice(0, 4)}-01-01`;
  if (resolution === "month") return `${date.slice(0, 7)}-01`;
  if (resolution === "hour") return date;
  return date;
}

function addUtc(date: string, unit: "day" | "month" | "year", amount: number): string {
  const [year, month, day] = date.split("-").map(Number);
  const next = new Date(Date.UTC(year, month - 1, day));
  if (unit === "day") next.setUTCDate(next.getUTCDate() + amount);
  if (unit === "month") next.setUTCMonth(next.getUTCMonth() + amount);
  if (unit === "year") next.setUTCFullYear(next.getUTCFullYear() + amount);
  return next.toISOString().slice(0, 10);
}

export function buildSteps(start: string, end: string, resolution: Resolution): string[] {
  if (!isDate(start) || !isDate(end) || start > end) return [];
  const steps: string[] = [];
  if (resolution === "irregular") return start === end ? [start] : [start, end];
  let cursor = snapToResolution(start, resolution) ?? start;
  const last = snapToResolution(end, resolution) ?? end;
  const guard = resolution === "hour" || resolution === "day" ? 20000 : 5000;
  while (cursor <= last && steps.length < guard) {
    steps.push(cursor);
    if (resolution === "year") cursor = addUtc(cursor, "year", 1);
    else if (resolution === "month") cursor = addUtc(cursor, "month", 1);
    else cursor = addUtc(cursor, "day", 1);
  }
  return steps;
}

export function nearestStep(steps: string[], date: string): string | null {
  if (steps.length === 0) return null;
  let best = steps[0];
  let bestDistance = Math.abs(Date.parse(steps[0]) - Date.parse(date));
  for (const step of steps) {
    const distance = Math.abs(Date.parse(step) - Date.parse(date));
    if (distance < bestDistance) {
      best = step;
      bestDistance = distance;
    }
  }
  return best;
}

export function shiftStep(steps: string[], date: string, delta: number): string | null {
  if (steps.length === 0) return null;
  const current = nearestStep(steps, date);
  if (!current) return null;
  const index = steps.indexOf(current) + delta;
  if (index < 0 || index >= steps.length) return null;
  return steps[index];
}

export function dateInRange(date: string, range: { start: string; end: string }): boolean {
  return isDate(date) && date >= range.start && date <= range.end;
}
