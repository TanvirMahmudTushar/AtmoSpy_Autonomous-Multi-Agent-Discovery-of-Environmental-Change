"use client";

import { Lottie } from "lottie-react";

export function Logo({ size = 28, className }: { size?: number; className?: string }) {
  return (
    <Lottie
      src="/logo.json"
      loop
      autoplay
      style={{ width: size, height: size }}
      className={className}
    />
  );
}
