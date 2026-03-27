# SIPM Risk And Architecture Register

Date: 2026-03-25
Purpose:
- track the open architecture decisions and medium+ risks that still matter after the initial cleanup program
- keep historical deferred work traceable without using this file as a generic backlog

## Active Items

### `ADR-001` Frontend Core Decomposition Boundary
- Severity: Major
- Area: `src/main/ui/js/app.js`, route-local UI modules, shared entity workflows
- Why open: `app.js` still owns too much route-specific behavior, modal workflow code, and view-specific interaction logic for an enterprise-quality shell boundary.
- Decision needed: where shared project/solution/subcomponent workflows should live as `app.js` shrinks further.
- Recommended choice: keep shell ownership limited to bootstrap, route dispatch, global state, and cross-route callbacks; move entity-specific modal workflows into `src/main/ui/js/entities/`; keep route-only behavior in route-local modules.
- Blocked public contracts: none; preserve existing UI routes, DOM IDs, and visible interaction behavior while ownership moves.

### `ADR-002` Route Stylesheet Ownership Policy
- Severity: Major
- Area: `src/main/ui/styles/routes/workbench-planning-admin.css` and planned split partials
- Why open: the mixed route stylesheet is still a concentration risk and makes visual ownership ambiguous across planning, workbench, team-capacity, and space-governance surfaces.
- Decision needed: whether new route styles should stay mixed until the split finishes or move immediately into route-owned partials.
- Recommended choice: move new rules directly into route-owned partials; leave only proven shared route chrome in the compatibility layer; require style-contract coverage for any selector that remains shared.
- Blocked public contracts: none; preserve selector contracts and visible layout unless fixing a proven defect.

### `ADR-003` Planning Work Allocation Package Boundary
- Severity: Major
- Area: `src/main/backend/app/routes/planning/work_allocation.py`
- Why open: the route package root exists, but the work-allocation file is still a backend hotspot and carries too many behaviors in one module.
- Decision needed: how to split route ownership without accidentally changing payload shapes, cache behavior, or permission handling.
- Recommended choice: keep the existing route package and wire contract; split the file into `common`, `teams`, `people`, `tasks`, `allocations`, and `report`; keep shared guards and publishing behavior in package-local common helpers.
- Blocked public contracts: none; preserve the existing planning API paths and request/response semantics.

### `ADR-004` Quality Gate Enforcement Rollout
- Severity: Medium
- Area: `scripts/codebase_review.py`, CI policy, review workflow
- Why open: the repo now needs explicit size and process gates, but the current codebase still violates the target budgets in several known hotspots.
- Decision needed: when the new `quality-gates` command should become CI-blocking instead of report-only.
- Recommended choice: keep `quality-gates` report-only until Epics 1-4 are compliant locally and in CI twice in a row; only then make it required in the workflow.
- Blocked public contracts: none.

### `ADR-005` Repo-Scoped Operability Boundary
- Severity: Medium
- Area: runtime/operator documentation and future observability work
- Why open: the repo now has readiness, request IDs, and structured logging, but the enterprise-quality gap still includes missing metrics, tracing, and production runbook depth.
- Decision needed: whether wave 1 should add vendor-specific observability or deployment artifacts.
- Recommended choice: stay repo-first in wave 1; add runtime mode docs, readiness semantics, Redis/Oracle expectations, and incident triage guidance only; defer vendor-specific metrics/tracing/IaC decisions until hotspot reduction lands.
- Blocked public contracts: none.

## Closed Historical Items

### RR-001 Frontend Shell Hotspot
- Resolution: completed on 2026-03-24
- Historical note: extracted shell responsibilities into `src/main/ui/js/shell/{paths,router,session,live-sync,data-store,context}.js`, standardized route modules on a primary `render(ctx)` entrypoint, and reduced `app.js` to controller wiring plus shared UI workflows.

### RR-002 Planning Backend Hotspot
- Resolution: completed on 2026-03-24
- Historical note: replaced the monolithic `src/main/backend/app/routes/planning.py` with a package split across `planning/common.py`, `planning/legacy_allocations.py`, and `planning/work_allocation.py`, and moved work-allocation request/response models into `src/main/backend/app/schemas/planning.py`.

### RR-003 Observability / Operations Pass
- Resolution: completed on 2026-03-24
- Historical note: added request-ID middleware, structured request/error logging, `/health/ready`, DB readiness checks, and README ops documentation.

## Register Rules
- Add new entries only for medium+ risks, unresolved architecture choices, or rollout questions that materially change execution.
- Each active item must state: area, why open, exact decision needed, recommended choice, and blocked public contracts if any.
- Do not use this file for small cleanup tasks or general backlog items; put execution work in the enterprise roadmap instead.
