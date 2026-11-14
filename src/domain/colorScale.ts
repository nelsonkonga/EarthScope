import type { ColorStop, Variable } from "./types";

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function hexToRgb(hex: string): [number, number, number] {
  const raw = hex.replace("#", "");
  const full = raw.length === 3 ? raw.split("").map((c) => c + c).join("") : raw;
  const n = Number.parseInt(full, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function rgbToHex(r: number, g: number, b: number): string {
  const channel = (n: number) => Math.round(clamp(n, 0, 255)).toString(16).padStart(2, "0");
  return `#${channel(r)}${channel(g)}${channel(b)}`;
}

export function mixHex(from: string, to: string, t: number): string {
  const [ar, ag, ab] = hexToRgb(from);
  const [br, bg, bb] = hexToRgb(to);
  const u = clamp(t, 0, 1);
  return rgbToHex(ar + (br - ar) * u, ag + (bg - ag) * u, ab + (bb - ab) * u);
}

export function derivedStops(color: string): ColorStop[] {
  return [0, 0.25, 0.5, 0.75, 1].map((at) => ({
    at,
    color: mixHex("#f4efe6", color, 0.2 + at * 0.8),
  }));
}

export function sampleScale(stops: ColorStop[], position: number): string {
  const sorted = [...stops].sort((a, b) => a.at - b.at);
  if (sorted.length === 0) return "#ffffff";
  if (position <= sorted[0].at) return sorted[0].color;
  const last = sorted[sorted.length - 1];
  if (position >= last.at) return last.color;
  for (let i = 1; i < sorted.length; i += 1) {
    if (position <= sorted[i].at) {
      const span = sorted[i].at - sorted[i - 1].at || 1;
      return mixHex(sorted[i - 1].color, sorted[i].color, (position - sorted[i - 1].at) / span);
    }
  }
  return last.color;
}

export function colorForValue(
  variable: Variable,
  value: number,
  scale: { min: number; max: number } | null,
): string {
  const stops = variable.colorScale?.stops?.length ? variable.colorScale.stops : derivedStops(variable.color);
  if (variable.scaleMode === "absolute") return sampleScale(stops, value);
  const min = scale?.min ?? variable.displayScale?.min ?? 0;
  const max = scale?.max ?? variable.displayScale?.max ?? 1;
  const t = max === min ? 0.5 : (value - min) / (max - min);
  return sampleScale(stops, clamp(t, 0, 1));
}
