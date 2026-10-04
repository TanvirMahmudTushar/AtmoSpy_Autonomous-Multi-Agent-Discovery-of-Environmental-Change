"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/AuthContext";
import { PixelButton, PixelLinkButton } from "@/components/ui/button";

// The landing page's own auth entry point — there is no top-level NavBar or
// header on "/" any more, so this is the only way in. Discover/Investigate
// used to sit here as direct links that skipped auth entirely; now the
// landing page's job is purely to get a session started before handing off
// to /home.
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
    return <div className="h-[52px] w-64 animate-pulse rounded-sm bg-[var(--app-panel-alt)]" />;
  }

  if (user) {
    return (
      <PixelLinkButton href="/home" variant="primary" size="lg">
        Go to Mission Console
      </PixelLinkButton>
    );
  }

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="flex flex-col gap-4 sm:flex-row">
        <PixelLinkButton href="/login" variant="primary" size="lg">
          Sign In
        </PixelLinkButton>
        <PixelLinkButton href="/signup" variant="gold" size="lg">
          Create Account
        </PixelLinkButton>
      </div>
      <PixelButton type="button" variant="ghost" size="sm" onClick={handleGuest} disabled={guestLoading}>
        {guestLoading ? "Starting..." : "Continue as Guest"}
      </PixelButton>
      {error && <p className="text-xs text-[var(--chart-critical)]">{error}</p>}
    </div>
  );
}
