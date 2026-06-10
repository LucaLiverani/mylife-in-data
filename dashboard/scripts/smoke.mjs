#!/usr/bin/env node
/**
 * Mocks-backed smoke test. Zero secrets, zero backend: boots `wrangler pages
 * dev` against the built dist/ (Functions run locally in workerd; with no
 * ClickHouse env vars every endpoint falls back to public/mocks/), then:
 *
 *   1. For every mock file, asserts GET /api/<path> returns 200 with
 *      `X-Data-Source: cache` and a JSON body. This both proves the Function
 *      routes build/run and catches a mock whose endpoint disappeared.
 *   2. Drives every route with headless chromium at 390px (mobile) and
 *      desktop width, with reducedMotion: 'reduce' (page sections sit in
 *      scroll-triggered FadeIn wrappers and render blank otherwise), failing
 *      on uncaught page errors and horizontal overflow
 *      (scrollWidth > clientWidth on documentElement).
 *
 * Used by CI (npm run smoke) after `npm run build`; works locally the same
 * way. Port: 8788 (kill leaked runtimes with `fuser -k 8788/tcp`).
 */

import { spawn } from "node:child_process";
import { readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const BASE = "http://127.0.0.1:8788";
const ROUTES = ["/", "/spotify", "/youtube", "/google", "/maps", "/now", "/system"];

const failures = [];
const note = (msg) => console.log(msg);
const fail = (msg) => {
  failures.push(msg);
  console.error(`  ✗ ${msg}`);
};

function mockEndpoints() {
  const mocksDir = join(ROOT, "public", "mocks");
  const out = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir)) {
      const p = join(dir, entry);
      if (statSync(p).isDirectory()) walk(p);
      else if (entry.endsWith(".json"))
        out.push("/api/" + relative(mocksDir, p).replace(/\.json$/, ""));
    }
  };
  walk(mocksDir);
  return out.sort();
}

async function waitForServer(timeoutMs = 120_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(BASE + "/", { signal: AbortSignal.timeout(3_000) });
      if (res.ok) return;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 1_000));
  }
  throw new Error(`pages dev server never became ready on ${BASE}`);
}

async function checkApi() {
  note("→ API endpoints (expect 200 + X-Data-Source: cache):");
  for (const endpoint of mockEndpoints()) {
    try {
      const res = await fetch(BASE + endpoint, { signal: AbortSignal.timeout(15_000) });
      const source = res.headers.get("x-data-source");
      if (res.status !== 200) {
        fail(`${endpoint} → HTTP ${res.status}`);
        continue;
      }
      if (source !== "cache") {
        fail(`${endpoint} → X-Data-Source: ${source ?? "<missing>"} (expected cache)`);
        continue;
      }
      await res.json(); // throws on non-JSON
      note(`  ✓ ${endpoint}`);
    } catch (err) {
      fail(`${endpoint} → ${err.message}`);
    }
  }
}

async function checkRoutes(browser, { width, height, label }) {
  note(`→ Routes at ${width}px (${label}):`);
  const context = await browser.newContext({
    viewport: { width, height },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const pageErrors = [];
  page.on("pageerror", (err) => pageErrors.push(err.message));

  for (const route of ROUTES) {
    pageErrors.length = 0;
    try {
      await page.goto(BASE + route, { waitUntil: "load", timeout: 30_000 });
      // Let the data hooks resolve + first paint settle (mocks are local, fast).
      await page.waitForTimeout(1_500);

      const { scrollWidth, clientWidth, textLength } = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
        textLength: document.body.innerText.trim().length,
      }));

      if (scrollWidth > clientWidth)
        fail(`${route} @${width}px → horizontal overflow (scrollWidth ${scrollWidth} > clientWidth ${clientWidth})`);
      else if (textLength === 0) fail(`${route} @${width}px → rendered blank`);
      else if (pageErrors.length > 0)
        fail(`${route} @${width}px → uncaught page error: ${pageErrors[0]}`);
      else note(`  ✓ ${route}`);
    } catch (err) {
      fail(`${route} @${width}px → ${err.message}`);
    }
  }
  await context.close();
}

async function main() {
  note("→ Starting wrangler pages dev...");
  const server = spawn(
    "npx",
    ["wrangler", "pages", "dev", "dist", "--compatibility-date=2024-11-16", "--port", "8788"],
    { cwd: ROOT, stdio: ["ignore", "pipe", "pipe"], detached: true }
  );
  server.stdout.on("data", () => {});
  server.stderr.on("data", () => {});
  const stopServer = () => {
    try {
      process.kill(-server.pid, "SIGTERM");
    } catch {
      /* already gone */
    }
  };
  process.on("exit", stopServer);

  try {
    await waitForServer();
    note(`✓ Server ready on ${BASE}\n`);

    await checkApi();

    const browser = await chromium.launch();
    await checkRoutes(browser, { width: 390, height: 844, label: "mobile" });
    await checkRoutes(browser, { width: 1280, height: 900, label: "desktop" });
    await browser.close();
  } finally {
    stopServer();
  }

  console.log("");
  if (failures.length > 0) {
    console.error(`✗ Smoke test failed (${failures.length} failure${failures.length > 1 ? "s" : ""}).`);
    process.exit(1);
  }
  console.log("✓ Smoke test passed.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
