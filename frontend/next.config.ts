import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces a minimal self-contained server (only the files actually
  // needed at runtime, deps pruned) — the standard shape for a lean
  // production Docker image instead of shipping the whole node_modules tree.
  // Skipped on Vercel (which sets VERCEL=1 during builds): it produces its
  // own serverless output and has no use for a self-hosted server.js.
  output: process.env.VERCEL ? undefined : "standalone",
  // Pin the project root: a lockfile in a parent folder (e.g. the home
  // directory) would otherwise make Next.js guess the wrong workspace root.
  turbopack: { root: path.join(__dirname) },
};

export default nextConfig;
