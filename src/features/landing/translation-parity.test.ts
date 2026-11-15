import { describe, expect, it } from 'vitest';
import fr from '../../i18n/translations/fr.json';
import en from '../../i18n/translations/en.json';

function leafPaths(value: unknown, prefix = ''): string[] {
  if (Array.isArray(value)) {
    if (value.length === 0) return [prefix];
    return value.flatMap((entry, index) => leafPaths(entry, `${prefix}[${index}]`));
  }
  if (value && typeof value === 'object') {
    return Object.entries(value).flatMap(([key, entry]) => leafPaths(entry, prefix ? `${prefix}.${key}` : key));
  }
  return [prefix];
}

describe('Terra Sense translations', () => {
  it('keeps exactly the same nested structure in French and English', () => {
    expect(leafPaths(en).sort()).toEqual(leafPaths(fr).sort());
  });
});

function strings(value: unknown): string[] {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(strings);
  if (value && typeof value === 'object') return Object.values(value).flatMap(strings);
  return [];
}

describe('Terra Sense copy', () => {
  it('keeps the same {placeholders} in both languages', () => {
    const holes = (text: string) => (text.match(/\{\w+\}/g) ?? []).sort().join(',');
    const french = strings(fr);
    strings(en).forEach((text, index) => expect(holes(text)).toBe(holes(french[index])));
  });

  it('never uses a geographic suffix on the brand name', () => {
    for (const text of [...strings(fr), ...strings(en)]) expect(text).not.toMatch(/Terra\s*Sense\s+(Camero|Africa)/i);
  });

  it('writes the English copy in American spelling', () => {
    const british = /\b(catalogue|programme|analys(e|ing|ed)|modell(ing|ed)|colour|behaviour|centre|organis(e|ation)|visualis(e|ation))\b/i;
    for (const text of strings(en)) expect(text).not.toMatch(british);
  });
});
