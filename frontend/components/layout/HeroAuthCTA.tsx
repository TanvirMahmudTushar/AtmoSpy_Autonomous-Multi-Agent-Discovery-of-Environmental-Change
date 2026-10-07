"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/AuthContext";
import { PixelButton, PixelLinkButton } from "@/components/ui/button";

// The landing page's own auth entry point — there is no NavBar on "/", so
// this (in the landing page's top-right header) is the only way in.
// Discover/Investigate used to sit here as direct links that skipped auth
// entirely; now the landing page's job is purely to get a session started
// before handing off to /home.
export function HeroAuthCTA() {
  const { user, loading, loginAsGuest, error, clearError } = useAuth();
  const router = useRouter();
  const [guestLoading, setGuestLoading] = useState(false);

  async function handleGuest() {
    setGuestLoading(true);
    clearError();
    try {
      await loginAsGuest();
      router.push("/home");
    } catch {
      // error already surfaced via context, rendered below
    } finally {
      setGuestLoading(false);
    }
  }

  if (loading) {
    return <div className="h-[34px] w-72 animate-pulse rounded-sm bg-[var(--app-panel-alt)]" />;
  }

  if (user) {
    return (
      <PixelLinkButton href="/home" variant="primary" size="sm">
        Go to Mission Console
      </PixelLinkButton>
    );
  }

  return (
    <div className="relative flex flex-wrap items-center justify-center gap-2 sm:justify-end">
      <PixelLinkButton href="/login" variant="primary" size="sm">
        Sign In
      </PixelLinkButton>
      <PixelLinkButton href="/signup" variant="gold" size="sm">
        Create Account
      </PixelLinkButton>
      <PixelButton type="button" variant="ghost" size="sm" onClick={handleGuest} disabled={guestLoading}>
        {guestLoading ? (
          "Starting..."
        ) : (
          <>
            <span className="sm:hidden">Guest</span>
            <span className="hidden sm:inline">Continue as Guest</span>
          </>
        )}
      </PixelButton>
      {error && (
        <p className="absolute right-0 top-full mt-2 text-xs text-[var(--chart-critical)]" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
