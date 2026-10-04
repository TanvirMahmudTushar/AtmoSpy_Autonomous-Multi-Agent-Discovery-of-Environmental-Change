"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { PixelSprite } from "@/components/pixel/PixelSprite";
import { Logo } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";
import { UserMenu } from "./UserMenu";
import { useAuth } from "@/lib/AuthContext";

const LINKS = [
  { href: "/discover", label: "Discover" },
  { href: "/investigate", label: "Investigate" },
  { href: "/globe", label: "Globe" },
  { href: "/watches", label: "Watches" },
  { href: "/findings", label: "Findings" },
];

export function NavBar() {
  const pathname = usePathname();
  const { user } = useAuth();

  // The landing page is the pre-login pitch and login/signup are their own
  // focused auth flows — none of them get nav chrome. Beyond that, the nav
  // is only useful once a session (real or guest) exists, so it stays
  // hidden until then rather than exposing authenticated-feature links to a
  // signed-out visitor.
  if (pathname === "/" || pathname === "/login" || pathname === "/signup" || !user) {
    return null;
  }

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--app-hud-line)] bg-[var(--app-panel)]/90 shadow-[0_1px_24px_-8px_var(--app-glow)] backdrop-blur-md">
      <div className="mx-auto flex max-w-[1400px] items-center justify-between gap-4 px-4 py-3">
        <Link href="/home" className="flex items-center gap-2.5">
          <div className="relative">
            <Logo size={52} />
            <span className="absolute inset-0 -z-10 rounded-full bg-[var(--app-accent-cyan)] opacity-20 blur-md" />
          </div>
          <div className="leading-tight">
            <span className="block font-display text-[10px] text-[var(--app-ink)] sm:text-[11px]">
              AtmoSpy
            </span>
            <span className="label-telemetry">Mission Console</span>
          </div>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {LINKS.map((link) => {
            const active = pathname === link.href || pathname.startsWith(link.href + "/");
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "relative rounded-sm px-3 py-2 font-display text-[9px] transition-colors",
                  active ? "text-[var(--app-accent-cyan)]" : "text-[var(--app-ink-soft)] hover:text-[var(--app-ink)]"
                )}
              >
                {link.label}
                {active && (
                  <span className="absolute inset-x-2 -bottom-[13px] h-[2px] bg-[var(--app-accent-cyan)] shadow-[0_0_8px_var(--app-accent-cyan)]" />
                )}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-4">
          <button
            onClick={() => window.dispatchEvent(new Event("open-command-palette"))}
            className="hidden items-center gap-2 rounded-sm border border-[var(--app-hud-line)] bg-[var(--app-panel-alt)] px-2.5 py-1.5 text-[var(--app-muted)] hover:border-[var(--app-accent-cyan)] hover:text-[var(--app-accent-cyan)] lg:flex"
          >
            <PixelSprite name="magnifier" size={14} />
            <span className="label-telemetry">Search</span>
            <span className="rounded-sm border border-[var(--app-hud-line)] px-1 font-mono-data text-[9px]">⌘K</span>
          </button>
          <ThemeToggle />
          <UserMenu />
        </div>
      </div>
      <nav className="flex flex-wrap items-center gap-1 border-t border-[var(--app-hud-line)] px-4 py-2 md:hidden">
        {LINKS.map((link) => (
          <Link key={link.href} href={link.href} className="rounded-sm px-2 py-1 font-display text-[8px] text-[var(--app-ink-soft)]">
            {link.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
