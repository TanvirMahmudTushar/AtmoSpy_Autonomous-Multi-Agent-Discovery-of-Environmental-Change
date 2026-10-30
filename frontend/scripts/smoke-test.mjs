/**
 * Headless-browser smoke test: loads every top-level page plus one finding
 * detail page and fails if the browser logs any console/page error.
 *
 * This exists because several real bugs in this app (a trend line rendered
 * off-chart, a MapLibre map that hung forever with zero console output)
 * were invisible to `tsc`/`next build` and only showed up when the pages
 * were actually rendered in a browser — see the MapLibre note in the root
 * README. `npx tsc --noEmit` and `next build` alone are not enough
 * end-to-end verification for this app.
 *
 * Usage: start the backend (port 8000) and `next start` (or `next dev`),
 * then: node scripts/smoke-test.mjs [baseUrl]
 */
import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright";

const BASE = process.argv[2] || "http://localhost:3000";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const PAGES = [
  "/", "/detect", "/discover", "/investigate", "/globe", "/watches", "/findings", "/about", "/learn",
  "/demos", "/demos/not-significant-yet", "/login", "/signup", "/home",
];

// Pages audited for accessibility (WCAG 2 A/AA). Serious and critical
// violations fail the run; moderate and minor ones are listed only.
const A11Y_PAGES = new Set(["/detect", "/learn", "/demos", "/demos/not-significant-yet", "/about", "/investigate"]);
const a11yFailures = [];

async function audit(path) {
  // The map canvas is third-party WebGL output; audit everything around it.
  const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).exclude(".maplibregl-map").analyze();
  for (const v of result.violations) {
    const line = `${path}: [${v.impact}] ${v.id} — ${v.help} (${v.nodes.length} element(s), e.g. ${v.nodes[0]?.target.join(" ")})`;
    if (v.impact === "serious" || v.impact === "critical") a11yFailures.push(line);
    else console.log(`  a11y note ${line}`);
  }
}

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();

const errors = [];
page.on("pageerror", (e) => errors.push(`[pageerror] ${e.message}`));
page.on("console", (m) => {
  if (m.type() === "error") errors.push(`[console] ${m.text()}`);
});

for (const path of PAGES) {
  await page.goto(`${BASE}${path}`, { waitUntil: "load", timeout: 20000 });
  // a demo replays its agent log for a few seconds before the report and tour appear
  await page.waitForTimeout(path.startsWith("/demos/") ? 6000 : 500);
  if (A11Y_PAGES.has(path)) await audit(path);
  console.log(`checked ${path}`);
}

try {
  const res = await page.request.get(`${API_BASE}/api/findings?limit=1`);
  const findings = await res.json();
  if (findings.length > 0) {
    await page.goto(`${BASE}/findings/${findings[0].id}`, { waitUntil: "load", timeout: 20000 });
    await page.waitForTimeout(3000); // MapLibre/Recharts need real time to finish loading
    await audit(`/findings/${findings[0].id}`);
    console.log(`checked /findings/${findings[0].id}`);
  } else {
    console.log("no findings in the database yet — skipped the detail-page check");
  }
} catch (err) {
  console.log("could not reach the backend to fetch a finding to check:", err.message);
}

await browser.close();

if (errors.length > 0) {
  console.error(`\n${errors.length} browser error(s):\n${errors.join("\n")}`);
  process.exit(1);
}
if (a11yFailures.length > 0) {
  console.error(`\n${a11yFailures.length} serious accessibility violation(s):\n${a11yFailures.join("\n")}`);
  process.exit(1);
}
console.log("\nNo console/page errors across all pages, and no serious accessibility violations.");
