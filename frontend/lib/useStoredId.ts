"use client";

import { useCallback, useSyncExternalStore } from "react";

// A string kept in sessionStorage so a running scan or investigation (which
// lives on the backend) can be re-attached after the user navigates away and
// back. Falls back to memory when storage is unavailable (private mode).
const listeners = new Set<() => void>();
const memory = new Map<string, string | null>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function read(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return memory.get(key) ?? null;
  }
}

function write(key: string, id: string | null) {
  memory.set(key, id);
  try {
    if (id) sessionStorage.setItem(key, id);
    else sessionStorage.removeItem(key);
  } catch {
    // memory only
  }
  listeners.forEach((l) => l());
}

export function useStoredId(key: string): [string | null, (id: string | null) => void] {
  const id = useSyncExternalStore(
    subscribe,
    () => read(key),
    () => null
  );
  const set = useCallback((next: string | null) => write(key, next), [key]);
  return [id, set];
}
