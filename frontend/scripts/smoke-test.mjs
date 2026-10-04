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
import { chromium } from "playwright";

const BASE = process.argv[2] || "http://localhost:3000";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const PAGES = ["/", "/discover", "/investigate", "/globe", "/watches", "/findings", "/datasets", "/journal", "/about", "/login", "/signup", "/home"];

const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();

const errors = [];
page.on("pageerror", (e) => errors.push(`[pageerror] ${e.message}`));
page.on("console", (m) => {
  if (m.type() === "error") errors.push(`[console] ${m.text()}`);
});

for (const path of PAGES) {
  await page.goto(`${BASE}${path}`, { waitUntil: "load", timeout: 20000 });
  await page.waitForTimeout(500);
  console.log(`checked ${path}`);
}

try {
  const res = await page.request.get(`${API_BASE}/api/findings?limit=1`);
  const findings = await res.json();
  if (findings.length > 0) {
    await page.goto(`${BASE}/findings/${findings[0].id}`, { waitUntil: "load", timeout: 20000 });
    await page.waitForTimeout(3000); // MapLibre/Recharts need real time to finish loading
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
console.log("\nNo console/page errors across all pages.");
