import { describe, expect, it } from "vitest";
import { selectBasemap } from "./globe";

describe("selectBasemap", () => {
  it("keeps Google Photorealistic 3D Tiles when a key is set", () => {
    expect(selectBasemap("map-tiles-key")).toBe("google");
  });

  it("uses Cesium ion when the Google key is missing", () => {
    expect(selectBasemap(undefined)).toBe("ion");
    expect(selectBasemap("")).toBe("ion");
    expect(selectBasemap("   ")).toBe("ion");
  });
});
