"use client";

import { useEffect, useRef, useState } from "react";
import type { InvestigationStep } from "./types";

interface StreamState {
  steps: InvestigationStep[];
  done: boolean;
  finalStatus: string | null;
  connectionError: boolean;
}

/**
 * Subscribes to a backend SSE endpoint (/api/investigations/{id}/events or
 * /api/discover/{id}/events) and accumulates the structured agent events —
 * this is the "live reasoning as structured events" surface (spec section
 * 14), never raw chain-of-thought.
 */
export function useAgentStream(url: string | null): StreamState {
  const [steps, setSteps] = useState<InvestigationStep[]>([]);
  const [done, setDone] = useState(false);
  const [finalStatus, setFinalStatus] = useState<string | null>(null);
  const [connectionError, setConnectionError] = useState(false);
  const seenRef = useRef<Set<string>>(new Set());

  // A new stream starts from a clean slate. Reset while rendering when the
  // url changes (React's "adjust state when a prop changes" pattern), so
  // the stale steps never paint for a frame.
  const [streamUrl, setStreamUrl] = useState(url);
  if (url !== streamUrl) {
    setStreamUrl(url);
    setSteps([]);
    setDone(false);
    setFinalStatus(null);
    setConnectionError(false);
  }

  useEffect(() => {
    if (!url) return;
    seenRef.current = new Set();

    const source = new EventSource(url);

    source.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as InvestigationStep;
        const key = `${data.agent}:${data.seq}:${data.message}`;
        if (seenRef.current.has(key)) return;
        seenRef.current.add(key);
        setSteps((prev) => [...prev, data]);
      } catch {
        // ignore malformed frames (e.g. keep-alive comments never reach onmessage)
      }
    };

    source.addEventListener("done", (ev: MessageEvent) => {
      try {
        const data = JSON.parse(ev.data) as { status: string };
        setFinalStatus(data.status);
      } catch {
        setFinalStatus("completed");
      }
      setDone(true);
      source.close();
    });

    source.addEventListener("error", () => {
      setConnectionError(true);
    });

    source.onerror = () => {
      // EventSource auto-retries; if the investigation is already terminal
      // this is expected once the server closes the stream.
    };

    return () => source.close();
  }, [url]);

  return { steps, done, finalStatus, connectionError };
}
