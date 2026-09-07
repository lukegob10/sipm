# Startup performance implementation

This is a bounded PERF-01/package-4 performance optimization against baseline
`3e77295342d4314539a151df294f62c6efabcc76`. It reduces signed-out JavaScript and
initial event binding while preserving the existing UI and shared editors.
It does not close the broader login and navigation performance plan.

## Change and evidence

`app.js` previously statically imported the large Spaces renderer/controller
and Deliverables interactions/quickstart. It bound governance forms before
starting session discovery. The initial `setView` also fetched the hidden
Deliverables renderer and table.

The existing Spaces/Access and Deliverables entrypoints now export their
controllers and bindings. The router calls a synchronous initialization hook
before publishing a module in its cache. Its existing in-flight promise shares loading and initialization;
warm navigation reuses the initialized module. Spaces and Platform Access also
share an explicit controller guard because they use the same forms.

The first shell route selection uses `loadContent: false`; authentication still
selects and loads the authorized route using the existing session code. Shared
program/project/solution/task forms, navigation, modal shortcuts, theme,
password reset, and public dashboard paths remain available as before. Tasks
and Team Capacity bindings stay eager because their static HTML controls are
visible while a route renderer loads. An integration review caught that
deferring Tasks bindings could discard text entered during a slow import; the
final patch keeps those bindings eager and adds delayed-import regressions for
both routes. Deliverables is different: `index.html` has empty filter/table
containers and a hidden empty quickstart container. The renderer creates
`#filter-query`; a held-import test checks that the control is absent while
loading and works immediately after rendering. Live-sync governance refresh
retains its API behavior and loads its controller on demand if necessary; the
added await guards against a changed user or space before issuing the read.

Static graph evidence from parsing ImportDeclaration and re-export nodes:

| Measure | Baseline | Current |
|---|---:|---:|
| Static app modules | 41 | 37 |
| Static graph raw bytes (LF) | 547,782 | 410,686 |
| Signed-out requested modules | 43 | 37 |
| Signed-out served raw JS bytes (LF) | 562,216 | 410,686 |
| Signed-out listener registrations | 218 | 195 |

The signed-out served-source reduction is 151,530 bytes (27.0%). The static
graph reduction is 25.0%. Both benchmark variants use LF-normalized source to
exclude Git/Windows checkout conversion from the comparison. These are raw
JavaScript byte measurements, not compressed transfer sizes. The provisional
40% target is not met by this deliberately bounded change.

## Behavior checks

The new browser suite exercises signed-out home and Tasks entrypoints, reset,
direct Team Capacity entry, repeat navigation with a capacity draft and one
save request, Tasks filter retention across back/forward and during a held
first renderer import, Team Capacity draft/filter retention during a held
import, lobby governance, Spaces/Platform Access shared modal bindings, public dashboards, and developer
direct links. It also creates a project immediately from Calendar without
visiting Deliverables, operates Calendar controls, and opens/closes the task
drawer with Escape/E while checking focus return to its row/editor.

A failed governance controller request is checked for recovery after a browser
reload, and router unit tests cover shared loading, once-only initialization,
and initialization failure/retry. No new retry UI or copy is introduced.
The existing browser suite covers login request counts, responsive layouts at
390/768/1024/1440 pixels and wider, navigation, and theme contrast. No HTML or
CSS changed. `app.js` is excluded from aggregate unit coverage, so the browser
tests are the primary validation for its wiring.

## Reproduction and validation

Dependencies were copied from the coordinating checkout into this worktree's
ignored `node_modules`. Python used the coordinating checkout's existing
`.venv/Scripts/python.exe`; the smoke script and application source under test
were always in this isolated worktree. The server used SQLite and in-memory
coordination on port 8773. Node needed normal filesystem access because the
sandbox denied module-resolution access to the user-profile parent directory.

Commands run from the worktree:

```powershell
& 'F:\vault\projects\the-eco-system\sipm\.venv\Scripts\python.exe' scripts/check_route_module_test_mapping.py
npm run lint:ui
npm run test:ui
npm run test:ui:coverage
$env:SIPM_UI_SMOKE_PORT = '8773'
& 'F:\vault\projects\the-eco-system\sipm\.venv\Scripts\python.exe' scripts/run_ui_smoke_app.py
# In a second shell using that same worktree:
$env:SIPM_UI_SMOKE_PORT = '8773'
$env:SIPM_UI_SMOKE_REUSE_SERVER = 'true'
npm run test:ui:smoke -- --workers=1
# The final additional boundary test was run separately after the full suite:
npm run test:ui:smoke -- startup-entrypoints --grep "Deliverables creates" --workers=1
& 'F:\vault\projects\the-eco-system\sipm\.venv\Scripts\python.exe' -m pytest src/main/test/test_ui_route_module_test_mapping_gate.py src/main/test/test_ui_route_modules_exports.py src/main/test/test_route_stylesheet_split_contract.py -q
node src/main/ui/test/e2e/startup-performance.mjs 3e77295342d4314539a151df294f62c6efabcc76 30
```

Mapping, lint, 210 UI tests in 32 files, UI coverage, and seven focused Python
contracts pass. Coverage: statements 45.78%, branches 35.87%, functions 52.30%,
lines 48.79%. The final full browser result is recorded below.

The benchmark alternates baseline/current order for 30 samples per variant and
journey, after excluded warmups. Both use identical Playwright interception of
LF-normalized JavaScript source, with a fresh browser context for each startup. The local
fixture has one member, one private space, and one program; no tasks are needed
for these startup journeys. Signed-out readiness is the visible auth form at
the next animation frame. Restored readiness requires the seeded program in
the visible Deliverables table. Capacity navigation measures a real nav click
to the visible member row at the next animation frame. Repeat navigation uses
the same page/module map. Raw samples are written to the ignored
`.tmp/startup-performance/samples.json`, independently of Playwright's cleaned
test-results directory. These localhost timings are directional and do not
establish production/network latency or INP.

## Limits and follow-up

- Fixed now: signed-out route imports and avoidable startup bindings within
  this package; startup graph and browser regressions guard the boundary.
- Retained intentionally: shared entity editors, Tasks and Team Capacity
  bindings, and Tasks helpers; Calendar, Roadmap, and Kanban controllers
  participate in synchronous shared state restoration. Moving these requires
  a separately validated state boundary.
- Authenticated live-sync still requests governance data. In the local restored
  journey it loads the deferred governance assets before the table is ready,
  so total restored JS bytes do not decrease. This patch preserves that data
  behavior and does not change live-sync or prefetch semantics.
- CSS splitting, compressed transfer, content-versioned caching, deployment
  rollout, Oracle/Redis integration, representative large fixtures, and field
  latency/INP remain unverified or outside this package. There are no backend,
  dependency, deployment, or authentication-policy changes.
- Browser timing is local, on one desktop runner; the production latency budget
  and the provisional 40% transfer reduction remain open. Rollback is a revert
  of this isolated commit; existing route paths and asset URLs are preserved.

## Final browser and timing results

The full 24-test browser suite passed in 44.1 seconds. The final added
Deliverables held-import check then passed separately (1 test, 2.5 seconds).
All 25 browser cases in the final tree were exercised successfully.

Runner: win32, Chromium 145.0.7632.6, Node v20.19.2, 1280 x 720.
Recorded: 2026-09-07T20:48:31.479Z. Each timing row has 30 samples per variant.

| Journey | Baseline p50/p75/p95 (ms) | Current p50/p75/p95 (ms) |
|---|---:|---:|
| Signed-out auth ready | 107.5 / 120.5 / 123.6 | 105.1 / 109.2 / 123.1 |
| Restored Deliverables ready | 178.2 / 183.9 / 247.4 | 167.7 / 181.9 / 229.8 |
| First Team Capacity navigation | 46.7 / 61.4 / 63 | 46.1 / 47 / 62.2 |
| Repeat Team Capacity navigation | 13.4 / 13.9 / 14.8 | 13.3 / 13.5 / 14 |

Repeat navigation fetched zero new modules in every baseline and current sample.
The restored journey requested 43/44 modules and 562,216/563,540 raw bytes
(baseline/current), consistent with preserving the existing live-sync governance
read and adding a small route entrypoint. The reliable result is the smaller
signed-out dependency graph. Timing gains are modest and runner-specific.

Raw timing arrays below retain sample order (milliseconds, rounded to 0.1).
The generated JSON also includes per-sample module/byte/listener counts and
unrounded measurements.

```json
{
  "baseline-signed-out-readyMs": [106.7, 120.7, 120.5, 103.1, 121.2, 105.7, 118.5, 120.7, 103.4, 107.1, 121.5, 107.5, 121.5, 118.4, 101.8, 115.1, 127.3, 109.7, 116.1, 102.4, 105.8, 120.5, 104.7, 118.6, 107.4, 99, 104.8, 102.4, 104.2, 123.6],
  "baseline-restored-readyMs": [183.9, 180.6, 178.3, 170.8, 178.2, 213.8, 178.4, 164.7, 165.3, 343.7, 164.8, 199.5, 179.1, 177.6, 179.1, 191.6, 193.5, 190.9, 164.6, 175.7, 172, 165, 175.7, 247.4, 165.3, 163.7, 166.2, 171.9, 183.3, 178.7],
  "baseline-restored-firstCapacityMs": [46.4, 63, 63.6, 60.8, 44.9, 60.3, 61.4, 61.1, 45.1, 46.2, 62.1, 62, 46.1, 62, 62, 61.4, 61.7, 44.6, 45.9, 60.6, 44.6, 45.3, 47, 46.3, 46.7, 46, 46.4, 44.8, 46.4, 61],
  "baseline-restored-repeatCapacityMs": [13, 13.7, 12.8, 11.6, 12.2, 13.7, 13.4, 15.2, 12.4, 12.9, 14.4, 13.5, 12.2, 13.9, 13.4, 12.8, 14.8, 13.6, 14, 12.4, 12.4, 14.4, 12.5, 14.6, 12.6, 12.9, 12.4, 13.4, 13.5, 14.1],
  "current-signed-out-readyMs": [102.6, 104.3, 130.9, 101.5, 104.3, 104.1, 106.6, 106.5, 105.8, 105.1, 107.1, 104.8, 121.6, 105.3, 105.8, 103.9, 109.2, 120.2, 123.1, 103.8, 103.5, 101.2, 114, 121.4, 106.1, 102.1, 104.6, 104.4, 105, 120.8],
  "current-restored-readyMs": [173.3, 165, 230.8, 178.4, 163.8, 164.9, 159.1, 163.8, 164.9, 162.9, 227.1, 212.5, 178.8, 165.7, 161.4, 192.4, 164.6, 177.2, 176.2, 180.2, 167.7, 181.9, 229.8, 180, 154.5, 208.6, 161, 195, 163.9, 167],
  "current-restored-firstCapacityMs": [45.8, 45.4, 62.1, 61.6, 45.8, 45.1, 45.8, 46.4, 46.1, 45.7, 45.8, 63.8, 45.2, 45.6, 45.3, 45.4, 62.2, 46.1, 43.9, 46.4, 47, 46.2, 46.1, 46, 46.1, 46.7, 59.8, 62, 47.7, 46.3],
  "current-restored-repeatCapacityMs": [13.3, 12.9, 13.2, 13.7, 13.7, 13.4, 13.4, 13.3, 13, 13.9, 14.2, 12.7, 12.7, 8.6, 13.5, 13.4, 13.5, 14, 12.9, 13.3, 12.6, 13.3, 13.6, 12.3, 12.8, 13.4, 12.8, 12.5, 13.8, 12.6]
}
```

Integration note: the coordinator migrated the global-admin browser fixture from
`/auth/active-space` to `/auth/bootstrap` and overrides its
`active_space.is_global_admin` property. The asset-budget test now normalizes
line endings, matching the measurement above, and the older Python structural
checks follow the new route exports. All 31 combined browser cases, 317 UI tests,
and 212 backend/UI contract tests pass. See the [integration report](performance-integration-20260907.md)
for combined measurements and validation; the package-level results above retain
their original isolated scope.
