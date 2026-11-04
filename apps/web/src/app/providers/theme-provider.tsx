import { useEffect, useState, type ReactNode } from "react";
import { ThemeContext, type Theme } from "./theme-context";

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem("counterpoint:theme:v1");
    if (saved === "dark" || saved === "light") return saved;
  } catch {
    /* Private browsing can deny storage. */
  }
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, updateTheme] = useState<Theme>(initialTheme);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.style.colorScheme = theme;
  }, [theme]);
  function setTheme(next: Theme) {
    updateTheme(next);
    try {
      localStorage.setItem("counterpoint:theme:v1", next);
    } catch {
      /* Theme remains usable. */
    }
  }
  return <ThemeContext value={{ theme, setTheme }}>{children}</ThemeContext>;
}
