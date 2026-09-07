# Navigation data-loading implementation

Date: 2026-09-07
Mode: performance optimization
Baseline: `3e77295342d4314539a151df294f62c6efabcc76`
Scope: PERF-03 and the request-coalescing portion of PERF-04, package 3 of the coordinating login-performance-and-responsiveness plan.

## Changes and preserved contracts

- Foreground loads start their missing collection reads immediately. The latest load owns loading status, route rendering, selection restoration, and `onViewDataLoaded`; superseded callers still await their own required data and route-module readiness. A cached destination also takes ownership immediately.
- Collection reads share a promise only for the same data generation, signed-in identity, space, entity endpoint, and invalidation version. The existing seven collection endpoints have no query parameters. Requests are released when they settle; logout and space changes clear the registry and abort active controllers. `clearDataState()` remains the context-transition boundary.
- Force reloads and live refresh events immediately invalidate the affected collections, increment their versions, and abort obsolete reads. Old snapshots cannot become loaded data. Existing foreground/refresh awaiters follow the new read. Final dependency checks catch invalidation while another collection or a route module was pending, including dependencies that were initially cached.
- Queued known refreshes retain their exact entity union. Unknown/full refreshes retain the existing seven-collection fallback. Already-refreshed collections can satisfy the pending refresh without another request. A refresh queued behind a foreground load retains the existing enqueue-and-return promise behavior; an immediately started refresh awaits its data and UI work.
- Prefetch remains delayed by 450 ms, runs at most two speculative collection consumers, and yields to foreground work. Navigation cancels the schedule and prevents canceled prefetch consumers from starting invalidation retries. Already-running useful requests remain shareable. Hidden tabs, save-data connections, and detected 2G connections skip speculative work.
- Successful collection application marks form options as needing synchronization. A cached destination receiving another route's partial results synchronizes those options before rendering. Unchanged cached navigation does not repeatedly populate controls or restore editors. Full synchronization reads the currently selected form IDs immediately before syncing, avoiding restoration of a selection from request start.
- Existing status text, route-ready callbacks, partial/error handling, My Work task-refresh invalidation, team-capacity request cancellation, API paths, payload semantics, and authentication refresh implementation remain in place. A silent/cached replacement settles a visible loading status inherited from an earlier foreground load.

No application wiring, routes, styles, telemetry, task rendering/filtering, backend code, or dependencies changed.

## Deterministic before/after evidence

The original 13 data-store tests passed before editing production code. Three new regressions were then run against the baseline and failed with the following observed results. They pass with this implementation; the suite now contains 36 data-store tests.

| Controlled scenario | Baseline observation | Implemented observation |
|---|---|---|
| A requests projects; B requests solutions; C requests tasks while A is held | Only `/projects` starts; C cannot start until A releases | `/projects`, `/solutions`, `/tasks` start immediately; C becomes ready before either A or B resolves |
| Prefetch `/projects`, then foreground navigation while it is held | Two `/projects` requests | One shared `/projects` request, a 50% reduction |
| Hold a phases refresh; enqueue projects, tasks, tasks | Eight requests total: initial phases, then phases/programs/projects/solutions/tasks/teams/users | Three total: phases/projects/tasks; follow-up reads fall from seven to two |

These are request counts and ordering evidence, not production latency measurements. Unit fixtures contain zero or one record per collection and use explicitly resolved promises and fake timers; the results do not depend on wall-clock speed.

Additional regressions cover A→B→A; old non-auth failures and completion callbacks; same-space identity/generation changes; old-space loads, refreshes, and prefetches; logout; foreground/refresh sharing; multiple force calls completing out of order; post-mutation invalidation; cached dependency invalidation; invalidation during module loading and multi-entity refresh; inherited loading status; current form selection; cached handoff control synchronization; bounded prefetch; canceled-prefetch retry suppression; and full/unknown refresh fallback.

The new real-browser test creates a personal space, program, and project, holds task responses during Deliverables→Roadmap→Calendar, and verifies that Calendar renders its days and populated project filter before the task responses release. It changes month and edits/focuses the owner filter, then verifies the active route, month, filter value, and focus survive the late responses.

## Validation

All commands ran with this worktree as the current directory and source under test:

`C:\Users\Luke Goblirsch\.codex\worktrees\c6e0\sipm`

Existing dependencies were borrowed through an ignored local `node_modules` junction to the coordinating checkout. Python came from its existing `.venv`. No dependency installation or coordinating source edit was performed. Node needed execution outside the filesystem sandbox because Node path resolution otherwise failed with `EPERM` on the user directory.

Environment: Windows, Node `v20.19.2`, Python `3.12.2`, Vitest `4.1.8`, the repository's Playwright configuration, and disposable SQLite/in-memory coordination smoke services on port **8772**.

| Check | Result |
|---|---|
| `F:\vault\projects\the-eco-system\sipm\.venv\Scripts\python.exe scripts/check_route_module_test_mapping.py` | Passed |
| `npm run lint:ui` | Passed |
| `npm run test:ui` | 31 files, 223 tests passed |
| `npm run test:ui:coverage` | 31 files, 223 tests passed; all configured thresholds passed |
| `npm run test:ui:smoke` with the shared `.venv\Scripts` prepended to PATH and `SIPM_UI_SMOKE_PORT=8772` | 12 tests passed; auth, responsive shell, themes, navigation, and delayed-task handoff |
| `git diff --check` | Passed |

Coverage: overall statements 46.30%, branches 36.36%, functions 52.61%, lines 49.20%; data-store statements 83.58%, branches 77.28%, functions 92.30%, lines 84.79%.

The first full smoke run passed 11/12 because the new assertion incorrectly expected the existing `All` option to read `All projects`. The assertion was corrected to the current UI text; the complete rerun passed. No product copy changed.

Backend, dependency-lock, Oracle, and Redis integration checks were not run: this patch changes frontend code only, and the smoke environment uses disposable SQLite/in-memory coordination. Real-device timing distributions, production payload sizes, Oracle/Redis latency, and deployed network conditions remain unmeasured.

## Integration limits and follow-up

**Initial WebSocket catch-up is intentionally still fresh.** `live-sync.js` calls `reloadCurrentViewData({ force: true, silent: true, preserveCapacitySelection: false })` when the socket opens. A collection request begun before subscription cannot prove coverage of changes between its snapshot and subscription. This patch aborts that older request and starts the required fresh read; it does not claim that login or reopening issues only one set of collection reads. Eliminating this boundary safely requires a coordinated subscription/snapshot contract or proof that the foreground read began after subscription. The coordinating task agreed to retain the existing catch-up semantics.

Final integration coordinates the timing of this first catch-up: the socket subscribes immediately, while its initial forced catch-up waits for the first foreground route load to settle. This restores the baseline's ability to render the first snapshot before background catch-up and avoids canceling/restarting it during login. Live messages, reconnects, and all forced-read freshness guards remain active. The fresh catch-up still runs after success or failure unless its socket/session/context has been replaced; it is not eliminated. See the [integration report](performance-integration-20260907.md) for the measured result and validation of this additional integration change.

**Global form synchronization remains an integration boundary.** `app.js` owns `populateSelects()` and `restoreSelections()`. The latter reopens/refills project, solution, and task forms and can overwrite dirty fields on unrelated refreshes. This patch preserves those callbacks and fixes current-selection and cached-handoff behavior; it does not claim full dirty-editor protection. The minimal next integration is to pass changed entity types into the existing option-sync callback and make editor restoration conditional on the relevant entity and dirty state, preserving the draft/focus/scroll contract. Form-opening paths must populate deferred options before inactive collections or controls can safely be deferred. No inactive entity refreshes or cross-entity dependencies were dropped here.

The required browser coverage passes, but complete PERF-04 closure and the plan's latency targets still require those app-level editor changes and measured production-representative journeys. Rollback is a revert of this implementation commit; there are no schema or data migrations.
