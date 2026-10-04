import { API_URL } from "@/lib/api";
import type { FindingDetail } from "@/lib/types";

// NEXT_PUBLIC_API_URL is baked into the client bundle for the *browser* to
// use (e.g. "http://localhost:8000" when the backend's port is published to
// the host). Server-side code running inside a container needs a different
// address for the same backend — the Docker Compose service name
// ("http://backend:8000"), not "localhost", which inside that container
// refers to the frontend container itself. INTERNAL_API_URL (no NEXT_PUBLIC_
// prefix, so it's never sent to the browser) lets docker-compose override
// just the server-side address; plain `next dev` on the host has no need
// for it since client and server share the same localhost there.
const SERVER_API_URL = process.env.INTERNAL_API_URL || API_URL;

// Shared by generateMetadata (page.tsx) and the dynamic OG image route —
// both need the same finding fetched server-side, so this is the one place
// that talks to the backend for this route segment.
export async function fetchFindingServer(id: string): Promise<FindingDetail | null> {
  try {
    const res = await fetch(`${SERVER_API_URL}/api/findings/${id}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as FindingDetail;
  } catch {
    return null;
  }
}
