import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export type Theme = "light" | "dark" | "soft";
export const THEMES: Theme[] = ["light", "dark", "soft"];
const STORAGE_KEY = "terrasense.theme";

function readStored(): Theme {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "dark" || value === "soft" ? value : "light";
  } catch {
    return "light";
  }
}

type ThemeState = { theme: Theme; setTheme: (theme: Theme) => void };
const ThemeContext = createContext<ThemeState | null>(null);

/** Landing appearance. Light is the default; the choice is remembered per browser. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(readStored);
  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* the choice lasts for this page only */
    }
  }, []);
  const value = useMemo(() => ({ theme, setTheme }), [theme, setTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme must be used inside ThemeProvider");
  return value;
}
