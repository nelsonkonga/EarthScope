import { describe, expect, it } from "vitest";
import { reduceAssistantActions, selectionSummary } from "./actions";
import type { SessionSlice } from "./actions";
import type { Variable, Zone } from "./types";

const zone = (id: string, name: string): Zone => ({
  id,
  name,
  country: "Pays",
  latitude: 0,
  longitude: 0,
  availableVariableIds: ["temp"],
});

const variable = (id: string): Variable => ({
  id,
  name: id,
  description: "Définition",
  categoryId: "cat",
  unit: "unité",
  color: "#112233",
  visualizationType: "zone-symbols",
  supportedTemporalResolutions: ["year"],
  defaultResolution: "year",
  availableDateRange: { start: "2000-01-01", end: "2020-01-01" },
  datasetVersion: "fixture-1",
});

const session = (): SessionSlice => ({
  selectedZoneId: null,
  activeVariableIds: [],
  primaryVariableId: null,
  selectedDate: "2020-01-01",
  playback: "playing",
  activePanel: null,
  zoneCardOpen: false,
  comparison: null,
  analyticsView: "single",
});

const catalog = {
  zones: [zone("a", "Alpha"), zone("b", "Beta")],
  variables: [variable("temp"), variable("rain")],
};

describe("reduceAssistantActions", () => {
  it("applies a valid batch and names the selection", () => {
    const result = reduceAssistantActions(
      [
        { type: "ACTIVATE_VARIABLES", variableIds: ["temp"], mode: "replace" },
        { type: "SELECT_ZONE", zoneId: "a" },
        { type: "SET_DATE", date: "2010-06-01" },
      ],
      session(),
      catalog,
    );
    expect(result.session.primaryVariableId).toBe("temp");
    expect(result.session.selectedZoneId).toBe("a");
    expect(result.session.selectedDate).toBe("2010-01-01");
    expect(result.session.playback).toBe("paused");
    expect(result.results.every((entry) => entry.status === "applied")).toBe(true);
    expect(selectionSummary(result.results, catalog)).toBe("Selected: temp, Alpha.");
  });

  it("keeps valid actions when one zone is unknown", () => {
    const result = reduceAssistantActions(
      [
        { type: "ACTIVATE_VARIABLES", variableIds: ["temp"], mode: "replace" },
        { type: "SELECT_ZONE", zoneId: "missing" },
      ],
      session(),
      catalog,
    );
    expect(result.session.activeVariableIds).toEqual(["temp"]);
    expect(result.session.selectedZoneId).toBeNull();
    expect(result.results[1]).toMatchObject({ status: "rejected", reason: "unknown_zone" });
  });

  it("rejects an unknown action type and a primary that is not active", () => {
    const result = reduceAssistantActions(
      [{ type: "FLY", zoneId: "a" }, { type: "SET_PRIMARY_VARIABLE", variableId: "temp" }],
      session(),
      catalog,
    );
    expect(result.results.map((entry) => entry.reason)).toEqual(["unknown_action", "primary_not_active"]);
    expect(result.session.primaryVariableId).toBeNull();
  });

  it("switches the analytics view", () => {
    const result = reduceAssistantActions(
      [{ type: "SET_VIEW_MODE", mode: "superposition" }],
      session(),
      catalog,
    );
    expect(result.session.analyticsView).toBe("superposition");
    expect(selectionSummary(result.results, catalog)).toBe("View: dual axis.");
  });

  it("rejects a comparison that is not between 2 and 6 known zones", () => {
    const result = reduceAssistantActions(
      [{ type: "SHOW_COMPARISON", variableId: "temp", zoneIds: ["a"] }],
      session(),
      catalog,
    );
    expect(result.results[0].reason).toBe("comparison_size");
    expect(result.session.comparison).toBeNull();
  });
});
