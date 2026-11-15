import { describe, expect, it } from "vitest";
import en from "./en.json";
import fr from "./fr.json";

function shape(value: unknown, path = ""): string[] {
  if (Array.isArray(value)) return [`${path}[${value.length}]`, ...value.flatMap((item, index) => shape(item, `${path}[${index}]`))];
  if (value && typeof value === "object") return Object.entries(value).flatMap(([key, item]) => shape(item, `${path}.${key}`));
  return [path];
}

function strings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(strings);
  if (value && typeof value === "object") return Object.values(value).flatMap(strings);
  return [];
}

describe("landing translations", () => {
  it("have the same keys and list lengths in French and English", () => {
    expect(shape(en)).toEqual(shape(fr));
  });

  it("never use the old brand name", () => {
    for (const text of [...strings(fr), ...strings(en)]) expect(text).not.toMatch(/Terra\s*Sense\s+Camero/i);
  });

  it("keep placeholders aligned between languages", () => {
    const fa = strings(fr);
    const ea = strings(en);
    fa.forEach((text, index) => {
      const holes = (value: string) => (value.match(/\{\w+\}/g) ?? []).sort().join(",");
      expect(holes(ea[index])).toBe(holes(text));
    });
  });
});
