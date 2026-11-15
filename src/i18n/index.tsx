import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import en from "./en.json";
import fr from "./fr.json";

export type Locale = "fr" | "en";
export type Dictionary = typeof fr;

// en.json must keep the same shape as fr.json; this line fails the type check if a key is missing.
const dictionaries: Record<Locale, Dictionary> = { fr, en: en satisfies Dictionary };
const STORAGE_KEY = "terrasense.locale";

function readStored(): Locale {
  try {
    return localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "fr";
  } catch {
    return "fr";
  }
}

/** Replaces {name} placeholders. */
export function format(template: string, values: Record<string, string | number>) {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}

type I18n = { locale: Locale; setLocale: (locale: Locale) => void; t: Dictionary };
const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
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
  const value = useMemo(() => ({ locale, setLocale, t: dictionaries[locale] }), [locale, setLocale]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used inside I18nProvider");
  return value;
}

export function monthYear(date: string, locale: Locale, month: "long" | "short" = "long") {
  return new Intl.DateTimeFormat(locale === "fr" ? "fr-FR" : "en-GB", { month, year: "numeric", timeZone: "UTC" }).format(new Date(date));
}
