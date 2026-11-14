import { describe, expect, it } from "vitest";
import { buildSteps, nearestStep, shiftStep, snapToResolution, unionRange } from "./time";

describe("time", () => {
  it("unions variable ranges and builds yearly steps", () => {
    const range = unionRange([
      { availableDateRange: { start: "2001-01-01", end: "2003-01-01" } },
      { availableDateRange: { start: "2000-01-01", end: "2002-01-01" } },
    ]);
    expect(range).toEqual({ start: "2000-01-01", end: "2003-01-01" });
    expect(buildSteps(range!.start, range!.end, "year")).toEqual([
      "2000-01-01",
      "2001-01-01",
      "2002-01-01",
      "2003-01-01",
    ]);
  });

  it("snaps a mid-year date to 1 January and stops at the ends", () => {
    expect(snapToResolution("2015-06-01", "year")).toBe("2015-01-01");
    const steps = buildSteps("2000-01-01", "2002-01-01", "year");
    expect(nearestStep(steps, "2001-08-01")).toBe("2002-01-01");
    expect(shiftStep(steps, "2000-01-01", -1)).toBeNull();
    expect(shiftStep(steps, "2002-01-01", 1)).toBeNull();
    expect(shiftStep(steps, "2001-01-01", 1)).toBe("2002-01-01");
  });
});
