"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";
import { Panel } from "@/components/ui/panel";
import { PixelButton } from "@/components/ui/button";
import { PixelSprite } from "@/components/pixel/PixelSprite";

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginPageInner />
    </Suspense>
  );
}

function LoginPageInner() {
  const { login, loginAsGuest, error, clearError } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("redirect") || "/home";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [guestLoading, setGuestLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    clearError();
    try {
      await login(email, password);
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
      <PixelSprite name="compass" size={44} />
      <h1 className="mt-4 font-display text-[16px] text-[var(--app-ink)]">Mission Login</h1>
      <p className="mt-2 text-center text-sm text-[var(--app-ink-soft)]">
        Sign in to save investigations to your research journal and pick up where you left off.
      </p>

      <Panel variant="hud" className="mt-8 w-full">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
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
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-sm border-2 border-[var(--app-border)]/40 bg-[var(--app-panel-alt)] p-2.5 text-sm text-[var(--app-ink)] outline-none focus:border-[var(--app-accent-cyan)]"
              placeholder="********"
              autoComplete="current-password"
            />
          </label>

          {error && (
            <p className="rounded-sm border border-[var(--chart-critical)] bg-[var(--app-panel-alt)] px-3 py-2 text-xs text-[var(--chart-critical)]">
              {error}
            </p>
          )}

          <PixelButton type="submit" disabled={submitting || guestLoading} className="mt-2">
            {submitting ? "Signing in..." : "Sign In"}
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
        No account?{" "}
        <Link href="/signup" className="text-[var(--app-accent-cyan)] underline underline-offset-2">
          Create one
        </Link>
      </p>
      <p className="mt-2 text-xs text-[var(--app-muted)]">
        You don&apos;t need an account to use Discover or Investigate — signing in just saves your history.
      </p>
    </div>
  );
}
