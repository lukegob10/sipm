# Local login and navigation performance baseline

Date: 2026-09-07. Mode: performance optimization. Baseline: `3e77295342d4314539a151df294f62c6efabcc76`.

This is an actual Chromium baseline for the [performance plan](login-performance-and-responsiveness-plan.md). It establishes a reproducible comparison for behavior-preserving changes. It does not certify production performance or claim that an optimization has shipped.

## Findings supported by this run

1. **High / should-fix: signed-out startup loads substantial route code.** All ten samples loaded 43 JavaScript files, totaling 574,714 body bytes, before the usable sign-in form. Spaces rendering and interactions alone account for 126,609 bytes. The browser also loaded the Deliverables entry module and table module before sign-in. This supports reducing the signed-out import path.
2. **High / should-fix: login and reopening start duplicate collection requests.** Each observed login and reload started two reads each for phases, programs, projects, solutions, and tasks. The first set is enough to render the seeded Deliverables route; the second set continues afterward. In nine samples, starting the subsequent reload canceled a still-running task read from the preceding page. This supports sharing requests and preventing redundant refresh work. It does not establish that the entire duplicate response body was transferred twice before readiness.
3. **Medium / should-fix: warm reload still revalidates every startup asset.** All ten reloads produced 59 HTTP 304 responses for 43 JavaScript and 16 CSS resources. Local assets use `no-cache, max-age=0, must-revalidate`. HTML returns HTTP 200. Local serving is HTTP/1.1 with no `Content-Encoding` header; deployment ingress settings remain unknown. The cache saves body transfer, but retains request and validation latency.
4. **Medium / advisory: the measured 100-task warm routes are already quick.** Warm Deliverables and Tasks completed around 30 ms at the median. No long tasks were observed inside the measured intervals. Larger fixtures, search, editing, and route-owned async screens still need their own evidence before making broader responsiveness claims.

## Environment and measurement contract

- Windows `10.0.26200`, AMD Ryzen 7 5800X, 16 logical CPUs, 63.9 GiB RAM; Node `v20.19.2`; headless Chromium `145.0.7632.6`.
- Desktop viewport: 1440 × 1000. CDP network emulation: 50 ms latency and 20 Mbps in both directions. Normal CPU speed. Reduced-motion preference enabled and held constant for reproducibility.
- Ten sequential samples on a shared development workstation, captured from `2026-09-07T20:28:28Z` to `20:29:06Z`. Full parent test suites were paused during this capture. This is not a dedicated runner or a concurrent-user test.
- The server ran the existing `scripts/run_ui_smoke_app.py` from an unchanged detached worktree at the baseline revision, listening only on `127.0.0.1:8774`. It used a disposable SQLite database and in-memory coordination. No production data, Oracle, Redis, or external server was accessed.
- Synthetic fixture: one local user, one personal space, one program, ten projects, ten solutions, and 100 assigned tasks. The personal-space user is a space administrator. Task descriptions are short fixed synthetic text. Password hashing retained 12 bcrypt rounds.
- The fixture is seeded once per invocation. Each sample creates a new isolated browser context, so the signed-out visit starts with an empty browser HTTP cache. Reload retains that sample's browser HTTP cache. Server process, database, and API caches are shared across the ten samples and have already performed fixture setup; this is not a cold server or cold database test.
- The first sample records a Playwright trace and screenshots; other samples do not. This overhead is included in the reported distribution and must be held the same for comparison.

Readiness is measured independently of the application's current telemetry. An init script captures the submit or navigation-click event with `performance.now()`, checks content during animation frames, then allows another rendering opportunity before marking ready. It never waits for global network idle or treats `#app-shell` visibility as readiness.

| Journey | End condition |
|---|---|
| Cold sign-in | Visible, enabled SOEID/password inputs and submit button after session discovery; successful form submission is subsequently exercised |
| Login to Deliverables | Active visible Deliverables, all ten seeded solution rows, the seeded project title, and enabled visible search |
| Authenticated reload | Same populated Deliverables condition after full-page reload |
| First Tasks navigation | Active visible Tasks, all 100 seeded task rows, and enabled visible search; previously fetched or prefetched entity data may be reused |
| Warm navigation | Same destination conditions after both route modules and route data have previously loaded |

These conditions demonstrate the selected route's real list content and principal search control. They do not prove every secondary control, user-option list, editor, or background request has finished. A first Tasks visit is therefore reported separately from a guaranteed uncached data-fetch journey. The harness records resource requests so that this distinction is inspectable.

## Timings

Values are milliseconds. Percentiles use nearest rank. With ten samples, p95 is the maximum and is directional evidence, not a stable tail-latency estimate.

| Journey | n | p50 | p75 | p95 | Min |
|---|---:|---:|---:|---:|---:|
| Cold visit → usable sign-in | 10 | 1,146.6 | 1,152.8 | 1,154.5 | 1,131.2 |
| Submit → populated Deliverables | 10 | 348.9 | 350.6 | 355.3 | 333.9 |
| Authenticated reload → populated Deliverables | 10 | 1,178.9 | 1,205.0 | 1,229.1 | 1,145.2 |
| First Tasks navigation | 10 | 102.4 | 110.0 | 121.2 | 87.7 |
| Warm Tasks → Deliverables | 10 | 30.3 | 31.0 | 42.8 | 26.9 |
| Warm Deliverables → Tasks | 10 | 29.8 | 39.7 | 53.0 | 23.8 |

The valid-session reopening p75 exceeds the plan's provisional 1,000 ms desktop target in this local profile. The other selected journeys are within their proposed desktop targets here. This is insufficient for production sign-off because it excludes representative infrastructure, device variation, full UX coverage, large workspaces, and field traffic.

## Network and rendering evidence

These are observed browser values. `transferSize` includes Chromium's estimated response-header overhead; body bytes are kept separately. Resource totals include requests that started inside the measured journey and completed by its readiness marker, plus the document for full loads. Request-start counts cover the harness's observation stage through snapshot collection and can include work still pending at readiness; they are intentionally distinct from completed resource counts.

| Journey | Observed request starts (median) | Completed resources (sample 1) | Transfer bytes (median) | JS files completed (median) |
|---|---:|---:|---:|---:|
| Cold sign-in | 63 | 63 | 964,773 | 43 |
| Login | 12 | 7 | 96,360 | 0 |
| Reload | 76 | 71 | 192,242 | 43 |
| First Tasks | 2 | 2 | 5,944 | 1 |
| Warm Deliverables | 0 | 0 | 0 | 0 |
| Warm Tasks | 0 | 0 | 0 | 0 |

Signed-out startup transferred 945,873 response-body bytes: 574,714 JavaScript bytes across 43 files, 294,375 CSS bytes across 16 files, and the document/auth responses. Encoded and decoded totals were equal, consistent with the absence of compression on this local HTTP server. Source-file counts in the original plan are an import-closure estimate; these browser counts additionally include actual dynamic imports, and checked-out line endings can affect served byte counts.

Largest signed-out JavaScript bodies, with paths relative to `src/main/ui/js/`:

| Actual loaded module | Body bytes |
|---|---:|
| `app.js` | 134,649 |
| `routes/spaces/render.js` | 71,329 |
| `routes/spaces/interactions.js` | 55,280 |
| `shell/session.js` | 19,496 |
| `shell/data-store.js` | 19,334 |
| `routes/tasks-workbench/drawer.js` | 18,372 |
| `shell/dom.js` | 16,771 |
| `shell/telemetry.js` | 15,735 |
| `routes/master/filters.js` | 15,132 |
| `entities/solutions.js` | 14,108 |
| `shell/live-sync.js` | 12,339 |
| `routes/team-capacity/interactions.js` | 12,157 |

The full per-resource path, initiator, start, duration, body bytes, transfer bytes, and status inventory is retained in the raw JSON. Its CDP response inventory includes actual wire status, cache-control, content-encoding, protocol, and cache flags without persisting authentication headers.

The representative login request itself took 214.7 ms including the emulated network. The initial tasks response took 103.9 ms and carried 78,301 body bytes; this is approximately 83% of the 94,260 response-body bytes completed before login readiness. These single-request examples identify composition, not isolated bcrypt or database costs. Backend phase timing still needs separate instrumentation.

All ten logins issued one `/auth/login` and no follow-up `/users/me/preferences`, `/spaces`, or `/auth/active-space` reads. Reload used `/auth/me`, followed by preferences/spaces/active-space context reads. The repeated five-collection reads above are separate from these correctly bundled explicit-login context requests.

DOM element counts in sample 1 were 1,047 at sign-in, 1,574 at populated Deliverables, and 3,216 after rendering 100 tasks. Zero long tasks were observed inside each of the six measured intervals across all samples; this does not establish INP, LCP, or CLS.

## Reproduce and compare

Run commands from the repository root. The script requires the existing Playwright dependency and installed Chromium, plus a Python environment containing repository requirements. System Python on this workstation lacks `bcrypt`; the existing project virtual environment works.

```powershell
# Existing baseline checkout created for this run; do not recreate over it.
node scripts/benchmark_ui_performance.mjs --source-root .tmp/performance-baseline/source-3e77295 --output-dir .tmp/performance-baseline/before-repeat --runs 10 --tasks 100 --port 8774 --python 'F:/vault/projects/the-eco-system/sipm/.venv/Scripts/python.exe'

# Measure the integrated working tree with identical profile and fixture.
node scripts/benchmark_ui_performance.mjs --source-root . --output-dir .tmp/performance-baseline/after-integration --runs 10 --tasks 100 --port 8774 --python 'F:/vault/projects/the-eco-system/sipm/.venv/Scripts/python.exe'

# Inspect the recorded before trace.
npx playwright show-trace .tmp/performance-baseline/baseline-10/first-sample-trace.zip
```

On another checkout, first create an owned detached baseline worktree with `git worktree add --detach .tmp/performance-baseline/source-3e77295 3e77295`; adjust the Python executable path. Choose a fresh output directory each time: the harness deliberately refuses to overwrite reports or reuse a listening server. It starts and stops its own disposable fixture, prints each sample, and writes results even on failure. The source revision, dirty paths, key source-file hashes, hardware, profile, browser version, and fixture are recorded with each result.

For a fair comparison, hold fixture sizes, browser version, CPU/network settings, motion preference, and trace policy constant. Run the baseline and integrated source sequentially while other suites are paused. Prefer alternating before/after batches on a dedicated runner before enforcing the proposed no-regression threshold of both 10% and 50 ms. Compare content readiness and request/byte counts together; a faster loading placeholder does not satisfy this harness.

The harness supports `--latency-ms`, `--download-mbps`, `--cpu-rate`, and `--tasks`. Larger values are available for follow-up experiments but were not exercised in this baseline. Mobile widths, direct links, developer-mode My Work, expired tokens, workspace switching, search/save latency, edit preservation, concurrent sessions, and deployed Oracle/Redis measurements remain follow-up work.

## Evidence and validation status

- [Reusable harness](../scripts/benchmark_ui_performance.mjs).
- [Raw ten-sample results](../.tmp/performance-baseline/baseline-10/results.json), [trace](../.tmp/performance-baseline/baseline-10/first-sample-trace.zip), and [local server log](../.tmp/performance-baseline/baseline-10/server.log).
- [Sign-in screenshot](../.tmp/performance-baseline/baseline-10/cold-sign-in.png), [Deliverables screenshot](../.tmp/performance-baseline/baseline-10/deliverables.png), and [Tasks screenshot](../.tmp/performance-baseline/baseline-10/tasks.png). All three were visually inspected and show populated, styled screens. These are baseline references for checking that optimization preserves the visual UX; no before/after visual comparison is claimed yet.
- Raw files and the detached checkout live in ignored `.tmp/performance-baseline/` and are local artifacts, not committed report attachments. The durable tables here preserve the measured baseline; archive raw artifacts with release evidence if needed. Traces contain only the disposable synthetic fixture session.
- The syntax check `node --check scripts/benchmark_ui_performance.mjs` passed. The venv pilot passed all six journeys. The final ten-sample run passed 10/10 journeys with no JavaScript exceptions or unexpected HTTP errors. Signed-out `/auth/me` and `/auth/refresh` each correctly returned 401. Nine still-running task reads were canceled on subsequent reload and are explicitly recorded as `net::ERR_ABORTED` in the raw data.
- The first pilot using system Python failed during startup because `bcrypt` was missing; it produced no journey measurements. No dependencies, application source, existing tests, or configuration were edited by the baseline subtask.
- Required full repository suites and integration validation belong to the implementation owners. This harness is a reproducible local measurement, not a substitute for those checks or the plan's broader performance sign-off.

## Raw journey samples

All values are milliseconds. Sample 1 includes tracing and screenshots between journeys.

| Run | Cold sign-in | Login | Reload | First Tasks | Warm Deliverables | Warm Tasks |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1,146.6 | 353.7 | 1,229.1 | 110.0 | 26.9 | 53.0 |
| 2 | 1,149.6 | 345.7 | 1,145.2 | 102.3 | 30.5 | 29.8 |
| 3 | 1,153.5 | 343.0 | 1,199.8 | 99.5 | 30.3 | 38.4 |
| 4 | 1,131.2 | 349.2 | 1,145.4 | 87.7 | 36.4 | 23.8 |
| 5 | 1,145.7 | 349.2 | 1,209.8 | 121.2 | 28.0 | 26.9 |
| 6 | 1,139.6 | 348.9 | 1,159.6 | 116.9 | 29.9 | 29.3 |
| 7 | 1,154.5 | 350.6 | 1,178.9 | 102.9 | 30.3 | 40.9 |
| 8 | 1,147.2 | 355.3 | 1,168.4 | 102.4 | 42.8 | 25.6 |
| 9 | 1,138.7 | 333.9 | 1,195.1 | 92.2 | 31.0 | 30.0 |
| 10 | 1,152.8 | 341.6 | 1,205.0 | 105.1 | 30.3 | 39.7 |
