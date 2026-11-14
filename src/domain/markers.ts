import { colorForValue } from "./colorScale";
import type { ValueStatus, Variable } from "./types";

export const NEUTRAL_MARKER = "#ffffff";
export const SELECTED_RING = "#8eabc4";

export type MarkerAppearance = {
  fill: string;
  rings: string[];
  dashed: boolean;
  dimmed: boolean;
  emphasized: boolean;
  selected: boolean;
};

export function markerAppearance(input: {
  zoneId: string;
  selected: boolean;
  primary: Variable | null;
  secondaries: Variable[];
  observation: { status: ValueStatus; value: number | null } | null;
  scale: { min: number; max: number } | null;
  highlighted: string[] | null;
}): MarkerAppearance {
  const hasValue =
    input.primary &&
    input.observation &&
    input.observation.status !== "missing" &&
    input.observation.value != null;
  const fill = hasValue
    ? colorForValue(input.primary as Variable, input.observation?.value as number, input.scale)
    : NEUTRAL_MARKER;
  const highlighted = input.highlighted;
  return {
    fill,
    rings: input.secondaries.map((variable) => variable.color),
    dashed: input.observation?.status === "estimated",
    dimmed: highlighted != null && !highlighted.includes(input.zoneId),
    emphasized: highlighted != null && highlighted.includes(input.zoneId),
    selected: input.selected,
  };
}
