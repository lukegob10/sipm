// Manual localhost benchmark: node <this-file> <baseline-git-revision> [samples]
// Run against scripts/run_ui_smoke_app.py, never a production environment.
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const root = fileURLToPath(new URL("../../../../../", import.meta.url));
const revision = process.argv[2];
if (!revision || revision.startsWith("-")) throw new Error("Supply a baseline git revision.");
const count = Number(process.argv[3] || 30);
if (!Number.isInteger(count) || count < 1) throw new Error("Samples must be a positive integer.");
const baseURL = `http://127.0.0.1:${Number(process.env.SIPM_UI_SMOKE_PORT || 8773)}/project-manager`;
const outputDir = resolve(root, ".tmp/startup-performance");
mkdirSync(outputDir, { recursive: true });
const sourceCache = new Map();
function sourceFor(variant, path) {
  const key = `${variant}:${path}`;
  if (!sourceCache.has(key)) {
    const source = variant === "baseline"
      ? execFileSync("git", ["-c", `safe.directory=${root.replaceAll("\\", "/").replace(/\/$/, "")}`, "show", `${revision}:src/main/ui/js/${path}`], { cwd: root })
      : readFileSync(resolve(root, "src/main/ui/js", path));
    // Git and a Windows checkout can use different line endings. Compare the
    // same source representation so CRLF conversion is not counted as a win.
    sourceCache.set(key, Buffer.from(source.toString("utf8").replaceAll("\r\n", "\n")));
  }
  return sourceCache.get(key);
}

const browser = await chromium.launch();
const browserVersion = browser.version();
const setup = await browser.newContext();
async function post(path, data) {
  const response = await setup.request.post(`${baseURL}/api${path}`, { data });
  if (!response.ok()) throw new Error(`${path}: ${response.status()} ${await response.text()}`);
  return response.json();
}
const soeid = `bench${Date.now()}`;
await post("/auth/register", { soeid, display_name: "Startup benchmark", password: "Password123" });
const space = await post("/spaces/personal", {});
await post("/auth/active-space", { space_id: space.space_id });
await post("/programs", { program_name: "Startup benchmark program" });
const session = await setup.storageState();
await setup.close();

async function sample(variant, authenticated) {
  const context = await browser.newContext({ storageState: authenticated ? session : undefined });
  const page = await context.newPage();
  const assets = new Map();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.addInitScript(() => {
    window.startupListenerCount = 0;
    const add = EventTarget.prototype.addEventListener;
    EventTarget.prototype.addEventListener = function (...args) {
      window.startupListenerCount += 1;
      return add.apply(this, args);
    };
    document.addEventListener("click", (event) => {
      if (event.target.closest?.(".nav-btn")) window.startupJourneyStart = performance.now();
    }, true);
  });
  // Both variants use identical interception, with bytes from the same checkout
  // or its baseline commit. A new context gives a cold module map each sample.
  await page.route("**/js/**", async (route) => {
    const path = new URL(route.request().url()).pathname.split("/js/")[1];
    const source = sourceFor(variant, path);
    assets.set(path, source.length);
    await route.fulfill({ contentType: "text/javascript", body: source });
  });
  await page.goto(`${baseURL}/`);
  if (authenticated) {
    await page.locator("#app-shell:not(.hidden)").waitFor();
    await page.locator("#master-table").getByText("Startup benchmark program", { exact: true }).waitFor();
  } else {
    await page.locator("#auth-screen:not(.hidden)").waitFor();
  }
  const startup = await page.evaluate(() => new Promise((resolveSample) => requestAnimationFrame(() => resolveSample({
    readyMs: performance.now(), listeners: window.startupListenerCount,
  }))));
  const result = { variant, authenticated, ...startup, modules: assets.size, rawJsBytes: [...assets.values()].reduce((a, b) => a + b, 0) };
  if (authenticated) {
    async function navigate(view, selector) {
      await page.locator(`.nav-btn[data-view="${view}"]`).click();
      await page.locator(selector).waitFor();
      return page.evaluate(() => new Promise((resolveSample) => requestAnimationFrame(() => resolveSample(performance.now() - window.startupJourneyStart))));
    }
    result.firstCapacityMs = await navigate("team-capacity", "#capacity-user-list tr[data-soeid]");
    await navigate("master", "#master-table table");
    const modulesBeforeRepeat = assets.size;
    result.repeatCapacityMs = await navigate("team-capacity", "#capacity-user-list tr[data-soeid]");
    result.repeatNewModules = assets.size - modulesBeforeRepeat;
  }
  if (errors.length) throw new Error(errors.join("\n"));
  await context.close();
  return result;
}

const samples = [];
try {
  // Prime source reads and runtime once; exclude these runs from distributions.
  for (const variant of ["baseline", "current"]) {
    await sample(variant, false);
    await sample(variant, true);
  }
  for (let index = 0; index < count; index += 1) {
    const variants = index % 2 ? ["current", "baseline"] : ["baseline", "current"];
    for (const variant of variants) {
      samples.push({ index, ...await sample(variant, false) });
      samples.push({ index, ...await sample(variant, true) });
    }
    if ((index + 1) % 5 === 0) process.stdout.write(`Completed ${index + 1}/${count} alternating pairs\n`);
  }
} finally {
  await browser.close();
}

function distribution(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const percentile = (p) => Number(sorted[Math.ceil(sorted.length * p) - 1].toFixed(2));
  return { count: sorted.length, p50: percentile(0.5), p75: percentile(0.75), p95: percentile(0.95), min: sorted[0], max: sorted.at(-1) };
}
const summary = {};
for (const variant of ["baseline", "current"]) {
  for (const authenticated of [false, true]) {
    const rows = samples.filter((row) => row.variant === variant && row.authenticated === authenticated);
    summary[`${variant}-${authenticated ? "restored" : "signed-out"}`] = Object.fromEntries(
      ["readyMs", "listeners", "modules", "rawJsBytes", ...(authenticated ? ["firstCapacityMs", "repeatCapacityMs", "repeatNewModules"] : [])]
        .map((key) => [key, distribution(rows.map((row) => row[key]))]),
    );
  }
}
const report = { baseline: revision, baseURL, browser: `Chromium ${browserVersion}`, node: process.version, platform: process.platform, recordedAt: new Date().toISOString(), viewport: { width: 1280, height: 720 }, samples, summary };
writeFileSync(resolve(outputDir, "samples.json"), JSON.stringify(report, null, 2));
process.stdout.write(`${JSON.stringify(summary, null, 2)}\nRaw samples: ${outputDir}/samples.json\n`);
