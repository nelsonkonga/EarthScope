import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import en from '../i18n/translations/en.json';
import fr from '../i18n/translations/fr.json';

export type Language = 'en' | 'fr';
export type Theme = 'light' | 'dark' | 'soft';
type Widen<T> = T extends string ? string : T extends readonly (infer U)[] ? Widen<U>[] : T extends object ? { [K in keyof T]: Widen<T[K]> } : T;
export type Messages = Widen<typeof en>;

// fr.json must keep the shape of en.json: the assignment fails the type check otherwise.
const messages: Record<Language, Messages> = { en, fr };
const LANGUAGE_KEY = 'terra-sense.language';
const THEME_KEY = 'terra-sense.theme';

function read(key: string) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage blocked: the choice lasts for this page only */
  }
}

/** American English is the default; French is an opt-in from the landing page selector. */
function readLanguage(): Language {
  return read(LANGUAGE_KEY) === 'fr' ? 'fr' : 'en';
}

function readTheme(): Theme {
  const value = read(THEME_KEY);
  return value === 'dark' || value === 'soft' ? value : 'light';
}

interface PreferencesValue {
  language: Language;
  theme: Theme;
  setLanguage: (language: Language) => void;
  setTheme: (theme: Theme) => void;
  t: Messages;
}

const PreferencesContext = createContext<PreferencesValue | null>(null);

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(readLanguage);
  const [theme, setThemeState] = useState<Theme>(readTheme);

  const setLanguage = useCallback((next: Language) => {
    write(LANGUAGE_KEY, next);
    setLanguageState(next);
  }, []);
  const setTheme = useCallback((next: Theme) => {
    write(THEME_KEY, next);
    setThemeState(next);
  }, []);

  useEffect(() => {
    document.documentElement.lang = language === 'fr' ? 'fr' : 'en-US';
  }, [language]);

  const value = useMemo(() => ({ language, theme, setLanguage, setTheme, t: messages[language] }), [language, theme, setLanguage, setTheme]);
  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences() {
  const value = useContext(PreferencesContext);
  if (!value) throw new Error('usePreferences must be used within PreferencesProvider');
  return value;
}
