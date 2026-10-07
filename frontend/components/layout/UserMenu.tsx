"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { LogOut } from "lucide-react";
import { useAuth } from "@/lib/AuthContext";
import { PixelLinkButton } from "@/components/ui/button";

export function UserMenu() {
  const { user, loading, loginAsGuest, logout } = useAuth();
  const router = useRouter();
  const [guestLoading, setGuestLoading] = useState(false);

  if (loading) {
    return <div className="h-8 w-8 animate-pulse rounded-full bg-[var(--app-panel-alt)]" />;
  }

  if (!user) {
    async function handleGuest() {
      setGuestLoading(true);
      try {
        await loginAsGuest();
        // Read the current URL's own ?redirect= directly (not via
        // useSearchParams, which would force this globally-rendered nav
        // component into a Suspense boundary) so this button behaves
        // identically to the login/signup pages' own "Continue as Guest"
        // button when both are visible at once — otherwise a user who
        // landed on /login?redirect=/watches via a gated page and clicks
        // *this* one instead of the page's own button would silently lose
        // their original destination.
        const redirectTo = new URLSearchParams(window.location.search).get("redirect") || "/home";
        router.push(redirectTo);
      } catch {
        /* silently no-op — the login/signup pages surface this error if they hit it too */
      } finally {
        setGuestLoading(false);
      }
    }

    return (
      <div className="flex items-center gap-3">
        <button
          onClick={handleGuest}
          disabled={guestLoading}
          className="font-display text-[9px] text-[var(--app-muted)] hover:text-[var(--app-accent-cyan)] disabled:opacity-50"
        >
          {guestLoading ? "Starting..." : "Continue as Guest"}
        </button>
        <Link href="/login" className="font-display text-[9px] text-[var(--app-ink-soft)] hover:text-[var(--app-ink)]">
          Sign In
        </Link>
        <PixelLinkButton href="/signup" size="sm" variant="gold">
          Sign Up
        </PixelLinkButton>
      </div>
    );
  }

  const initial = (user.display_name || user.email)[0]?.toUpperCase() ?? "?";

  function handleLogout() {
    logout();
    // A hard navigation (not router.push) deliberately: logging out while on
    // an auth-only page like /home clears `user` before the client-side
    // router transition would unmount it, so that page's own "redirect to
    // /login if signed out" guard wins the race and undoes this navigation.
    // A full reload sidesteps that race entirely.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- deliberate full reload, see above
    window.location.assign("/");
  }

  return (
    <div className="flex items-center gap-2">
      <Link
        href="/home"
        className="flex items-center gap-2 rounded-sm border-2 border-[var(--app-hud-line)] bg-[var(--app-panel-alt)] px-2 py-1.5 hover:border-[var(--app-accent-cyan)]"
      >
        <span className="flex h-6 w-6 items-center justify-center rounded-full border border-[var(--app-accent-cyan)] bg-[var(--app-bg-deep)] font-mono-data text-[11px] text-[var(--app-accent-cyan)]">
          {initial}
        </span>
        <span className="hidden font-display text-[8px] text-[var(--app-ink-soft)] sm:inline">
          {user.display_name || user.email.split("@")[0]}
        </span>
      </Link>
      <button
        onClick={handleLogout}
        title="Sign out"
        aria-label="Sign out"
        className="flex h-[34px] w-8 items-center justify-center rounded-sm border-2 border-[var(--app-hud-line)] bg-[var(--app-panel-alt)] text-[var(--app-ink-soft)] hover:border-[var(--chart-critical)] hover:text-[var(--chart-critical)]"
      >
        <LogOut size={14} />
      </button>
    </div>
  );
}
