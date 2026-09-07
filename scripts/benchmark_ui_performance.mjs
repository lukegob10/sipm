#!/usr/bin/env node
// Local, disposable SQLite journeys. Never accepts a remote server or production data.
import { spawn, execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, request } from "playwright";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
function option(name, fallback) {
  const at = args.indexOf(`--${name}`);
  if (at === -1) return fallback;
  if (!args[at + 1] || args[at + 1].startsWith("--")) throw new Error(`Missing --${name} value`);
  return args[at + 1];
}
const known = new Set(["source-root", "output-dir", "runs", "tasks", "port", "python", "latency-ms", "download-mbps", "cpu-rate"]);
for (let i = 0; i < args.length; i += 2) {
  if (!known.has(args[i].replace(/^--/, ""))) throw new Error(`Unknown option ${args[i]}`);
}
function boundedNumber(name, fallback, min, max) {
  const value = Number(option(name, fallback));
  if (!Number.isFinite(value) || value < min || value > max) throw new Error(`Invalid --${name}`);
  return value;
}
const sourceRoot = path.resolve(option("source-root", repoRoot));
const outputDir = path.resolve(option("output-dir", path.join(repoRoot, ".tmp/performance-baseline", new Date().toISOString().replaceAll(/[:.]/g, "-"))));
const runs = boundedNumber("runs", 10, 1, 100);
const taskCount = boundedNumber("tasks", 100, 1, 10000);
const port = boundedNumber("port", 8774, 1024, 65535);
if (![runs, taskCount, port].every(Number.isInteger)) throw new Error("Runs, tasks and port must be integers");
const profile = {
  viewport: { width: 1440, height: 1000 },
  latencyMs: boundedNumber("latency-ms", 50, 0, 10000),
  downloadMbps: boundedNumber("download-mbps", 20, 0.1, 1000),
  cpuRate: boundedNumber("cpu-rate", 1, 1, 20),
};
const baseURL = `http://127.0.0.1:${port}`;
const api = "/project-manager/api";
const password = "LocalBenchmark123";
const soeid = `bench${Date.now()}`;
const round = (value) => Math.round(value * 10) / 10;
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const git = (...parameters) => execFileSync("git", ["-C", sourceRoot, ...parameters], { encoding: "utf8", windowsHide: true }).trim();

// Refuse an existing listener: all mutations must target our newly spawned fixture.
await new Promise((resolve, reject) => {
  const probe = createServer();
  probe.once("error", reject);
  probe.listen(port, "127.0.0.1", () => probe.close(resolve));
});
await mkdir(path.dirname(outputDir), { recursive: true });
await mkdir(outputDir); // Deliberately fail rather than overwrite a previous report.
const sourceFiles = ["scripts/run_ui_smoke_app.py", "src/main/ui/js/app.js", "src/main/ui/index.html"];
const sourceHashes = {};
for (const file of sourceFiles) sourceHashes[file] = createHash("sha256").update(await readFile(path.join(sourceRoot, file))).digest("hex");
const report = {
  startedAt: new Date().toISOString(),
  sourceRoot, revision: git("rev-parse", "HEAD"), sourceChanges: git("status", "--short"), sourceHashes,
  environment: { platform: os.platform(), release: os.release(), architecture: os.arch(), cpu: os.cpus()[0]?.model, logicalCpus: os.cpus().length, memoryGiB: round(os.totalmem() / 2 ** 30), node: process.version },
  profile, fixture: { storage: "disposable SQLite", coordination: "memory", users: 1, spaces: 1, programs: 1, projects: 10, solutions: 10, tasks: taskCount, bcryptRounds: 12 },
  samples: [], failures: [],
  boundaries: {
    coldSignIn: "navigation start to visible enabled auth inputs and submit button, followed by one animation frame; a new browser context per sample",
    login: "captured login-form submit event to active Deliverables with all ten seeded solution rows, the seeded project title and usable search, followed by one animation frame",
    reload: "navigation start on authenticated same-context reload to the same Deliverables readiness check; browser HTTP cache retained",
    firstTasks: "captured navigation click to active Tasks with every seeded task row and enabled search, followed by one animation frame; data may have been prefetched",
    warmNavigation: "captured navigation click between previously opened Tasks and Deliverables to the same per-route readiness checks, followed by one animation frame",
    resources: "resource timing entries completed by readiness and started inside the journey; document navigation timing added for full loads; transferSize includes browser-estimated headers; request-start lists cover the harness observation stage through snapshot collection and can include requests still pending at readiness",
  },
};
let serverLog = "";
let serverError;
const server = spawn(option("python", process.platform === "win32" ? "python" : "python3"), ["scripts/run_ui_smoke_app.py"], {
  cwd: sourceRoot, windowsHide: true, stdio: ["ignore", "pipe", "pipe"],
  env: { ...process.env, ENV: "dev", SIPM_ENV_OVERRIDE: "false", SIPM_COORDINATION_BACKEND: "memory", SIPM_DISABLE_STARTUP: "true", SIPM_KEEPALIVE_TASK: "false", SIPM_UI_SMOKE_PORT: String(port), SIPM_SECRET_KEY: "local-disposable-performance-fixture-secret-only", SIPM_SECURE_COOKIES: "false", SIPM_ALLOW_SELF_REGISTER: "true", SIPM_BCRYPT_ROUNDS: "12", SIPM_ACCESS_MINUTES: "60", SIPM_REFRESH_MINUTES: "60" },
});
server.on("error", (error) => { serverError = error; });
server.stdout.on("data", (chunk) => { serverLog += chunk; });
server.stderr.on("data", (chunk) => { serverLog += chunk; });
let browser;
let seed;

async function post(url, data = {}) {
  const response = await seed.post(`${api}${url}`, { data });
  if (!response.ok()) throw new Error(`Fixture POST ${url}: HTTP ${response.status()} ${await response.text()}`);
  return response.status() === 204 ? null : response.json();
}

function installReadinessMonitor({ count }) {
  const stats = window.__sipmBenchmark = { marks: {}, longTasks: [], active: null };
  const visible = (element) => element && element.getClientRects().length > 0 && getComputedStyle(element).visibility !== "hidden";
  const usable = (selector) => { const element = document.querySelector(selector); return visible(element) && !element.disabled; };
  const routeReady = (route) => {
    if (!visible(document.querySelector(`#view-${route}.active`)) || !visible(document.querySelector("#app-shell"))) return false;
    if (route === "master") return document.querySelectorAll("#master-table .deliverable-row-solution").length === 10
      && document.querySelector("#master-table")?.textContent.includes("Benchmark Project 00") && usable("#filter-query");
    return document.querySelectorAll("#tasks-workbench-table tbody tr[data-id]").length === count && usable("#tasks-workbench-search");
  };
  stats.arm = (name, route, start = performance.now()) => { stats.active = { name, route, start, confirming: false }; };
  document.addEventListener("submit", (event) => {
    if (event.target.id === "login-form") stats.arm("login", "master");
  }, true);
  document.addEventListener("click", (event) => {
    const navigation = event.target.closest(".nav-btn[data-view]");
    if (navigation && stats.nextNavigation) {
      stats.arm(stats.nextNavigation, navigation.dataset.view);
      stats.nextNavigation = null;
    }
  }, true);
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) stats.longTasks.push({ startTime: entry.startTime, duration: entry.duration });
    }).observe({ type: "longtask", buffered: true });
  } catch { /* Unsupported entry types are reported via browser metadata. */ }
  stats.arm("document", "document", 0);
  const poll = () => {
    const active = stats.active;
    if (active && !active.confirming) {
      const signedOut = active.route === "document" && usable('#login-form input[name="soeid"]') && usable('#login-form input[name="password"]') && usable('#login-form button[type="submit"]');
      const ready = signedOut || routeReady(active.route === "document" ? "master" : active.route);
      if (ready) {
        active.confirming = true;
        requestAnimationFrame(() => {
          // One rendering opportunity after readiness; never equate a shell placeholder with content.
          if (stats.active === active && (signedOut ? usable('#login-form input[name="soeid"]') : routeReady(active.route === "document" ? "master" : active.route))) {
            const end = performance.now();
            stats.marks[active.name] = { start: active.start, end, duration: end - active.start, kind: signedOut ? "sign-in" : "route-content" };
            stats.active = null;
          } else if (stats.active === active) active.confirming = false;
        });
      }
    }
    requestAnimationFrame(poll);
  };
  requestAnimationFrame(poll);
}

async function snapshot(page, name, requestsByStage, stage) {
  await page.waitForFunction((key) => Boolean(window.__sipmBenchmark?.marks[key]), name, { timeout: 30000 });
  return page.evaluate(({ key, starts }) => {
    const bench = window.__sipmBenchmark;
    const mark = bench.marks[key];
    const resources = performance.getEntriesByType("resource").filter((entry) => entry.startTime >= mark.start && entry.responseEnd <= mark.end).map((entry) => ({
      path: new URL(entry.name).pathname, initiatorType: entry.initiatorType, startTime: entry.startTime, duration: entry.duration,
      transferSize: entry.transferSize, encodedBodySize: entry.encodedBodySize, decodedBodySize: entry.decodedBodySize, responseStatus: entry.responseStatus,
    }));
    const navigation = key === "document" ? performance.getEntriesByType("navigation").map((entry) => ({ path: new URL(entry.name).pathname, initiatorType: "navigation", startTime: 0, duration: entry.duration, transferSize: entry.transferSize, encodedBodySize: entry.encodedBodySize, decodedBodySize: entry.decodedBodySize, responseStatus: entry.responseStatus })) : [];
    resources.push(...navigation);
    const longTasks = bench.longTasks.filter((entry) => entry.startTime >= mark.start && entry.startTime <= mark.end);
    return { ...mark, requestStarts: starts, resources, longTasks, domElements: document.querySelectorAll("*").length,
      totalTransferBytes: resources.reduce((sum, entry) => sum + entry.transferSize, 0),
      encodedBodyBytes: resources.reduce((sum, entry) => sum + entry.encodedBodySize, 0),
      decodedBodyBytes: resources.reduce((sum, entry) => sum + entry.decodedBodySize, 0),
      javascript: resources.filter((entry) => entry.path.endsWith(".js")), stylesheets: resources.filter((entry) => entry.path.endsWith(".css")),
    };
  }, { key: name, starts: requestsByStage[stage] || [] });
}

function distribution(values) {
  const ordered = [...values].sort((a, b) => a - b);
  const percentile = (p) => round(ordered[Math.max(0, Math.ceil(p * ordered.length) - 1)]);
  return { samples: ordered.length, min: round(ordered[0]), p50: percentile(0.5), p75: percentile(0.75), p95: percentile(0.95), max: round(ordered.at(-1)) };
}

try {
  for (let attempt = 0; attempt < 120; attempt++) {
    if (serverError) throw serverError;
    if (server.exitCode !== null) throw new Error(`Smoke server exited with ${server.exitCode}`);
    const healthy = await fetch(`${baseURL}/health`, { signal: AbortSignal.timeout(1000) }).then((response) => response.ok).catch(() => false);
    if (healthy) break;
    if (attempt === 119) throw new Error("Smoke server readiness timed out");
    await delay(500);
  }
  seed = await request.newContext({ baseURL });
  await post("/auth/register", { soeid, display_name: "Performance Fixture User", password });
  const space = await post("/spaces/personal");
  await post("/auth/active-space", { space_id: space.space_id });
  const program = await post("/programs", { program_name: "Benchmark Program", description: "Disposable synthetic benchmark data." });
  const solutions = [];
  for (let index = 0; index < 10; index++) {
    const suffix = String(index).padStart(2, "0");
    const project = await post("/projects", { program_id: program.program_id, project_name: `Benchmark Project ${suffix}`, sponsor: "Synthetic Sponsor", description: "Synthetic project description." });
    const solution = await post(`/projects/${project.project_id}/solutions`, { solution_name: `Benchmark Solution ${suffix}`, description: "Synthetic solution description." });
    solutions.push(solution);
  }
  for (let index = 0; index < taskCount; index++) {
    await post(`/solutions/${solutions[index % solutions.length].solution_id}/tasks`, { task_name: `Benchmark Task ${String(index).padStart(5, "0")}`, description: "Synthetic task description for a reproducible local UI benchmark.", assignee: "Performance Fixture User", assignee_user_soeid: soeid });
  }
  await post("/auth/logout");
  await seed.dispose();
  seed = null;
  browser = await chromium.launch({ headless: true });
  report.environment.browser = browser.version();
  for (let run = 1; run <= runs; run++) {
    const context = await browser.newContext({ viewport: profile.viewport, baseURL, reducedMotion: "reduce" });
    await context.addInitScript(installReadinessMonitor, { count: taskCount });
    if (run === 1) await context.tracing.start({ screenshots: true, snapshots: true, sources: false });
    const page = await context.newPage();
    const cdp = await context.newCDPSession(page);
    await cdp.send("Network.enable");
    await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: profile.latencyMs, downloadThroughput: profile.downloadMbps * 1e6 / 8, uploadThroughput: profile.downloadMbps * 1e6 / 8, connectionType: "ethernet" });
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: profile.cpuRate });
    let stage = "coldSignIn";
    const starts = {};
    const sample = { run, traced: run === 1, errors: [], httpErrors: [], requestFailures: [], responses: [] };
    const networkResponses = new Map();
    const wireStatuses = new Map();
    cdp.on("Network.responseReceivedExtraInfo", ({ requestId, statusCode }) => {
      wireStatuses.set(requestId, statusCode);
      const response = networkResponses.get(requestId);
      if (response) response.wireStatus = statusCode;
    });
    cdp.on("Network.responseReceived", ({ requestId, response }) => {
      const headers = Object.fromEntries(Object.entries(response.headers).map(([name, value]) => [name.toLowerCase(), value]));
      const entry = { stage, path: new URL(response.url).pathname, status: response.status, wireStatus: wireStatuses.get(requestId), protocol: response.protocol, fromDiskCache: Boolean(response.fromDiskCache), fromServiceWorker: Boolean(response.fromServiceWorker), cacheControl: headers["cache-control"] || null, contentEncoding: headers["content-encoding"] || null };
      networkResponses.set(requestId, entry);
      sample.responses.push(entry);
    });
    page.on("request", (req) => { (starts[stage] ||= []).push({ method: req.method(), path: new URL(req.url()).pathname, type: req.resourceType() }); });
    page.on("pageerror", (error) => { sample.errors.push(error.message); });
    page.on("response", (response) => { if (response.status() >= 400) sample.httpErrors.push({ stage, path: new URL(response.url()).pathname, status: response.status() }); });
    page.on("requestfailed", (req) => { sample.requestFailures.push({ stage, path: new URL(req.url()).pathname, error: req.failure()?.errorText }); });
    try {
      await page.goto("/project-manager/", { waitUntil: "domcontentloaded" });
      sample.coldSignIn = await snapshot(page, "document", starts, stage);
      if (sample.coldSignIn.kind !== "sign-in") throw new Error("Cold visit was not signed out");
      if (run === 1) await page.screenshot({ path: path.join(outputDir, "cold-sign-in.png"), fullPage: true });
      await page.locator('#login-form input[name="soeid"]').fill(soeid);
      await page.locator('#login-form input[name="password"]').fill(password);
      stage = "login";
      await page.locator('#login-form input[name="password"]').press("Enter");
      sample.login = await snapshot(page, "login", starts, stage);
      if (run === 1) await page.screenshot({ path: path.join(outputDir, "deliverables.png"), fullPage: true });
      stage = "reload";
      await page.reload({ waitUntil: "domcontentloaded" });
      sample.reload = await snapshot(page, "document", starts, stage);
      if (sample.reload.kind !== "route-content") throw new Error("Authenticated reload returned to sign in");
      for (const [name, route] of [["firstTasks", "tasks-workbench"], ["warmDeliverables", "master"], ["warmTasks", "tasks-workbench"]]) {
        stage = name;
        await page.evaluate((key) => { window.__sipmBenchmark.nextNavigation = key; }, name);
        await page.locator(`.nav-btn[data-view="${route}"]`).click();
        sample[name] = await snapshot(page, name, starts, stage);
      }
      if (run === 1) await page.screenshot({ path: path.join(outputDir, "tasks.png"), fullPage: true });
      if (sample.errors.length) throw new Error(`Browser errors: ${sample.errors.join("; ")}`);
      const unexpectedHttp = sample.httpErrors.filter((entry) => !(entry.stage === "coldSignIn" && entry.status === 401 && ["/auth/me", "/auth/refresh", "/auth/bootstrap"].some((route) => entry.path === api + route)));
      if (unexpectedHttp.length) throw new Error(`Unexpected HTTP errors: ${JSON.stringify(unexpectedHttp)}`);
      report.samples.push(sample);
      console.log(JSON.stringify({ run, coldSignInMs: round(sample.coldSignIn.duration), loginMs: round(sample.login.duration), reloadMs: round(sample.reload.duration), firstTasksMs: round(sample.firstTasks.duration), warmTasksMs: round(sample.warmTasks.duration) }));
    } catch (error) {
      report.failures.push({ run, stage, message: error.message, sample });
      await page.screenshot({ path: path.join(outputDir, `failure-${run}.png`), fullPage: true }).catch(() => {});
      throw error;
    } finally {
      if (run === 1) await context.tracing.stop({ path: path.join(outputDir, "first-sample-trace.zip") });
      await context.close();
    }
  }
  report.summary = {};
  for (const journey of ["coldSignIn", "login", "reload", "firstTasks", "warmDeliverables", "warmTasks"]) {
    report.summary[journey] = { durationMs: distribution(report.samples.map((sample) => sample[journey].duration)), transferBytes: distribution(report.samples.map((sample) => sample[journey].totalTransferBytes)), requestStarts: distribution(report.samples.map((sample) => sample[journey].requestStarts.length)), javascriptFiles: distribution(report.samples.map((sample) => sample[journey].javascript.length)) };
  }
  console.log(JSON.stringify({ outputDir, summary: report.summary }, null, 2));
} catch (error) {
  if (!report.failures.length) report.failures.push({ stage: "setup", message: error.message });
  console.error(error);
  process.exitCode = 1;
} finally {
  await Promise.allSettled([seed?.dispose(), browser?.close()]);
  server.kill();
  report.finishedAt = new Date().toISOString();
  await writeFile(path.join(outputDir, "results.json"), JSON.stringify(report, null, 2) + "\n");
  await writeFile(path.join(outputDir, "server.log"), serverLog);
}
