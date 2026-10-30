// Lets Next partially prefetch this dynamic route (layout + this fallback
// only) and switch to it instantly on click, instead of waiting for the
// server render — which calls the backend for the page metadata.
export default function Loading() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <p className="text-sm text-[var(--app-muted)]">Loading...</p>
    </div>
  );
}
