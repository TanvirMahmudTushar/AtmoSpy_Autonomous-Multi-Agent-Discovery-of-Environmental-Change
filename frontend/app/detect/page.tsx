"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { PlaceType, RegionInfo, Suggestion, VariableInfo } from "@/lib/types";
import { Panel, PanelTitle } from "@/components/ui/panel";
import { PixelButton } from "@/components/ui/button";
import { PixelSprite } from "@/components/pixel/PixelSprite";
import { Term } from "@/components/glossary/Term";
import { RegionPicker, type Where } from "@/components/detect/RegionPicker";
import { ScanResults } from "@/components/detect/ScanResults";
import { InvestigationRun } from "@/components/investigate/InvestigationRun";

const LAST_YEAR = new Date().getFullYear() - 1;

const PLACES: Array<{ id: PlaceType; label: string; hint: string }> = [
  { id: "city", label: "City air", hint: "Heat, haze and pollution above big cities" },
  { id: "desert", label: "Desert", hint: "Heat, dust and rare rain" },
  { id: "rainforest", label: "Rainforest", hint: "Rain, humidity and forest water" },
  { id: "coast", label: "Coast or estuary", hint: "Where rivers meet the sea" },
  { id: "ice", label: "Ice and snow", hint: "Polar regions and ice sheets" },
  { id: "ocean", label: "Open ocean", hint: "Sea surface and the air above it" },
  { id: "farmland", label: "Farmland", hint: "Soil water, rain and heat for crops" },
  { id: "mountains", label: "Mountains", hint: "Snowpack, glaciers and high air" },
  { id: "river_basin", label: "River basin", hint: "Rain, runoff and stored water" },
];

const STEPS = ["Place", "Where", "What", "When", "Results"] as const;

export default function DetectPage() {
  const [step, setStep] = useState(0);
  const [place, setPlace] = useState<PlaceType | null>(null);
  const [where, setWhere] = useState<Where | null>(null);
  const [variable, setVariable] = useState<string | null>(null);
  const [startYear, setStartYear] = useState<number | null>(null);
  const [endYear, setEndYear] = useState(LAST_YEAR);
  const [related, setRelated] = useState(false);
  const [run, setRun] = useState<{ kind: "investigation" | "scan"; id: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [regions, setRegions] = useState<RegionInfo[]>([]);
  const [variables, setVariables] = useState<VariableInfo[]>([]);
  useEffect(() => {
    api.getRegions().then(setRegions).catch(() => setError("Could not load regions — is the server running?"));
    api.getVariables().then(setVariables).catch(() => undefined);
  }, []);

  const available = useMemo(() => variables.filter((v) => v.available !== false), [variables]);
  const chosen = available.find((v) => v.code === variable) ?? null;
  const regionName =
    where?.region_code != null
      ? (regions.find((r) => r.code === where.region_code)?.name ?? where.region_code)
      : where?.bbox
        ? "your drawn area"
        : "";
  const firstYear = Math.max(1981, chosen?.coverage_start ?? 1981);
  const start = Math.min(Math.max(startYear ?? firstYear, firstYear), endYear - 7);

  const resultsRef = useRef<HTMLDivElement>(null);
  const go = (s: number) => {
    setStep(s);
    setError(null);
  };

  /** `period` is given when following a scan result, so the full analysis
   * covers exactly the years the scan tested. */
  async function startInvestigation(code = variable, period?: { start: number; end: number }) {
    if (!code || !where) return;
    setBusy(true);
    setError(null);
    try {
      const v = available.find((x) => x.code === code);
      const first = Math.max(1981, v?.coverage_start ?? 1981);
      const { investigation_id } = await api.createStructuredInvestigation({
        variable_code: code,
        ...(where.bbox ? { bbox: where.bbox } : { region_code: where.region_code }),
        start_year: period?.start ?? Math.min(Math.max(startYear ?? first, first), endYear - 7),
        end_year: period?.end ?? endYear,
        run_relationship_analysis: related,
      });
      if (period) {
        setStartYear(period.start);
        setEndYear(period.end);
      }
      setVariable(code);
      setRun({ kind: "investigation", id: investigation_id });
      go(4);
      setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the investigation.");
    } finally {
      setBusy(false);
    }
  }

  async function startScan() {
    if (!where) return;
    setBusy(true);
    setError(null);
    try {
      const { investigation_id } = await api.startScan({
        ...(where.bbox ? { bbox: where.bbox } : { region_code: where.region_code }),
        start_year: 1990,
        end_year: LAST_YEAR,
      });
      setRun({ kind: "scan", id: investigation_id });
      go(4);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the scan.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <div className="mb-6 flex items-center gap-3">
        <PixelSprite name="compass" size={40} />
        <div>
          <h1 className="font-display text-[16px] text-[var(--app-ink)]">Be a trend detective</h1>
          <p className="mt-1 text-sm text-[var(--app-ink-soft)]">
            Answer four short questions. We&apos;ll fetch real NASA data and test whether it is really changing.
          </p>
        </div>
      </div>

      <ol className="mb-6 flex flex-wrap gap-2" aria-label="Progress">
        {STEPS.map((s, i) => (
          <li key={s}>
            <button
              type="button"
              disabled={i > step || (i === 4 && !run)}
              onClick={() => go(i)}
              aria-current={i === step ? "step" : undefined}
              className={`border-2 px-2.5 py-1 font-display text-[8px] disabled:opacity-40 ${
                i === step
                  ? "border-[var(--app-accent-green)] text-[var(--app-ink)]"
                  : "border-[var(--app-border)]/40 text-[var(--app-muted)]"
              }`}
            >
              {i + 1}. {s}
            </button>
          </li>
        ))}
      </ol>

      {step === 0 && (
        <Panel>
          <PanelTitle>1. What kind of place do you want to investigate?</PanelTitle>
          <div className="grid gap-2 sm:grid-cols-3">
            {PLACES.map((p) => (
              <button
                key={p.id}
                type="button"
                aria-pressed={place === p.id}
                onClick={() => {
                  setPlace(p.id);
                  setWhere(null);
                  go(1);
                }}
                className={`rounded-sm border-2 p-3 text-left hover:bg-[var(--app-panel-alt)] ${
                  place === p.id ? "border-[var(--app-accent-green)]" : "border-[var(--app-border)]/30"
                }`}
              >
                <span className="block font-display text-[9px] text-[var(--app-ink)]">{p.label}</span>
                <span className="mt-1 block text-xs text-[var(--app-ink-soft)]">{p.hint}</span>
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => {
              setPlace(null);
              go(1);
            }}
            className="mt-3 text-xs text-[var(--app-accent-cyan)] underline"
          >
            Skip — I&apos;ll pick any place on the map
          </button>
        </Panel>
      )}

      {step === 1 && (
        <Panel>
          <PanelTitle>2. Where exactly?</PanelTitle>
          <p className="mb-3 text-xs text-[var(--app-ink-soft)]">
            The trend is computed for the whole area as an <Term k="area_mean">area-weighted average</Term>, and each{" "}
            <Term k="grid_cell">grid cell</Term> inside it is also tested on its own, to see whether different parts are
            changing in <Term k="opposite_trends">opposite directions</Term>.
          </p>
          <RegionPicker
            regions={regions}
            tags={place ? [place] : []}
            value={where}
            onChange={(w) => {
              setWhere(w);
              loadSuggestions(place, w); // start now so step 3 opens with them ready
            }}
          />
          <div className="mt-4 flex items-center justify-between gap-3">
            <span className="text-xs text-[var(--app-ink-soft)]">
              {where ? <>Selected: <strong className="text-[var(--app-ink)]">{regionName}</strong></> : "Nothing selected yet."}
            </span>
            <PixelButton type="button" disabled={!where} onClick={() => go(2)}>
              Next: what to look at
            </PixelButton>
          </div>
        </Panel>
      )}

      {step === 2 && where && (
        <WhatStep
          place={place}
          where={where}
          regionName={regionName}
          available={available}
          value={variable}
          onPick={(code) => {
            setVariable(code);
            setStartYear(null);
            go(3);
          }}
          onScan={startScan}
          busy={busy}
        />
      )}

      {step === 3 && chosen && where && (
        <Panel>
          <PanelTitle>4. Over what years?</PanelTitle>
          <p className="mb-4 text-sm text-[var(--app-ink-soft)]">
            <strong className="text-[var(--app-ink)]">{chosen.name}</strong> over {regionName}. Longer records give a
            trend more chance to stand out from natural ups and downs (see <Term k="detectability">years to detect</Term>
            ).
          </p>
          {chosen.level_hpa != null && (
            <LevelLadder variables={available} current={chosen} onPick={(code) => setVariable(code)} />
          )}
          <div className="flex flex-wrap items-end gap-4 text-sm">
            <label className="flex flex-col gap-1 text-xs text-[var(--app-ink-soft)]">
              From
              <select
                value={start}
                onChange={(e) => setStartYear(Number(e.target.value))}
                className="rounded-sm border border-[var(--app-border)]/40 bg-[var(--app-panel-alt)] px-2 py-1 text-[var(--app-ink)]"
              >
                {range(firstYear, endYear - 7).map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-[var(--app-ink-soft)]">
              To
              <select
                value={endYear}
                onChange={(e) => setEndYear(Number(e.target.value))}
                className="rounded-sm border border-[var(--app-border)]/40 bg-[var(--app-panel-alt)] px-2 py-1 text-[var(--app-ink)]"
              >
                {range(firstYear + 7, LAST_YEAR).map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-2 text-xs text-[var(--app-ink-soft)]">
              <input type="checkbox" checked={related} onChange={(e) => setRelated(e.target.checked)} />
              Also check which other variables move with it
            </label>
          </div>
          <p className="mt-2 text-[11px] text-[var(--app-muted)]">
            {endYear - start + 1} years selected. Data for this variable starts in {firstYear}.
          </p>
          {(chosen.known_breaks ?? []).some((b) => b.year > start && b.year <= endYear) && (
            <p className="mt-2 rounded-sm border border-[var(--chart-warning)] p-2 text-xs text-[var(--app-ink-soft)]">
              Heads up: there is a <Term k="known_break">known break</Term> in this period —{" "}
              {(chosen.known_breaks ?? []).filter((b) => b.year > start && b.year <= endYear).map((b) => b.note).join(" ")}
            </p>
          )}
          <div className="mt-5 flex justify-end">
            <PixelButton type="button" disabled={busy} onClick={() => startInvestigation()}>
              {busy ? "Starting..." : "Investigate"}
            </PixelButton>
          </div>
        </Panel>
      )}

      {error && (
        <Panel className="mt-4 border-[var(--chart-critical)]">
          <p className="text-sm text-[var(--text-critical)]">{error}</p>
        </Panel>
      )}

      <div ref={resultsRef}>
        {step === 4 && run?.kind === "investigation" && <InvestigationRun investigationId={run.id} />}
        {step === 4 && run?.kind === "scan" && (
          <ScanResults
            scanId={run.id}
            regionName={regionName}
            onInvestigate={(code, start, end) => startInvestigation(code, { start, end })}
          />
        )}
      </div>
    </div>
  );
}

// Suggestions for a place and region, fetched once and shared: the region
// step starts the request so the variable step usually opens with it ready.
const suggestionCache = new Map<string, ReturnType<typeof api.suggest>>();

function loadSuggestions(place: PlaceType | null, where: Where): ReturnType<typeof api.suggest> {
  const key = JSON.stringify([place, where]);
  let pending = suggestionCache.get(key);
  if (!pending) {
    pending = api.suggest(place ? [place] : [], where.bbox ? { bbox: where.bbox } : { region_code: where.region_code });
    pending.catch(() => suggestionCache.delete(key)); // let a failed request be retried
    suggestionCache.set(key, pending);
  }
  return pending;
}

function range(a: number, b: number): number[] {
  return a > b ? [] : Array.from({ length: b - a + 1 }, (_, i) => a + i);
}

function WhatStep({
  place,
  where,
  regionName,
  available,
  value,
  onPick,
  onScan,
  busy,
}: {
  place: PlaceType | null;
  where: Where;
  regionName: string;
  available: VariableInfo[];
  value: string | null;
  onPick: (code: string) => void;
  onScan: () => void;
  busy: boolean;
}) {
  const [suggestions, setSuggestions] = useState<Suggestion[] | null>(null);
  const [source, setSource] = useState<"rules" | "llm">("rules");
  const [showAll, setShowAll] = useState(false);
  useEffect(() => {
    let cancelled = false;
    loadSuggestions(place, where)
      .then((r) => {
        if (cancelled) return;
        setSuggestions(r.suggestions);
        setSource(r.source);
      })
      .catch(() => !cancelled && setSuggestions([]));
    return () => {
      cancelled = true;
    };
  }, [place, where]);

  const byDomain = useMemo(() => {
    const groups: Record<string, VariableInfo[]> = {};
    for (const v of available) (groups[v.domain ?? "land"] ??= []).push(v);
    return groups;
  }, [available]);

  return (
    <Panel>
      <PanelTitle>3. What do you want to look at over {regionName}?</PanelTitle>
      <p className="mb-3 text-xs text-[var(--app-ink-soft)]">
        Suggested for this kind of place{source === "llm" ? " (reasons written by an AI model, which never sees or states any results)" : ""}.
      </p>
      {suggestions === null ? (
        <p className="text-sm text-[var(--app-muted)]">Finding good variables to check…</p>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2">
          {suggestions.map((s) => (
            <button
              key={s.variable_code}
              type="button"
              aria-pressed={value === s.variable_code}
              onClick={() => onPick(s.variable_code)}
              className="rounded-sm border-2 border-[var(--app-border)]/30 p-3 text-left hover:border-[var(--app-accent-green)] hover:bg-[var(--app-panel-alt)]"
            >
              <span className="block font-display text-[9px] text-[var(--app-ink)]">{s.name}</span>
              <span className="mt-1 block text-xs text-[var(--app-ink-soft)]">{s.definition}</span>
              <span className="mt-1.5 block text-xs text-[var(--app-ink)]">Why here: {s.reason}</span>
              <span className="mt-1.5 block text-[10px] text-[var(--app-muted)]">
                {s.source_label}
                {s.coverage_start ? ` · since ${s.coverage_start}` : ""}
              </span>
            </button>
          ))}
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--app-border)]/20 pt-4">
        <button type="button" onClick={() => setShowAll((s) => !s)} className="text-xs text-[var(--app-accent-cyan)] underline">
          {showAll ? "Hide the full list" : `Browse all ${available.length} variables`}
        </button>
        <PixelButton type="button" variant="gold" size="sm" disabled={busy} onClick={onScan}>
          Scan everything here
        </PixelButton>
      </div>
      <p className="mt-1 text-right text-[10px] text-[var(--app-muted)]">
        Tests every variable over {regionName} and ranks what is changing.
      </p>

      {showAll && (
        <div className="mt-3 flex flex-col gap-3">
          {Object.entries(byDomain).map(([domain, vars]) => (
            <div key={domain}>
              <div className="font-display text-[8px] uppercase text-[var(--app-muted)]">{domain}</div>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {vars.map((v) => (
                  <button
                    key={v.code}
                    type="button"
                    title={v.definition}
                    onClick={() => onPick(v.code)}
                    className="rounded-sm border border-[var(--app-border)]/30 px-2 py-1 text-xs text-[var(--app-ink-soft)] hover:bg-[var(--app-panel-alt)]"
                  >
                    {v.name}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

/** Picks between the same variable at different heights in the atmosphere. */
function LevelLadder({
  variables,
  current,
  onPick,
}: {
  variables: VariableInfo[];
  current: VariableInfo;
  onPick: (code: string) => void;
}) {
  const family = variables
    .filter((v) => v.level_hpa != null && v.dataset_code === current.dataset_code && v.units === current.units)
    .sort((a, b) => (a.level_hpa ?? 0) - (b.level_hpa ?? 0));
  if (family.length < 2) return null;
  return (
    <fieldset className="mb-4">
      <legend className="mb-2 text-xs text-[var(--app-ink-soft)]">
        Height in the atmosphere (<Term k="pressure_level">pressure level</Term>) — higher is further up:
      </legend>
      <div className="flex flex-col gap-1">
        {family.map((v) => (
          <label key={v.code} className="flex items-center gap-2 text-xs text-[var(--app-ink-soft)]">
            <input type="radio" name="level" checked={v.code === current.code} onChange={() => onPick(v.code)} />
            <span className="w-16 tabular-nums text-[var(--app-ink)]">{v.level_hpa} hPa</span>
            <span>{v.name}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
