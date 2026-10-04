"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";
import { Panel } from "@/components/ui/panel";
import { PixelButton } from "@/components/ui/button";
import { PixelSprite } from "@/components/pixel/PixelSprite";

export default function SignupPage() {
  return (
    <Suspense fallback={null}>
      <SignupPageInner />
    </Suspense>
  );
}

function SignupPageInner() {
  const { signup, loginAsGuest, error, clearError } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("redirect") || "/home";
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [mismatchError, setMismatchError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [guestLoading, setGuestLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setMismatchError(null);
    if (password !== confirmPassword) {
      setMismatchError("Passwords don't match.");
      return;
    }
    setSubmitting(true);
    clearError();
    try {
      await signup(email, password, displayName || undefined);
      router.push(redirectTo);
    } catch {
      // error already surfaced via context
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGuest() {
    setGuestLoading(true);
    clearError();
    try {
      await loginAsGuest();
      router.push(redirectTo);
    } catch {
      // error already surfaced via context
    } finally {
      setGuestLoading(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-md flex-col items-center px-4 py-16">
      <PixelSprite name="star" size={44} />
      <h1 className="mt-4 font-display text-[16px] text-[var(--app-ink)]">Join the Mission</h1>
      <p className="mt-2 text-center text-sm text-[var(--app-ink-soft)]">
        Create an account to build a personal research journal of investigations and findings.
      </p>

      <Panel variant="hud" className="mt-8 w-full">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="label-telemetry">Display name (optional)</span>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full rounded-sm border-2 border-[var(--app-border)]/40 bg-[var(--app-panel-alt)] p-2.5 text-sm text-[var(--app-ink)] outline-none focus:border-[var(--app-accent-cyan)]"
              placeholder="Dr. Ada Researcher"
              autoComplete="name"
              maxLength={255}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="label-telemetry">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-sm border-2 border-[var(--app-border)]/40 bg-[var(--app-panel-alt)] p-2.5 text-sm text-[var(--app-ink)] outline-none focus:border-[var(--app-accent-cyan)]"
              placeholder="you@example.com"
              autoComplete="email"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="label-telemetry">Password</span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-sm border-2 border-[var(--app-border)]/40 bg-[var(--app-panel-alt)] p-2.5 text-sm text-[var(--app-ink)] outline-none focus:border-[var(--app-accent-cyan)]"
              placeholder="At least 8 characters"
              autoComplete="new-password"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="label-telemetry">Confirm password</span>
            <input
              type="password"
              required
              minLength={8}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full rounded-sm border-2 border-[var(--app-border)]/40 bg-[var(--app-panel-alt)] p-2.5 text-sm text-[var(--app-ink)] outline-none focus:border-[var(--app-accent-cyan)]"
              placeholder="Type it again"
              autoComplete="new-password"
            />
          </label>

          {(mismatchError || error) && (
            <p className="rounded-sm border border-[var(--chart-critical)] bg-[var(--app-panel-alt)] px-3 py-2 text-xs text-[var(--chart-critical)]">
              {mismatchError || error}
            </p>
          )}

          <PixelButton type="submit" variant="gold" disabled={submitting || guestLoading} className="mt-2">
            {submitting ? "Creating account..." : "Create Account"}
          </PixelButton>
        </form>

        <div className="my-4 flex items-center gap-3">
          <div className="h-px flex-1 bg-[var(--app-hud-line)]" />
          <span className="label-telemetry">or</span>
          <div className="h-px flex-1 bg-[var(--app-hud-line)]" />
        </div>

        <PixelButton
          type="button"
          variant="ghost"
          onClick={handleGuest}
          disabled={submitting || guestLoading}
          className="w-full"
        >
          {guestLoading ? "Starting..." : "Continue as Guest"}
        </PixelButton>
        <p className="mt-2 text-center text-xs text-[var(--app-muted)]">
          Instant access to every feature, including Watches — no email needed.
        </p>
      </Panel>

      <p className="mt-6 text-sm text-[var(--app-ink-soft)]">
        Already have an account?{" "}
        <Link href="/login" className="text-[var(--app-accent-cyan)] underline underline-offset-2">
          Sign in
        </Link>
      </p>
    </div>
  );
}
