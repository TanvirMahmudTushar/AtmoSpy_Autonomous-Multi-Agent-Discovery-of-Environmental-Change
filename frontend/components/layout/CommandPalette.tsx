"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { PixelSprite } from "@/components/pixel/PixelSprite";
import type { ICONS } from "@/components/pixel/icons";

type IconName = keyof typeof ICONS;

interface PaletteItem {
  id: string;
  title: string;
  subtitle: string;
  icon: IconName;
  keywords: string;
  action: () => void;
}

const STATIC_PAGES: { title: string; subtitle: string; href: string; icon: IconName }[] = [
  { title: "Home", subtitle: "Your mission dashboard", href: "/home", icon: "star" },
  { title: "Discover Changes", subtitle: "Autonomous scan across NASA POWER", href: "/discover", icon: "telescope" },
  { title: "Investigate a Question", subtitle: "Ask in plain language", href: "/investigate", icon: "compass" },
  { title: "Globe", subtitle: "Every finding plotted where it happened", href: "/globe", icon: "earth" },
  { title: "Watches", subtitle: "Standing checks on a region and variable", href: "/watches", icon: "satellite" },
  { title: "Findings", subtitle: "All discovered environmental changes", href: "/findings", icon: "notebook" },
  { title: "About", subtitle: "Methodology, limitations, citations", href: "/about", icon: "magnifier" },
];

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [regions, setRegions] = useState<{ code: string; name: string; kind: string }[]>([]);
  const [variables, setVariables] = useState<{ code: string; name: string; units: string }[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const loadedRef = useRef(false);

  useEffect(() => {
    // Every open starts from an empty search with the first item active.
    function openFresh() {
      setQuery("");
      setActiveIndex(0);
      setOpen(true);
    }
    function onKeyDown(e: KeyboardEvent) {
      const isMeta = e.metaKey || e.ctrlKey;
      if (isMeta && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (open) setOpen(false);
        else openFresh();
      } else if (e.key === "Escape" && open) {
        setOpen(false);
      }
    }
    function onOpenRequest() {
      openFresh();
    }
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("open-command-palette", onOpenRequest);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("open-command-palette", onOpenRequest);
    };
  }, [open]);

  useEffect(() => {
    if (open && !loadedRef.current) {
      loadedRef.current = true;
      api.getRegions().then(setRegions).catch(() => {});
      api.getVariables().then(setVariables).catch(() => {});
    }
    if (open) setTimeout(() => inputRef.current?.focus(), 10);
  }, [open]);

  const go = useCallback(
    (href: string) => {
      setOpen(false);
      router.push(href);
    },
    [router],
  );

  const items: PaletteItem[] = useMemo(() => {
    const pages: PaletteItem[] = STATIC_PAGES.map((p) => ({
      id: `page-${p.href}`,
      title: p.title,
      subtitle: p.subtitle,
      icon: p.icon,
      keywords: `${p.title} ${p.subtitle} page`,
      action: () => go(p.href),
    }));

    const regionItems: PaletteItem[] = regions.map((r) => ({
      id: `region-${r.code}`,
      title: r.name,
      subtitle: `Investigate this region — ${r.kind}`,
      icon: "pin" as IconName,
      keywords: `region ${r.name} ${r.code}`,
      action: () => go(`/investigate?prefill_region=${encodeURIComponent(r.name)}`),
    }));

    const variableItems: PaletteItem[] = variables.map((v) => ({
      id: `variable-${v.code}`,
      title: v.name,
      subtitle: `Variable — ${v.units}`,
      icon: "chart" as IconName,
      keywords: `variable ${v.name} ${v.code}`,
      action: () => go(`/investigate?prefill_variable=${encodeURIComponent(v.name)}`),
    }));

    return [...pages, ...regionItems, ...variableItems];
  }, [regions, variables, go]);

  const filtered = useMemo(() => {
    if (!query.trim()) return items.slice(0, 8);
    const q = query.toLowerCase();
    return items.filter((it) => it.keywords.toLowerCase().includes(q)).slice(0, 12);
  }, [items, query]);


  function onInputKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      filtered[activeIndex]?.action();
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[200] flex items-start justify-center bg-black/60 p-4 pt-24" onClick={() => setOpen(false)}>
      <div className="hud-panel w-full max-w-lg !rounded-md p-0" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b border-[var(--app-hud-line)] px-4 py-3">
          <PixelSprite name="magnifier" size={18} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActiveIndex(0);
            }}
            onKeyDown={onInputKeyDown}
            placeholder="Jump to a page, region, or variable..."
            className="flex-1 bg-transparent text-sm text-[var(--app-ink)] outline-none placeholder:text-[var(--app-muted)]"
          />
          <span className="label-telemetry rounded-sm border border-[var(--app-hud-line)] px-1.5 py-0.5">ESC</span>
        </div>
        <div className="max-h-96 overflow-y-auto p-2">
          {filtered.length === 0 && <p className="px-3 py-4 text-center text-sm text-[var(--app-muted)]">No matches.</p>}
          {filtered.map((item, i) => (
            <button
              key={item.id}
              onClick={item.action}
              onMouseEnter={() => setActiveIndex(i)}
              className={`flex w-full items-center gap-3 rounded-sm px-3 py-2 text-left ${
                i === activeIndex ? "bg-[var(--app-panel-alt)]" : ""
              }`}
            >
              <PixelSprite name={item.icon} size={18} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm text-[var(--app-ink)]">{item.title}</div>
                <div className="truncate text-xs text-[var(--app-muted)]">{item.subtitle}</div>
              </div>
              {i === activeIndex && <span className="label-telemetry text-[var(--app-accent-cyan)]">ENTER</span>}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
