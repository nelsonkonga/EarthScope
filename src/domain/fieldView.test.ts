import { describe, expect, it } from "vitest";
import type { Variable } from "./types";
import { composeField, kindForRole, normalizeValue } from "./fieldView";

function variable(partial: Partial<Variable> & Pick<Variable, "id" | "role" | "color">): Variable {
  return {
    name: partial.id,
    description: "",
    categoryId: "cat_soil",
    unit: "",
    colorScale: {
      stops: [
        { at: 0, color: "#000000" },
        { at: 1, color: "#ffffff" },
      ],
    },
    visualizationType: "zone-symbols",
    supportedTemporalResolutions: ["month"],
    defaultResolution: "month",
    availableDateRange: { start: "2002-07-01", end: "2014-11-01" },
    datasetVersion: "observations-1",
    ...partial,
  };
}

describe("composeField", () => {
  const zone = { id: "zone_yaounde" as const };

  it("paints only the measured cell for a temperature", () => {
    const primary = variable({ id: "var_soil_temp", role: "soil-temperature", color: "#E23B2F" });
    const field = composeField({
      zone,
      primary,
      secondaries: [],
      valueOf: () => 24,
      scaleOf: () => ({ min: 20, max: 30 }),
    });
    expect(field?.theme).toBe("thermal");
    expect(field?.footprint).toEqual({ west: 11.4, south: 3.75, east: 11.65, north: 3.98 });
    expect(field?.layers.map((layer) => layer.channel)).toEqual(["surface"]);
    expect(field?.layers[0].t).toBeCloseTo(0.4);
    expect(field?.layers[0].altitude).toBe(2400);
    expect(field?.layers[0].motion).toBe("pulse");
    expect(field?.layers[0].directional).toBe(false);
    expect(field?.layers[0].emit).toBe(false);
  });

  it("keeps a second ground variable as a rim and lifts aerosols above the soil", () => {
    const primary = variable({ id: "var_soil_moisture", role: "soil-moisture", color: "#1F6F9A" });
    const field = composeField({
      zone,
      primary,
      secondaries: [
        variable({ id: "var_soil_temp", role: "soil-temperature", color: "#E23B2F" }),
        variable({ id: "var_aod", role: "aerosol-optical-depth", color: "#C48A3A" }),
      ],
      valueOf: () => 1,
      scaleOf: () => ({ min: 0, max: 2 }),
    });
    expect(field?.layers.map((layer) => `${layer.channel}:${layer.kind}`)).toEqual([
      "surface:moisture",
      "halo:thermal",
      "veil:haze",
    ]);
    expect(field?.layers.every((layer) => layer.directional === false)).toBe(true);
    expect(field?.layers.find((layer) => layer.kind === "haze")?.emit).toBe(true);
    expect(field?.layers.find((layer) => layer.kind === "thermal")?.altitude).toBe(2400);
  });

  it("draws evaporation as mist and leaves a gap when the month is missing", () => {
    const primary = variable({ id: "var_evaporation", role: "evaporation", color: "#1F6B62" });
    const field = composeField({
      zone,
      primary,
      secondaries: [],
      valueOf: () => null,
      scaleOf: () => ({ min: 0, max: 5 }),
    });
    expect(field?.layers).toEqual([
      expect.objectContaining({ channel: "vapor", kind: "vapor", t: null, color: "#c5ccd1", emit: false }),
    ]);
    expect(normalizeValue(null, { min: 0, max: 1 })).toBeNull();
    expect(kindForRole("runoff")).toBe("runoff");
    expect(kindForRole("precipitation")).toBe("precipitation");
    expect(kindForRole(undefined)).toBeNull();
    expect(kindForRole("custom-index")).toBe("generic");
  });

  it("does not invent a flow direction and keeps a third plume as an outline", () => {
    const field = composeField({
      zone,
      primary: variable({ id: "var_evaporation", role: "evaporation", color: "#1F6B62" }),
      secondaries: [
        variable({ id: "var_aod", role: "aerosol-optical-depth", color: "#C48A3A" }),
        variable({ id: "var_rain", role: "precipitation", color: "#6EA4C4" }),
        variable({ id: "var_runoff", role: "runoff", color: "#1D6E93" }),
      ],
      valueOf: () => 1,
      scaleOf: () => ({ min: 0, max: 2 }),
    });
    const rain = field?.layers.find((layer) => layer.kind === "precipitation");
    const runoff = field?.layers.find((layer) => layer.kind === "runoff");
    expect(field?.layers.filter((layer) => layer.emit).map((layer) => layer.kind).sort()).toEqual(["haze", "vapor"]);
    expect(rain?.channel).toBe("halo");
    expect(rain?.emit).toBe(false);
    expect(runoff?.channel).toBe("halo");
    expect(runoff?.directional).toBe(false);
  });
});
