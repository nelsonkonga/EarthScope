import { usePreferences, type Language, type Messages } from '../../../context/Preferences';

export type { Language };
export type Theme = 'light' | 'dark' | 'dusk';
export type LandingMessages = Messages;

/** Every landing string comes from src/i18n/translations/{en,fr}.json. */
export function useLandingLanguage() {
  const { language, setLanguage, t } = usePreferences();
  return { language, setLanguage, t, locale: language === 'fr' ? 'fr-FR' : 'en-US' };
}

export function useLandingTheme() {
  const { theme, setTheme } = usePreferences();
  const mappedTheme: Theme = theme === 'soft' ? 'dusk' : theme;
  const cycleTheme = () => setTheme(theme === 'light' ? 'dark' : theme === 'dark' ? 'soft' : 'light');
  return { theme: mappedTheme, cycleTheme, setTheme, rawTheme: theme };
}

/** Replaces {name} placeholders. */
export function format(template: string, values: Record<string, string | number>) {
  return template.replace(/\{(\w+)\}/g, (match, key: string) => (key in values ? String(values[key]) : match));
}
