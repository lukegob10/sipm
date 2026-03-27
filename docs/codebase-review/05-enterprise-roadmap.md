# SIPM Enterprise Roadmap

Date: 2026-03-25
Mode: enterprise-quality alignment, wave 1
Scope default: repo-first, behavior-preserving, no intentional API/schema/UI route/DOM ID changes

## Purpose
- convert `docs/codebase-review/` from cleanup memory alone into the forward operating system for enterprise-quality execution
- keep the assessment in `docs/project-assessment-2026-03-25.md` as the executive artifact
- use epics for forward planning and small PRs for implementation

## Status Model
- `completed`: roadmap setup or epic exit criteria are satisfied
- `queued`: approved and ready for implementation slices
- `active`: currently being worked
- `blocked`: waiting on an explicit register decision in `04-review-required.md`

## Wave 1 Budgets

| Surface | Budget |
| --- | --- |
| `src/main/ui/js/app.js` | `<= 4000` LOC |
| Any route-local JS module | `<= 700` LOC |
| Any backend route module | `<= 500` LOC |
| Any route stylesheet | `<= 900` LOC |

These budgets are enforced as report-only through `scripts/codebase_review.py quality-gates` until the repo is compliant.

## Milestone 0: Review-System Alignment
- Status: `completed`
- Owner: `repo-quality`
- Deliverables:
  - `05-enterprise-roadmap.md` as the forward execution artifact
  - `06-quality-gates.md` as the policy artifact
  - `04-review-required.md` repurposed as the risk / architecture register
  - `03-fix-queue.md` frozen as historical record
  - `00-system-map.md` and `02-dependency-map.md` updated with remaining gap and extraction-boundary guidance
- Exit criteria:
  - roadmap, gates, and register exist and are linked
  - forward work no longer depends on creating new `BATCH-*` entries

## Epic 1: Frontend Core Decomposition
- Status: `active`
- Owner: `frontend`
- Depends on: `ADR-001`
- Progress:
  - `2026-03-25 slice 1 completed`: moved master deliverables filter normalization, deliverable row filtering, quickstart rendering, and bulk/table interactions into `src/main/ui/js/routes/master/{filters,quickstart,interactions}.js`; `app.js` now composes route context and retains only shell-side state persistence and cross-route callbacks for this surface
  - `2026-03-26 slice 2 completed`: moved subcomponents workbench filter normalization, visible-row derivation, preset/selection UI state, and bulk-action behavior into `src/main/ui/js/routes/subcomponents-workbench/{filters,bulk-actions}.js`; `app.js` now composes workbench route context for these behaviors instead of owning the implementation bodies
  - `2026-03-26 slice 3 completed`: moved subcomponents workbench drawer visibility, activity loading, form population, drilldown/context links, editor save/delete helpers, and keyboard/click handlers into `src/main/ui/js/routes/subcomponents-workbench/drawer.js`; `app.js` now delegates these route-local behaviors through the workbench context instead of implementing them inline
  - `2026-03-26 slice 4 completed`: moved subcomponents workbench saved-view storage, selection/self-heal UI syncing, apply/save/delete handlers, and confirm/status behavior into `src/main/ui/js/routes/subcomponents-workbench/saved-views.js`; `app.js` now treats saved views as route-owned state/UI behavior and only triggers the route module through context
  - `2026-03-26 slice 5 completed`: moved subcomponents workbench preset/filter/select bindings, row-selection handling, remaining form/context/delete/reset/shortcut wiring, and solution-option ownership into `src/main/ui/js/routes/subcomponents-workbench/interactions.js`; `app.js` now only initializes the route controls and keeps render-time shell context assembly
  - `2026-03-26 slice 6 completed`: moved subcomponents workbench project/assignee option population and post-population UI-state normalization into `src/main/ui/js/routes/subcomponents-workbench/options.js`; `populateSelects()` in `app.js` now delegates the workbench-specific options surface instead of rendering it inline
  - `2026-03-26 slice 7 completed`: created `src/main/ui/js/entities/projects.js` for the shared project modal workflow, including form visibility, payload/save/delete handling, inline status feedback, and confirm-modal usage; `app.js` now keeps the existing shell callback names but delegates the implementation to the entities layer
  - `2026-03-26 slice 8 completed`: created `src/main/ui/js/entities/solutions.js` for the shared solution modal workflow, including payload construction, form fill/reset, save/delete handling, modal open/close, and the saved-parent subcomponent gate; `app.js` now preserves the existing solution callbacks while delegating the implementation to the entities layer
  - `2026-03-26 slice 9 completed`: created `src/main/ui/js/entities/subcomponents.js` for the shared subcomponent modal workflow, including payload construction, form visibility, create/edit/delete handling, inline status feedback, and repo-preview wiring; `app.js` now preserves the existing subcomponent callbacks while delegating the implementation to the entities layer
  - `2026-03-26 slice 10 completed`: created `src/main/ui/js/routes/calendar/interactions.js` for route-local calendar controls, modal drilldowns, and scoped month persistence; `app.js` now keeps only the calendar render entrypoint plus thin persistence wrappers and delegates the route-owned behavior to the calendar module
  - `2026-03-26 slice 11 completed`: created `src/main/ui/js/routes/kanban/interactions.js` for route-local kanban filtering, drilldowns, and scoped filter persistence; `app.js` now keeps only thin kanban wrappers and delegates the route-owned behavior to the kanban module
  - `2026-03-26 slice 12 completed`: created `src/main/ui/js/routes/team-capacity/interactions.js` for route-local team-capacity selection, form bindings, scoped filter persistence, and the space-aware loader pipeline; `app.js` now keeps only thin loader/binding/persistence wrappers and delegates the route-owned behavior to the team-capacity module
  - `2026-03-26 slice 13 completed`: created `src/main/ui/js/routes/spaces/interactions.js` for route-local space-governance modals, membership/admin actions, directory/platform form bindings, and modal/global event handling; `app.js` now keeps the governance render surface plus thin modal/data/binding wrappers and delegates the route-owned interaction logic to the spaces module
  - `2026-03-26 slice 14 completed`: created `src/main/ui/js/routes/spaces/render.js` for route-local governance rendering, including current-space, directory, directory modal, and platform-access surfaces; `app.js` now keeps only thin governance render wrappers while the spaces render module owns the route-specific markup and lazy-load side effects
- Target files:
  - `src/main/ui/js/app.js`
  - `src/main/ui/js/routes/master/`
  - `src/main/ui/js/routes/subcomponents-workbench/`
  - `src/main/ui/js/entities/`
- Required moves:
  - keep shell ownership limited to bootstrap, state bootstrap, route dispatch, and cross-route callbacks
  - extract deliverables filters, bulk actions, render, and interactions into route-local modules
  - create route-local modules for subcomponents workbench drawer, activity, filters, render, and interactions
  - move shared project/solution/subcomponent modal workflows into a shared entities layer
  - move route-only calendar, kanban, spaces, and team-capacity interactions into route-owned modules
- Exit criteria:
  - `app.js` is within budget
  - no route-specific render/bind logic remains in shell code
  - route export, loader, and focused frontend contract tests stay green

## Epic 2: Route Stylesheet Ownership Split
- Status: `completed`
- Owner: `frontend`
- Depends on: `ADR-002`
- Progress:
  - `2026-03-26 slice 17 completed`: split `src/main/ui/styles/routes/workbench-planning-admin.css` into route-owned partials for `subcomponents-workbench`, `planning-work-allocation`, `team-capacity`, and `space-governance`, preserved `src/main/ui/styles.css` as the single import surface, removed stale WAB summary/legend selectors that no longer match the live planning render, and reduced the legacy mixed file to shared leftovers
- Target files:
  - `src/main/ui/styles/routes/workbench-planning-admin.css`
  - `src/main/ui/styles/routes/subcomponents-workbench.css`
  - `src/main/ui/styles/routes/planning-work-allocation.css`
  - `src/main/ui/styles/routes/team-capacity.css`
  - `src/main/ui/styles/routes/space-governance.css`
- Required moves:
  - split mixed route ownership into route-scoped partials
  - keep `src/main/ui/styles.css` as the only import surface
  - preserve selector contracts while the split is underway
- Exit criteria:
  - each route stylesheet is within budget
  - the mixed stylesheet is gone or reduced to true shared leftovers
  - style contract coverage points at route-owned partials instead of the mixed file

## Epic 3: Planning Surface Decomposition
- Status: `queued`
- Owner: `backend`
- Depends on: `ADR-003`
- Target files:
  - `src/main/backend/app/routes/planning/work_allocation.py`
  - `src/main/ui/js/routes/planning/api.js`
- Required moves:
  - convert the backend hotspot into a `work_allocation/` package with `common`, `teams`, `people`, `tasks`, `allocations`, `report`, and aggregating package init
  - split planning API helpers into client calls, payload builders, and mutation/query helpers
  - keep request guards, payload shapes, cache behavior, and realtime semantics unchanged
- Exit criteria:
  - no planning route module exceeds budget
  - planning API payloads and paths remain unchanged
  - planning behavior, router composition, and report tests remain green

## Epic 4: PM Dashboard Isolation
- Status: `completed`
- Owner: `frontend`
- Depends on: `ADR-001`
- Progress:
  - `2026-03-26 slice 15 completed`: created `src/main/ui/js/routes/pm-dashboard/sections.js` for PM dashboard summary, health, risk, timeline, capacity, status, and actions rendering; `src/main/ui/js/routes/pm-dashboard/render.js` now keeps orchestration, derived dashboard state, and drilldown wiring only
- Target files:
  - `src/main/ui/js/routes/pm-dashboard/render.js`
  - new route-local PM dashboard renderer modules
- Required moves:
  - keep orchestration and section ordering in the top-level renderer only
  - extract summary, capacity, status/health/timeline, and action renderers into route-local files
  - remove PM dashboard-specific drilldown markup logic from `app.js`; keep only shell callbacks in context
- Exit criteria:
  - `pm-dashboard/render.js` is within budget
  - PM dashboard contract tests still describe the same UI behavior

## Epic 5: Repo Governance And Operability
- Status: `active`
- Owner: `repo-quality`
- Depends on: none
- Deliverables:
  - remove residual `Jira-lite` naming from repo-visible backend metadata/comments
  - add `.editorconfig`, `CONTRIBUTING.md`, `.env.example`, and `.github/CODEOWNERS`
  - add repo-only operator guidance covering runtime mode matrix, readiness semantics, Redis/Oracle expectations, and incident triage
  - add a report-only `quality-gates` command to repo tooling
- Exit criteria:
  - governance artifacts exist and are source-of-truth linked
  - `quality-gates` reports known violations without blocking CI
  - the repo has no remaining `Jira-lite` runtime branding

## Supplemental Hotspot Clearance
- `2026-03-26 slice 16 completed`: split `src/main/backend/app/routes/projects.py` into `src/main/backend/app/routes/projects/{common,read,write,import_export}.py`, preserved `/projects` route behavior and the package-level conflict-detector helper import used by tests, and cleared the projects backend budget violation

## Known Current Violations
- `src/main/backend/app/routes/planning/work_allocation.py` exceeds the backend route budget
- additional backend route files may still surface in `quality-gates` as the codebase evolves

## Execution Rules
- Ship each epic in small PRs with characterization coverage first when active behavior is being moved.
- Re-run focused validation after every slice, then run the full regression set before closing an epic.
- Do not make `quality-gates` blocking until the register decision for rollout is closed and the repo passes twice in CI.
