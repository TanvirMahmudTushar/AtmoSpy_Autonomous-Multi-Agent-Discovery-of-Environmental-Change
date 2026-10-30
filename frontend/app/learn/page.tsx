import type { Metadata } from "next";
import { Panel, PanelTitle } from "@/components/ui/panel";
import { GLOSSARY, type GlossaryEntry } from "@/lib/glossary";

export const metadata: Metadata = {
  title: "Learn the words — AtmoSpy",
  description: "Plain-language definitions of the Earth-science and statistics terms used by the trend detective.",
};

const GROUPS: Array<{ id: GlossaryEntry["group"]; title: string; intro: string }> = [
  { id: "Data", title: "Where the numbers come from", intro: "Satellites, models and the grids they share." },
  { id: "Change", title: "Describing change", intro: "Trends, seasons and how big a change is." },
  {
    id: "Statistics",
    title: "Is it significant?",
    intro: "How a detective tells a real trend from random ups and downs.",
  },
];

export default function LearnPage() {
  const entries = Object.entries(GLOSSARY) as Array<[string, GlossaryEntry]>;
  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="font-display text-[16px] text-[var(--app-ink)]">Learn the words</h1>
      <p className="mt-2 text-sm text-[var(--app-ink-soft)]">
        Every dotted-underlined word in the app links here. Each definition is short on purpose.
      </p>
      <div className="mt-8 flex flex-col gap-6">
        {GROUPS.map((g) => (
          <Panel key={g.id}>
            <PanelTitle>{g.title}</PanelTitle>
            <p className="mb-4 text-xs text-[var(--app-muted)]">{g.intro}</p>
            <dl className="grid gap-4 sm:grid-cols-2">
              {entries
                .filter(([, e]) => e.group === g.id)
                .map(([key, e]) => (
                  <div key={key} id={key} className="scroll-mt-24 border-l-2 border-[var(--app-accent-sky)] pl-3">
                    <dt className="font-display text-[9px] text-[var(--app-ink)]">{e.term}</dt>
                    <dd className="mt-1 text-sm leading-relaxed text-[var(--app-ink-soft)]">{e.short}</dd>
                    {e.more && <dd className="mt-1 text-xs leading-relaxed text-[var(--app-muted)]">{e.more}</dd>}
                  </div>
                ))}
            </dl>
          </Panel>
        ))}
      </div>
    </div>
  );
}
