import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatSigFig(n: number, digits = 3): string {
  if (n === 0) return "0";
  const abs = Math.abs(n);
  if (abs >= 100) return n.toFixed(1);
  if (abs >= 1) return n.toFixed(2);
  return n.toPrecision(digits);
}

export function formatPercent(n: number | null | undefined): string {
  if (n === null || n === undefined) return "n/a";
  return `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
}

export function formatPValue(p: number): string {
  if (p < 0.0001) return "p < 0.0001";
  return `p = ${p.toFixed(4)}`;
}

export function formatRelativeTime(iso: string): string {
  const diffMs = new Date(iso).getTime() - Date.now();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "today";
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (Math.abs(diffDays) < 30) return rtf.format(diffDays, "day");
  return rtf.format(Math.round(diffDays / 30), "month");
}
