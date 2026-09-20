import { useCallback, useEffect, useState } from "react";
import { THEME_KEY } from "@/lib/constants";

export type Theme = "light" | "dark";

function currentTheme(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

const listeners = new Set<(theme: Theme) => void>();

/** Shared so charts and Mermaid diagrams re-render on the same signal. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(currentTheme);

  useEffect(() => {
    const listener = (next: Theme) => setTheme(next);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  const toggle = useCallback(() => {
    const next: Theme = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.classList.toggle("dark", next === "dark");
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* storage blocked */
    }
    listeners.forEach((l) => l(next));
  }, []);

  return { theme, toggle };
}

/** Reads a themed CSS variable so Recharts/Mermaid can use the design tokens. */
export function cssVar(name: string, fallback = "#888"): string {
  if (typeof window === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}
