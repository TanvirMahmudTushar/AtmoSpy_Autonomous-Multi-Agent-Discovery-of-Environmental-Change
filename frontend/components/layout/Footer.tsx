const REPO_URL =
  "https://github.com/TanvirMahmudTushar/AtmoSpy_Autonomous-Multi-Agent-Discovery-of-Environmental-Change";

export function Footer() {
  return (
    <footer className="border-t-4 border-[var(--app-border)] bg-[var(--app-panel)] py-6">
      <div className="mx-auto flex max-w-7xl flex-col items-center gap-2 px-4 text-center">
        <a
          href={REPO_URL}
          target="_blank"
          rel="noreferrer"
          className="font-display text-[9px] text-[var(--app-accent-cyan)] underline underline-offset-4 hover:text-[var(--app-ink)]"
        >
          View the source on GitHub
        </a>
        
      </div>
    </footer>
  );
}
