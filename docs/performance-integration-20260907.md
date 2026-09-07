# Login and responsiveness implementation

Date: 2026-09-07
Baseline: `3e77295342d4314539a151df294f62c6efabcc76`
Integration branch: `codex/performance-integration-20260907`
Status: implemented and validated locally; production sign-off remains open

This implements the first measured improvements from the [performance plan](login-performance-and-responsiveness-plan.md). The product requirement is to preserve the existing appearance and workflows while making login and navigation more responsive. Three isolated task chats handled login, navigation, and startup; three subagents supplied benchmarks, task-filter optimization, and independent regression reviews. Changes are local; no deployment or production measurements are claimed.

## Implemented changes

| Area | Change | Evidence |
|---|---|---|
| Session reopening | Add `/auth/bootstrap`, returning authorized user, preferences, spaces, and active space together. Reuse membership rows within the request. | Normal-user valid reopening: four context requests in two stages become one request in one stage; fixture SQL statements fall from 11 to 4, connection checkouts from 4 to 1. |
| Login | Reuse the authorized membership snapshot when building the existing login response. | Fixture SQL statements fall from 8 to 7; password verification and existing response contracts remain intact. |
| Login screen code | Begin loading the requested route and governance modules concurrently with the explicit login request. | Both are known dependencies of authenticated startup. A held-login browser test verifies that code arrives before credentials complete, with no private data reads; module failure or a pending preload cannot block authentication. |
| Initial live sync | Subscribe immediately and run the first forced catch-up after the initial foreground load settles. | The first snapshot finishes without cancellation; mandatory fresh catch-up follows success or failure. Live messages and heartbeats remain immediate, and obsolete socket/session waits are discarded. |
| Navigation | Start the latest route's reads immediately; share in-flight collection reads within the same identity, space, generation, and invalidation version. | A held unrelated route no longer blocks the destination. Overlapping prefetch and foreground reads fall from two to one. |
| Background refresh | Keep the exact union of invalidated collections; cap speculative prefetch at two and stop canceled consumers from starting retries. | Queued projects/tasks updates fetch two collections instead of all seven. Mandatory freshness invalidation remains enforced. |
| Startup | Defer governance and Deliverables modules until needed, retaining eager handlers for visible static controls. | Isolated source-normalized browser capture: signed-out modules fall from 43 to 37, raw JavaScript from 562,216 to 410,686 bytes (27.0%), listener registrations from 218 to 195. |
| Task filtering | Build fresh project and solution lookup maps once per filtering call, preserving the first duplicate ID match. | The 10,000-task synthetic benchmark reduces filtering CPU time by about 33% and search CPU time by about 40%. |
| Filter input preservation | Record Task search/priority draft state immediately while keeping rendering and persistence debounced. | A background render or arriving route module cannot replace newly typed input with older filter state. Debounced callbacks use the value captured from the input event. |
| Route-local reads | Guard My Work and Repositories results by request, user, space, authentication, and route-state identity. | Deferred-response tests reject stale successes, errors, and completion work after session/context replacement. |
| Telemetry | Register supported buffered observer types separately; preserve absent timings as null; defer observer setup until analytics is enabled. | Focused tests cover partial browser support, missing values, and disabled analytics. Application readiness measurements use the independent browser harness. |

See the [login report](performance-login-implementation.md), [navigation report](performance-navigation-implementation.md), and [startup report](performance-startup-implementation.md) for contracts, controlled reproductions, and package-level validation. Startup-only byte counts exclude the other packages and normalize line endings; the combined browser comparison below measures actual served bytes.

## Task computation measurements

The [task-filter benchmark](../scripts/benchmark_task_filtering.mjs) compares the baseline function with the current function on identical synthetic inputs, checks equivalent output, warms both implementations, and alternates 30 sample pairs. Values below are p50 CPU time in milliseconds, not browser interaction or production latency.

| Tasks | Filter before | Filter after | Search before | Search after |
|---:|---:|---:|---:|---:|
| 100 | 0.284 | 0.259 | 0.451 | 0.442 |
| 1,000 | 5.771 | 4.696 | 4.600 | 3.905 |
| 10,000 | 132.700 | 88.695 | 88.298 | 53.289 |

The largest fixture contains 500 projects and 2,000 solutions. Parent-ID reads fall from 12,510,000 to 5,000. The sort, search, date boundaries, and duplicate-ID behavior are preserved; the optimization does not cache across calls or change rendered rows. Environment: Windows 10.0.26200, Node 20.19.2, AMD Ryzen 7 5800X.

## Regression review

Independent review found and corrected two shared-refresh races: an old refresh could restore a logged-out session, and overlapping bootstrap callers could incorrectly invalidate each other's shared refresh. Refresh lifetime now follows the session and identity; each caller separately guards its own continuation. An obsolete completion cannot clear a replacement refresh promise.

Navigation review found and corrected a partial-data handoff that left cached route controls stale, plus a canceled prefetch that could restart obsolete work ahead of a foreground load. Reproduction tests passed after both fixes. Unchanged cached navigation avoids unnecessary control repopulation.

Startup review requires handlers to remain attached for static controls exposed while route imports are pending. Delayed-import browser checks verify that input entered before the renderer arrives is retained. Final startup and combined browser results are recorded after integration below.

The first combined performance capture caught a submit-to-content regression: p50 rose from 348.2 to 470.5 ms despite a slightly faster login HTTP request. Traces identified a post-authentication module waterfall, competing governance downloads, and cancellation/restart of the first snapshot at WebSocket connection. The final correction warms the requested route and required governance code while login is pending, then lets the first snapshot settle before the mandatory fresh catch-up. Actual authorization, preferences, developer/lobby redirects, rendering, and private data loading still follow the successful response. Unit tests cover duplicate submit, unfinished/failed preload, catch-up after success/failure, immediate live messages, and replaced contexts. The rejected captures remain available for audit, as listed below.

The final full browser sweep also reproduced a Task query race: background normalization could overwrite the input before its 180 ms debounce recorded the value. Input now updates draft state immediately; expensive rendering and persistence keep their existing debounce. The delayed-module test releases rendering before waiting for persistence, and the full browser rerun passes query retention across direct entry, refresh, back/forward, and first-module loading.

## Remaining boundaries

- Initial WebSocket connection still forces a fresh collection catch-up. A request begun before subscription cannot establish that it includes updates between its snapshot and subscription. Removing these extra reads requires a coordinated subscription/snapshot contract.
- Global editor restoration on background refresh is an existing limitation. This work does not claim complete protection for dirty forms during every unrelated live update; selective editor synchronization remains a separate change.
- Startup asset caching, deployment compression, whole-collection API payloads, and large-table DOM rendering remain unchanged. Address these using deployed measurements and dedicated traces.
- The existing aggregate route telemetry still lacks explicit asynchronous route readiness and INP. The observer fixes do not close PERF-08; browser timing uses content and control readiness rather than the application's aggregate metric.
- Local SQLite measurements do not establish Oracle, Redis, corporate-network, concurrent-user, constrained-device, or production performance. The broad plan's targets remain provisional until those environments are measured.

## Integration validation

The integrated login/navigation/backend changes passed all 613 backend tests with 82.61% coverage using `.venv/Scripts/python.exe -m pytest -m "not integration" --cov --cov-report=term-missing --cov-report=xml` (194.03 seconds). No backend production source changed afterward. The Redis integration invocation collected one test and skipped it because `SIPM_REDIS_URL` is unavailable.

Final UI unit coverage passes all 317 tests in 34 files: statements 48.50%, branches 38.68%, functions 54.04%, lines 51.20%, meeting the configured thresholds. UI lint, route-module mapping, and pinned Ruff checks on changed Python files pass. The startup asset budget now uses LF-normalized source bytes, matching its benchmark and avoiding an OS-dependent assertion failure; the threshold remains unchanged. Older Python structural assertions now follow governance's route exports and the split immediate/debounced Task input callbacks. The synthetic browser admin fixture now overrides the bundled bootstrap context.

The final browser suite passes all 31 cases (51.5 seconds) using `SIPM_UI_SMOKE_PORT=8775` and `npm run test:ui:smoke -- --workers=1`, with the existing `.venv/Scripts` prepended to PATH. The post-integration `.venv/Scripts/python.exe -m pytest -m "not integration" -k "frontend or ui or route or topbar"` rerun passes all 212 selected cases (12.31 seconds). These overlap the full backend suite and are not additional unique backend tests. The Windows smoke server logged a connection-reset callback while pages closed; all browser assertions completed successfully.

The changes add no dependencies, schema migrations, visual design, or deployment settings. Roll back by reverting the isolated implementation commits in reverse integration order; the additive bootstrap endpoint must remain deployed while any frontend using it is served.

## Combined browser comparison

The final integrated candidate `482719a20120f1cac6e485041160769ab8eb20bf` passes the provisional regression gate against the unchanged baseline `3e77295342d4314539a151df294f62c6efabcc76`. All 10 samples completed all six journeys per build. No measured journey's p50, p75, or p95 became both more than 10% and more than 50 ms slower. Cold sign-in and authenticated reopening improved; submit-to-content login time was effectively preserved. This is a directional local comparison, not a production performance claim.

### Journey timings

All values are milliseconds. Quantiles use nearest rank; with 10 samples, p95 is the observed maximum.

| Journey | Before p50 | Before p75 | Before p95 | After p50 | After p75 | After p95 | Median change |
|---|---:|---:|---:|---:|---:|---:|---:|
| Cold sign-in form | 1117.6 | 1133.7 | 1170.9 | 1056.2 | 1065.9 | 1085.9 | -61.4 ms (-5.5%) |
| Submit to Deliverables content | 354.7 | 363.0 | 405.1 | 362.1 | 371.5 | 405.3 | +7.4 ms (+2.1%) |
| Authenticated reload to Deliverables | 1176.6 | 1209.6 | 1226.0 | 1101.0 | 1127.5 | 1153.1 | -75.6 ms (-6.4%) |
| First Tasks navigation | 102.4 | 119.7 | 125.6 | 109.0 | 127.1 | 140.1 | +6.6 ms (+6.4%) |
| Warm Deliverables navigation | 29.8 | 30.4 | 31.0 | 30.2 | 30.5 | 31.1 | +0.4 ms (+1.3%) |
| Warm Tasks navigation | 30.3 | 39.3 | 50.8 | 29.6 | 30.7 | 42.5 | -0.7 ms (-2.3%) |

The small warm-navigation differences are sensitive to frame scheduling. First Tasks p75 rose 7.4 ms, below the absolute regression threshold. Authenticated reopening still exceeds the plan's provisional 1000 ms p75 target at 1127.5 ms; passing the relative gate does not close that budget. No long tasks were recorded inside these measured intervals. These observations do not establish INP, LCP, or CLS.

### Requests and served assets

Counts and bytes below are per-stage medians. Request starts include work observed before the stage snapshot, including pending background requests. Transfer bytes count document/resources begun within the measured journey and completed by its content-readiness boundary. These are different observation sets; stage medians must not be summed into a total session payload.

| Journey | Request starts before | Request starts after | Transfer bytes before | Transfer bytes after | Completed JS files before / after |
|---|---:|---:|---:|---:|---:|
| Cold sign-in form | 63 | 57 | 964,773 | 810,445 | 43 / 37 |
| Submit to Deliverables content | 12 | 19 | 96,360 | 252,244 | 0 / 7 |
| Authenticated reload to Deliverables | 76 | 71 | 192,242 | 190,329 | 43 / 41 |
| First Tasks navigation | 2 | 5 | 6,653 | 7,252 | 1 / 3 |
| Warm Deliverables navigation | 0 | 0 | 0 | 0 | 0 / 0 |
| Warm Tasks navigation | 0 | 0 | 0 | 0 | 0 / 0 |

Cold sign-in transfers fell 16.0%; its JavaScript encoded bodies fell from 574,714 to 422,383 bytes (26.5%). The actual import list omits six formerly eager files: `routes/master.js`, `routes/master/table.js`, `routes/master/quickstart.js`, `routes/master/interactions.js`, `routes/spaces/interactions.js`, and `routes/spaces/render.js`. Login now loads these plus `routes/spaces.js` concurrently with credential verification. This moves code between stages and explains the larger login-stage payload. Baseline checkout files include CRLF while integrated files include committed LF; raw served-byte differences therefore include platform checkout effects. The separate [startup report](performance-startup-implementation.md) normalizes source line endings and isolates that package's 27.0% reduction.

Each authenticated reload replaced four context requests (`/auth/me`, `/users/me/preferences`, `/spaces`, `/auth/active-space`) with one `/auth/bootstrap`; the separate session-policy request remains. Each explicit login made one login request without redundant bootstrap/preferences/space-context follow-ups. The larger first-Tasks request count includes governance work finishing after reload: `spaces/interactions.js`, `spaces/render.js`, and `/agent/change-requests`, alongside the Tasks renderer and `/users`. It is not five Tasks-only dependencies.

The fixture still serves HTTP/1.1 without content encoding and uses `no-cache, max-age=0, must-revalidate`; reloads of `app.js` and `styles.css` produce actual wire-status 304 responses. Deployment compression and cache policy did not change.

### Readiness and startup catch-up

The [browser harness](../scripts/benchmark_ui_performance.mjs) uses independent DOM assertions and another animation frame: visible enabled sign-in inputs and submit control; an active Deliverables route containing exactly 10 solution rows, the seeded project label, and its enabled filter; or an active Tasks route containing exactly 100 task rows and its enabled search control. Timing begins at navigation start, the captured submit event, or the captured navigation click. Each sample also completes the real login interaction. The sign-in timestamp does not separately instrument listener attachment. No measurement ends merely because the application shell is visible, and none uses network idle with the live WebSocket.

Route readiness means the first usable seeded content, not completion of every secondary control or live refresh. Login and reload still each issue two reads of phases/programs/projects/solutions/tasks: the initial snapshot and the mandatory connection catch-up. The final change opens the subscription, processes messages, and starts its heartbeat immediately, but allows the initial foreground load to settle before forcing that catch-up. It preserves the baseline ability to show the first snapshot before the background refresh completes; it does not remove the freshness requirement or claim duplicate reads are eliminated.

The final capture recorded zero page exceptions, unexpected HTTP errors, or request failures. Signed-out bootstrap/refresh 401 responses are expected. Baseline recorded nine task and three solution request aborts when a later page replaced the old one. These observations cover the measured sequence, not all background work after it.

Three intermediate candidates were rejected by the same login regression rule, using the earlier `before-repeat` reference, and remain archived locally:

| Candidate | Login p50 | Login p75 | Login p95 | Trace finding |
|---|---:|---:|---:|---|
| `7b37339`, `after-integration` | 470.5 | 487.9 | 541.0 | Deliverables imports moved after authentication, delaying content despite a slightly faster login HTTP response. |
| `aae8274`, `after-login-preload` | 531.5 | 533.8 | 536.5 | Requested-route imports overlapped login, but governance imports and forced initial collection cancellation/restart delayed content. |
| `34c3bb4`, `after-login-warmup` | 482.1 | 490.6 | 498.7 | Requested-route and live-sync code warmed successfully; WebSocket startup still canceled the initial entity reads and waited for replacements. |

The final coordination change removed that startup cancellation from the measured sequence. Independent behavioral tests, reported separately above, cover immediate subscription and required catch-up after the held first load succeeds or fails.

### Repeat-run variability

An earlier capture of the same final source, [final-482719a](../.tmp/performance-baseline/final-482719a/results.json), recorded login p50/p95 of 481.6/609.5 ms and seven first-Tasks long tasks of 53-78 ms. Request counts, payloads, and cancellation behavior were unchanged; the extra time appeared in login HTTP duration and browser rendering/scheduling. Host contention is suggested, but was not proven with CPU/server profiling. The adjacent baseline/final pair above returned to the earlier timing range without a runtime change and recorded no long tasks. This variability is retained as evidence: the relative gate passed in the final pair, but stable tail latency requires a dedicated runner, more alternating samples, and production-representative infrastructure.

### Visual check and reproducibility

All three full-page ready-state screenshot pairs have identical RGB pixels after decoding; each pair also has identical dimensions. They were visually inspected. This verifies these desktop snapshots, not every responsive layout, intermediate state, focus interaction, or draft-editing flow.

| Screen | Dimensions | Before | After | RGB difference |
|---|---|---|---|---|
| Sign-in | 1440 x 1000 | [Baseline](../.tmp/performance-baseline/paired-before-final/cold-sign-in.png) | [Integrated](../.tmp/performance-baseline/paired-after-final/cold-sign-in.png) | None |
| Deliverables | 1440 x 1007 | [Baseline](../.tmp/performance-baseline/paired-before-final/deliverables.png) | [Integrated](../.tmp/performance-baseline/paired-after-final/deliverables.png) | None |
| Tasks | 1440 x 1000 | [Baseline](../.tmp/performance-baseline/paired-before-final/tasks.png) | [Integrated](../.tmp/performance-baseline/paired-after-final/tasks.png) | None |

Both captures used Chromium 145.0.7632.6, Node 20.19.2, Windows 10.0.26200, an AMD Ryzen 7 5800X with 16 logical CPUs and 63.9 GiB RAM, a 1440 x 1000 viewport, 50 ms network latency, 20 Mbps in both directions, normal CPU speed, and reduced motion. Each of 10 samples used a new browser context; authenticated reload retained that context's cache. The safe fixture contained one synthetic user and personal space, one program, 10 projects, 10 solutions, and 100 short tasks, using disposable SQLite, memory coordination, and normal bcrypt cost 12. Seeding warmed the local server/data caches. The first sample in each capture included a trace and screenshots.

Baseline ran at 21:26:30-21:27:08 UTC on 2026-09-07; final capture ran at 21:28:05-21:28:42 UTC. Other heavy suites were paused, but this shared workstation was not a dedicated runner. The final builds were measured in adjacent batches with no code changes between them; individual samples were not alternated. Ten samples do not establish a stable tail, constrained-device performance, production concurrency, Oracle/Redis behavior, or deployed-network latency. No production service or real user data was accessed.

Raw [baseline results](../.tmp/performance-baseline/paired-before-final/results.json) and [final results](../.tmp/performance-baseline/paired-after-final/results.json) retain every sample, request path, resource timing, source hash, and response/cache observation. Their directories also contain `server.log` and `first-sample-trace.zip`. The three rejected capture directories retain equivalent raw evidence. These `.tmp` artifacts are local and ignored by Git; the tables above preserve the comparison in this committed report.

To repeat from the repository root, use a new output directory; the harness refuses an existing output directory or a listener on port 8774 and stops its owned server afterward:

```powershell
node scripts/benchmark_ui_performance.mjs --source-root . --output-dir .tmp/performance-baseline/after-next-candidate --runs 10 --tasks 100 --port 8774 --python 'F:/vault/projects/the-eco-system/sipm/.venv/Scripts/python.exe'
```

For the same baseline, set `--source-root .tmp/performance-baseline/source-3e77295` and choose another new output directory. The [original baseline report](performance-baseline-20260907.md) documents harness setup and the initial capture; `paired-before-final` is the reference for the final tables above; earlier candidate trials used `before-repeat`.
