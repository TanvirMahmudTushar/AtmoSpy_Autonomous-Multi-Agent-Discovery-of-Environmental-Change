"use client";

import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

type Theme = "light" | "dark";

function applyTheme(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem("etd-theme", theme);
  } catch {
    /* private browsing / blocked storage — theme just won't persist */
  }
}

// The source of truth is <html data-theme>, which the inline script in
// app/layout.tsx sets from storage / system preference before first paint.
// Reading it as an external store keeps every toggle in sync with it.
function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => observer.disconnect();
}

function getTheme(): Theme {
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

// Unknown on the server; the label fills in after hydration.
function getServerTheme(): Theme | null {
  return null;
}

export function ThemeToggle() {
  const theme = useSyncExternalStore<Theme | null>(subscribe, getTheme, getServerTheme);

  function toggle() {
    applyTheme(getTheme() === "dark" ? "light" : "dark");
  }

  return (
    <button
      onClick={toggle}
      aria-label="Toggle day/night theme"
      className="pixel-button flex items-center gap-2 px-3 py-2 bg-[var(--app-panel)] text-[var(--app-ink)]"
      suppressHydrationWarning
    >
      {theme === "dark" ? <Moon size={14} /> : <Sun size={14} />}
      <span className="font-display text-[8px]">{theme === null ? "" : theme === "dark" ? "Night" : "Day"}</span>
    </button>
  );
}
