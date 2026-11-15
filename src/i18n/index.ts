import { useCallback, useEffect, useState } from "react";
import en from "./en.json";
import fr from "./fr.json";

export type Locale = "fr" | "en";
export type Dictionary = typeof fr;

const dictionaries: Record<Locale, Dictionary> = { fr, en };
const STORAGE_KEY = "terrasense.locale";

function readStored(): Locale {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "en" ? "en" : "fr";
  } catch {
    return "fr";
  }
}

/** Replaces {name} placeholders. */
export function format(template: string, values: Record<string, string | number>) {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}

export function useLocale() {
  const [locale, setLocaleState] = useState<Locale>(readStored);
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* private mode: the choice lasts for this page only */
    }
  }, []);
  return { locale, setLocale, t: dictionaries[locale] };
}
