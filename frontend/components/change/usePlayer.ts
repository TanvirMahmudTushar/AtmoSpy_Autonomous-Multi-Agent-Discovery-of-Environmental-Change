"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * A year that can be scrubbed by hand or played from `start` to `end`.
 * `year` is fractional while playing so scenes glide; callers round it for
 * anything that should snap to a whole year (slider value, frame lookup).
 */
export function usePlayer(start: number, end: number, seconds = 7) {
  const [year, setYear] = useState(end);
  const [playing, setPlaying] = useState(false);
  const yearRef = useRef(year);
  useEffect(() => {
    yearRef.current = year;
  }, [year]);

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    // The loop owns its position rather than re-reading state each frame, so a
    // frame that fires before React has committed the last setYear can't lose time.
    let pos = yearRef.current;
    const step = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      pos = Math.min(end, pos + ((end - start) / seconds) * dt);
      setYear(pos);
      if (pos >= end) setPlaying(false);
      else raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [playing, start, end, seconds]);

  const toggle = useCallback(() => {
    if (playing) return setPlaying(false);
    if (yearRef.current >= end) setYear(start);
    setPlaying(true);
  }, [playing, start, end]);

  const scrub = useCallback((y: number) => {
    setPlaying(false);
    setYear(y);
  }, []);

  return { year, playing, toggle, scrub, pause: () => setPlaying(false) };
}
