# Login, Performance, and Responsiveness Plan

Date: 2026-09-06  
Review baseline: commit `3e77295`  
Mode: performance optimization planning  
Status: proposed; no application changes made

## Intended outcome

Make SIPM feel immediate when signing in, reopening a session, navigating, searching, editing, and switching workspaces. Every action should receive prompt feedback, and background work should preserve the user's current task.

This document defines the implementation and measurement plan. It does not certify current performance or claim measured speed improvements. Findings come from source inspection, a local asset inventory, existing test inspection, and primary documentation. Browser timings, production traffic, Oracle execution plans, and deployed delivery settings have not been measured in this review.

Recommended order: establish trustworthy measurements, improve session startup and foreground request scheduling, reduce startup assets, then optimize large-workspace rendering and API payloads where traces justify it. Keep changes in small, independently reviewable PRs.

## Performance targets

The following are proposed product budgets, to be calibrated against a recorded baseline before implementation. They are not current results or contractual service levels.

| Journey or signal | Proposed acceptance target | Measurement boundary |
|---|---|---|
| Interaction feedback | p95 at or below 100 ms | Click/key event to first visible acknowledgement; applies to submit, navigation, menus, drawers, and save |
| Fresh visit to usable sign-in form | p75 at or below 1.5 s; p95 at or below 2.5 s | Navigation start to visible, enabled form with handlers attached |
| Sign-in to usable landing route | p75 at or below 1.5 s; p95 at or below 2.5 s | Submit to authorized route content painted and primary controls usable; includes password verification |
| Valid-session reopening | p75 at or below 1 s; p95 at or below 1.5 s | Navigation start to usable route with a warm browser cache; report expired-access-token recovery separately |
| Warm navigation | p95 at or below 200 ms | Navigation click to usable destination when module and required data are already present |
| Navigation requiring data | p75 at or below 800 ms; p95 at or below 1.5 s | Navigation click to usable destination; pending feedback still meets 100 ms target |
| Search/filter/sort | p95 at or below 200 ms | Last input to painted result, including any debounce; typing remains responsive throughout |
| Workspace switch | p95 at or below 1.5 s | Selection to usable authorized destination; old workspace content is cleared immediately |
| Save | Feedback within 100 ms; confirmed outcome p95 at or below 1 s | Input to pending state, then server acknowledgement to rendered result; report these separately |
| Visual stability | No unexpected focus, scroll, or draft loss | During navigation, loading, background refresh, and save |

Also track LCP at or below 2.5 s, INP at or below 200 ms, and CLS at or below 0.1 at the 75th percentile, separately for desktop and mobile. These are the published Core Web Vitals thresholds. A quick startup placeholder can satisfy a paint metric while the workspace is still unusable, so application readiness remains a separate measurement. [Web Vitals guidance](https://web.dev/articles/vitals)

Use a fixed reference profile: supported desktop browser, recorded hardware and browser version, 1440 px viewport, normal CPU, and a controlled 50 ms latency/20 Mbps download connection. Include a constrained profile at 390 px, 4× CPU slowdown, and 150 ms latency/1.6 Mbps download. Initially report constrained-profile results separately; establish its journey budgets from the baseline without relaxing immediate feedback or state-preservation requirements. Confirm results on representative real devices and the deployed corporate network.

## Current implementation and evidence

### Existing strengths to preserve

- Successful local login already returns preferences, spaces, and active-space context in one response. `finishAuthentication()` consumes that payload, and a browser test explicitly checks that login makes no redundant follow-up context requests. Sources: [auth route](../src/main/backend/app/routes/auth.py), [session controller](../src/main/ui/js/shell/session.js), [auth browser tests](../src/main/ui/test/e2e/auth-and-deliverables.spec.js).
- Route entry modules use dynamic imports with module caching and in-flight deduplication. Data requirements are declared by route, and missing entity collections load concurrently. Sources: [router](../src/main/ui/js/shell/router.js), [route registry](../src/main/ui/js/shell/route-registry.js), [data store](../src/main/ui/js/shell/data-store.js).
- Session refresh already shares an in-flight promise. Data-context changes abort requests and reject stale results. Preserve these controls while changing request scheduling.
- The UI already has a startup screen, disabled/busy auth buttons, bounded API requests, responsive navigation, and reduced-motion styling. Improve these existing patterns rather than replacing the visual system.
- Server request logs include duration and request IDs; the UI has route/performance telemetry; read APIs have scoped caches. Build on these facilities.

### Asset inventory

Static filesystem counts at the reviewed commit:

| Surface | Count or size |
|---|---:|
| `app.js` | 3,821 lines; 134,649 bytes |
| Recursively reachable static JavaScript imports, including `app.js` | 41 modules; 559,958 bytes |
| Stylesheet import closure, including `styles.css` | 16 files; 294,178 bytes |
| `index.html` | 77,942 bytes |

Method: recursively follow relative static imports from `js/app.js` and CSS `@import` declarations from `styles.css`, deduplicate file paths, and sum file bytes. These are uncompressed source sizes, not transferred bytes, measured parse times, or a complete browser request count. Dynamic route imports are additional. Repeat the inventory with resource timing and a HAR before assigning transfer budgets.

### Prioritized findings

Severity describes potential user impact; it does not imply measured production latency. All items remain proposed.

| ID | Severity / disposition | Confirmed behavior and implication | Planned response |
|---|---|---|---|
| PERF-01 | High / should-fix | [App initialization](../src/main/ui/js/app.js) imports route interaction modules and binds many route/form controllers before starting auth bootstrap. [Styles](../src/main/ui/styles.css) load all route styles through imports. Cold login carries substantial unrelated startup work. | Isolate the critical auth/shell path and defer route-specific initialization and styles; measure cold-load impact. |
| PERF-02 | Medium / should-fix | `bootstrapAuth()` awaits `/auth/me`, then preferences and space context; context itself requests `/spaces` and `/auth/active-space` concurrently. Expired access adds `/auth/refresh`. Explicit login already avoids this context waterfall. | Profile reopening separately and consolidate authenticated bootstrap context if the extra stage is material. |
| PERF-03 | High / should-fix | [Data-store](../src/main/ui/js/shell/data-store.js) foreground loads use one `loadOperation`; later route loads queue behind it. Prefetch uses separate requests after 450 ms and does not share entity promises with foreground loading. A route change after prefetch starts can overlap requests for the same entity. | Give the latest route priority and share context-scoped entity requests across foreground, prefetch, and refresh. |
| PERF-04 | Medium / should-fix | `flushPendingRefreshes()` expands multiple pending entity types into `all`, which fetches all seven entity collections. `syncUiAfterDataLoad()` and completed prefetch call global `populateSelects()`, including controls on inactive routes. | Preserve the union of invalidations, defer inactive-route work, and update affected controls only. |
| PERF-05 | High / should-fix at scale | [Task filtering](../src/main/ui/js/routes/tasks-workbench/filters.js) searches projects and solutions for each task: O(T × (P + S)) lookup work. [Task rendering](../src/main/ui/js/routes/tasks-workbench.js) builds and replaces all visible rows. | Build lookup maps once per relevant data revision; profile filtering and DOM updates; bound row rendering when needed. |
| PERF-06 | Medium / advisory pending profiling | [Task list API](../src/main/backend/app/routes/tasks/read.py) materializes all matching rows, and the data store calls `/tasks` without filters. Several primary routes require whole collections. Cache hits still incur payload processing. | Record payload sizes, query counts, and serialization costs; use bounded list/summary requests where data size breaches budgets. |
| PERF-07 | Medium / should-fix | [Frontend serving](../src/main/backend/main.py) applies `no-cache, max-age=0, must-revalidate` to both HTML and assets. Reopening requires asset revalidation. No compression middleware was found here; ingress behavior is unknown. | Verify deployed headers first; introduce content-versioned asset caching and verify compression with the platform owner. |
| PERF-08 | High / must-fix before performance sign-off | [Telemetry](../src/main/ui/js/shell/telemetry.js) completes route duration by adding data-load and synchronous render timings, rather than measuring click-to-ready elapsed time. Data-load timing can already include rendering; route-local async work can continue afterward. INP is absent from its samples. | Establish explicit journey start/ready/failure markers and correct metric collection before using telemetry to declare success. |

`no-cache` permits storage but requires revalidation; it does not necessarily force a full body download. Preserve that distinction when measuring PERF-07. [Cache-Control semantics](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control)

## Implementation work packages

### 1. Establish the baseline and readiness contract

Owner: frontend and backend engineers, supported by QA. Dependency: none.

1. Capture cold sign-in, local login, valid-session reopening, expired-access recovery, direct links, and workspace switching. Cover the regular Deliverables landing route, developer-mode My Work, and the lobby/Spaces route.
2. Add monotonic timing markers for auth start/end, context ready, route selected, module ready, data ready, and content ready. Give each navigation an operation ID so superseded routes cannot complete the current route's measurement. Treat errors and abandoned routes as separate outcomes.
3. Define content ready per route: authorized content or an explicit empty state is painted and the main control is usable. My Work and other routes with their own async loading must report their actual completion. Do not use global network-idle as readiness; WebSockets, heartbeats, telemetry, and prefetch continue in the background.
4. Extend telemetry with correct Web Vitals lifecycle handling and INP. Evaluate the official `web-vitals` implementation before extending hand-written collectors. The current observer combines `entryTypes` and `buffered`; check supported entry types and use supported registration forms. Preserve the existing analytics enablement setting. [PerformanceObserver options](https://developer.mozilla.org/en-US/docs/Web/API/PerformanceObserver/observe)
5. Instrument backend login phases in a test/UAT harness: pool checkout, user lookup, bcrypt verification, lockout/update handling, session creation, space resolution, preferences, serialization, and commit. Correlate with existing request IDs and log aggregate durations without passwords, cookies, tokens, or form contents.
6. Record compressed transfer bytes, request counts, cache status, longest tasks, DOM size, query count, cache hit/miss behavior, and route-ready latency.

Acceptance: a reproducible before-change report with fixture sizes, environment, revision, raw samples, traces, and p50/p75/p95. Readiness must distinguish a rendered loading placeholder from usable content.

### 2. Streamline login and session restoration

Owner: frontend/backend. Dependency: package 1.

1. Preserve the current single-response local-login bootstrap and its zero-redundant-context-request test.
2. Move auth binding and session discovery ahead of unrelated route initialization. Use a deliberate session-checking and workspace-opening state so users never see an apparently ready but uninitialized route. Keep pending submit feedback immediate and avoid duplicate submissions.
3. If reopening traces show a material context delay, add an authenticated bootstrap response containing the same context already returned by login. Preserve existing public response contracts through an additive endpoint or explicitly compatible change. Continue using shared refresh for expired access, with one bounded retry.
4. Profile shared space-resolution work. `_issue_session()` checks the default space, while active-space resolution and listing perform additional space queries. Reuse data within the request where contracts permit; only tune queries or pool settings when evidence identifies the cost.
5. Retain bcrypt strength, dummy verification for unknown users, lockout handling, password-reset requirements, session revocation, idle expiration, and cookie protections. Do not trade away authentication checks to meet a timing budget.
6. Maintain deep links and the developer-mode landing preference. Make slow/network-failure recovery actionable without presenting a connectivity problem as a wrong password.

Acceptance: all auth journeys meet their agreed budgets; local login still issues one login request without follow-up bootstrap reads; recovery does not loop; no extra session is created merely by reopening; security and space-isolation tests pass.

### 3. Prioritize navigation and contain background work

Owner: frontend. Dependency: package 1; coordinate shared session changes with package 2.

1. Share in-flight entity reads using keys that include session/data generation, active space, entity, and query parameters. Do not share reads across users or workspaces.
2. Let a newly selected route start its missing reads without waiting for unrelated old-route work. Reuse shared work when useful and cancel obsolete requests only when no active consumer needs them.
3. Make prefetch lower priority than the current route. Cancel scheduled prefetch on navigation, deduplicate already-running reads, and avoid unnecessary prefetch on hidden tabs or constrained connections where detectable.
4. Coalesce refreshes into their exact affected-entity union. Invalidate inactive data immediately, then reload it on demand; preserve required cross-entity dependencies and the existing fallback for unknown/full invalidations.
5. Update the active route and open editors only when their relevant data changes. Populate hidden form options when those forms open. Preserve selection, focus, scroll, and dirty fields during live updates.
6. Exercise reconnect and tab-resume bursts with [live sync](../src/main/ui/js/shell/live-sync.js); confirm background refresh never extends the genuine-user-activity idle policy.

Acceptance: one in-flight read per identical context/entity/query; the latest route is not blocked by unrelated requests; two known invalidations do not fetch seven collections; old-space results never repaint the new space; background events do not reset an active editor.

### 4. Reduce startup assets and improve repeat visits

Owner: frontend; platform support for delivery. Dependency: package 1.

1. Move route-only interaction imports and bindings behind route entry points. Keep shared navigation, session, theme, and modal essentials small. Preserve route-module test mappings and bind each controller once.
2. Keep auth, shell, shared tokens, and responsive essentials available at startup. Load route styles before revealing that route so deferred CSS does not create flashes or layout shifts. Validate shared styles used by public pages and modals.
3. Start with the existing ES-module architecture. Introduce a production bundling step only if the measured module waterfall or packaging needs justify it; a framework migration is outside this plan.
4. Add content-versioned asset URLs before assigning long-lived immutable caching. Keep HTML revalidated and retain old referenced assets through deployments so open tabs can still lazy-load their release's modules.
5. Verify actual transfer encoding and HTTP caching at the deployed ingress; apply compression once at the appropriate layer. Test cache-warm reloads and a release transition.

Acceptance: signed-out startup no longer loads route-only controllers/styles; a provisional goal is at least 40% less critical-path JavaScript transfer, subject to the package-1 inventory. Repeat visits reuse unchanged versioned assets without per-asset validation; direct links, password reset, public dashboards, theme selection, and lazy-route failures remain usable.

Smaller initial JavaScript and deferred execution can reduce main-thread contention; measure the resulting route-ready and interaction timings rather than accepting a smaller file count as success. [JavaScript code splitting](https://web.dev/learn/performance/code-split-javascript)

### 5. Keep large workspaces responsive

Owner: frontend/backend. Dependency: package 1; apply package 3 before comparing refresh workloads.

1. Replace per-task project/solution scans with maps built per relevant data revision. Reuse derived search text where profitable, with explicit invalidation after edits, imports, refresh, logout, and workspace changes. Keep time-sensitive urgency calculations fresh.
2. Profile Deliverables, Tasks, My Work, dashboards, Kanban, Calendar, and Roadmap for filtering, repeated derivation, layout work, and full-list DOM replacement. Optimize the largest measured contributor first.
3. If row creation dominates, adopt pagination or windowed rendering for the affected table. Preserve keyboard movement, selection across pages, bulk actions, find behavior, and screen-reader semantics. Do not virtualize every route preemptively.
4. Keep typing updates immediate. Any search debounce counts toward the result budget. Split genuinely long processing tasks and provide cancellation for superseded work; consider a worker only if computation remains dominant after algorithmic fixes. [Long-task guidance](https://web.dev/articles/optimize-long-tasks?hl=en)
5. If payload/query costs dominate, introduce an additive paginated/filterable endpoint or route-specific summary payload. Existing consumers expecting complete arrays must continue to receive them until migrated. Never silently truncate a collection used for totals, selection, or exports.
6. Inspect Oracle query plans and indexes for demonstrated slow paths. Separate database execution, row fetching, ORM materialization, and serialization. Review cache lock/coordination time under concurrency before changing cache architecture. [SQLAlchemy performance profiling](https://docs.sqlalchemy.org/en/20/faq/performance.html)

Acceptance: task lookup preparation approaches O(T + P + S); agreed large-workspace search and route budgets pass; list totals and bulk/export behavior stay correct; data/cache isolation remains intact. API changes include contract tests and explicit consumer migration.

### 6. Verify smooth UX and prevent regressions

Owner: QA and implementation owners. Dependency: each changed work package.

1. Add deterministic browser assertions for request counts, duplicate-submit prevention, stale-response rejection, loading/error states, and draft/focus/scroll preservation. Keep these in ordinary CI.
2. Run performance budgets on a dedicated, recorded runner with repeated samples. Use deterministic fixture resets and alternating before/after runs. Separate timing failures from correctness failures; do not gate on a single noisy shared-runner measurement.
3. Inspect slow-network transitions visually: stable skeleton geometry, short pending messages, no misleading empty states, no forced spinner dwell, no theme flash, and usable retry controls. Honor reduced motion and keyboard navigation.
4. Establish a provisional no-regression rule: no repeatable deterioration greater than 10% and 50 ms in a primary journey, alongside its absolute budget. Record any accepted tradeoff explicitly.
5. Roll out independently by work package. Compare the same user/device/route cohorts against baseline. Roll back the relevant change for auth failures, cross-space data leakage, lost edits, stale deployment assets, or reproducible budget regressions.

Acceptance: reproducible before/after evidence, required repository checks, and a UX walkthrough at 390, 768, 1024, and 1440 px. Performance sign-off requires both latency results and preserved behavior.

## Validation matrix and execution

| Dimension | Required scenarios |
|---|---|
| Authentication | Fresh signed-out visit; correct/incorrect credentials; double submit; temporary-password reset; valid session; expired access with valid refresh; expired/revoked/idle session; server error and offline recovery |
| Identity and context | Regular member; space admin; global admin; lobby-only account; developer mode; one and many memberships; workspace switch during a slow request; logout while requests are pending |
| Navigation | Direct route URL; back/forward; warm/cold module cache; rapid A → B → C navigation; lazy-module failure; public Program Dashboard |
| Interactions | Search, filters, sorting, menus, drawer open/close, create/edit/save, bulk actions, calendar navigation, board dragging, dense-table scrolling |
| Background activity | Refresh during editing; multiple entity invalidations; reconnect storm; hidden/resumed tab; multiple tabs; token refresh concurrent with route reads |
| Scale | Synthetic small/typical/large fixtures initially at 100/1,000/10,000 tasks, with realistic project/solution/user ratios and description sizes; calibrate against anonymized production counts |
| Infrastructure | Cold/warm browser cache; cold/warm API cache and DB pool; Oracle/Redis UAT; controlled latency and CPU profiles; deployed cache/compression headers |

Start with 30 repeated lab journeys per selected profile and report sample count and raw distributions. Treat initial p95 values as directional until enough stable samples exist; use larger repeated interaction samples and field/UAT data for sign-off. Test concurrent logins and navigation at provisional 1/10/25-user levels in an isolated environment, replacing these with representative concurrency after baseline discovery. Record pool wait, auth CPU cost, throughput, and error rates together.

Use `scripts/run_ui_smoke_app.py` and the existing Playwright setup for disposable local functional fixtures. SQLite smoke results cannot establish Oracle/Redis production latency. No load testing against production is part of this document-only task.

For future implementation, apply the checks required by [CONTRIBUTING.md](../CONTRIBUTING.md):

```text
# Frontend structural changes
python scripts/check_route_module_test_mapping.py
npm run lint:ui
npm run test:ui
npm run test:ui:coverage
npm run test:ui:smoke

# Backend/shared runtime changes
npm run test:backend
npm run test:backend:coverage
npm run test:backend:integration

# Dependency changes
python scripts/check_requirements_lock.py
```

Backend integration checks require the configured Redis service. Extend the existing session, router, data-store, telemetry, auth/dependency, space-isolation, and responsive browser suites. The UI coverage configuration excludes `app.js`, so moving startup behavior needs explicit behavioral/browser coverage rather than reliance on the aggregate coverage percentage.

## Delivery checkpoints

| Checkpoint | Deliverable | Exit condition |
|---|---|---|
| Baseline | Journey traces, phase timings, fixture inventory, agreed budgets | Bottlenecks ranked by measured user impact |
| Startup | Session-restoration and auth-path PRs | Login/reopening budgets and auth regressions pass |
| Navigation | Request scheduling and refresh PR | Foreground work is prioritized; state is preserved |
| Asset delivery | Deferred initialization/styles and versioned caching PRs | Cold/warm improvement plus release-transition tests |
| Scale | Targeted rendering/query/payload PRs | Large-fixture budgets and data contracts pass |
| Sign-off | Before/after report and deployed verification | Product budgets, UX checks, and required tests pass |

Assign effort estimates after the baseline. Do not commit to a completion date before identifying whether the dominant cost is browser startup, authentication CPU, Oracle/network latency, or data volume.

## Closure ledger

- **Completed now:** source review, static asset counts, prioritized findings, work packages, target budgets, and validation plan.
- **Fixed now:** none; this is a plan-only deliverable.
- **Flagged for implementation:** PERF-01 through PERF-08, with payload/API and infrastructure changes conditional on profiling evidence.
- **Not verified:** actual login/navigation timings, deployed compression/caching, representative device performance, Oracle query plans, concurrent-user capacity, and current test pass status. Tests were inspected but not executed for this documentation-only change.
- **Out of scope:** application edits in this task, authentication-policy changes, a frontend framework rewrite, unrelated feature redesign, production load tests, and deployment execution.

Begin execution with package 1. Performance closure requires measured improvement on the real user journeys; completion of the code changes alone is insufficient.
