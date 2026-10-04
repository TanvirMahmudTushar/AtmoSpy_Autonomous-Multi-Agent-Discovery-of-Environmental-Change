"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function applyTheme(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem("etd-theme", theme);
  } catch {
    /* private browsing / blocked storage — theme just won't persist */
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    let initial: Theme = "dark";
    try {
      const stored = localStorage.getItem("etd-theme") as Theme | null;
      if (stored === "light" || stored === "dark") {
        initial = stored;
      } else if (window.matchMedia("(prefers-color-scheme: light)").matches) {
        initial = "light";
      }
    } catch {
      /* ignore */
    }
    setTheme(initial);
    applyTheme(initial);
  }, []);

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    applyTheme(next);
  }

  return (
    <button
      onClick={toggle}
      aria-label="Toggle day/night theme"
      className="pixel-button flex items-center gap-2 px-3 py-2 bg-[var(--app-panel)] text-[var(--app-ink)]"
      suppressHydrationWarning
    >
      {mounted && theme === "dark" ? <Moon size={14} /> : <Sun size={14} />}
      <span className="font-display text-[8px]">{mounted ? (theme === "dark" ? "Night" : "Day") : ""}</span>
    </button>
  );
}
