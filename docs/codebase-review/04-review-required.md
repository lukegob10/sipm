# SIPM Review-Required Queue

Date: 2026-03-24
Policy:
- medium and major code changes require user review
- any DB schema, migration, DDL, or data-migration change requires user review
- low-risk work continues without stopping; deferred items are recorded here instead

## Active Deferred Items

No active deferred items remain from the initial seeded review-required queue.

## Closed Deferred Items

### RR-001 `BATCH-003` Frontend Shell Hotspot In `src/main/ui/js/app.js`
- Severity: Major
- Resolution: completed on 2026-03-24
- What changed: extracted shell responsibilities into `src/main/ui/js/shell/{paths,router,session,live-sync,data-store,context}.js`, standardized route modules on a primary `render(ctx)` entrypoint, and reduced `app.js` to controller wiring plus shared UI workflows.
- Validation: `pytest -q -s src/main/test/test_ui_route_modules_exports.py src/main/test/test_frontend_ux_improvement_contract.py src/main/test/test_live_sync_session_frontend_contract.py src/main/test/test_team_capacity_frontend_contract.py src/main/test/test_*frontend_contract.py src/main/test/test_context_path_routing.py`

### RR-002 `BATCH-007` Planning Backend Hotspot
- Severity: Major
- Resolution: completed on 2026-03-24
- What changed: replaced the monolithic `src/main/backend/app/routes/planning.py` with a package split across `planning/common.py`, `planning/legacy_allocations.py`, and `planning/work_allocation.py`, and moved work-allocation request/response models into `src/main/backend/app/schemas/planning.py`.
- Validation: `pytest -q -s src/main/test/test_planning_fte_month.py src/main/test/test_planning_work_allocation_people.py src/main/test/test_planning_work_allocation_tasks.py src/main/test/test_planning_work_allocation_report.py src/main/test/test_planning_router_composition.py`

### RR-003 `CCR-007` Observability / Operations Pass
- Severity: Medium
- Resolution: completed on 2026-03-24
- What changed: added request-ID middleware, structured request/error logging, `/health/ready`, DB readiness checks, and README ops documentation in `src/main/backend/main.py`, `src/main/backend/app/db/db.py`, and `src/main/README.md`.
- Validation: `pytest -q -s src/main/test/test_observability.py src/main/test/test_context_path_routing.py src/main/test/test_seed_and_db.py`

## Deferred Discovery Rules
- Add new items here only if they are medium+, DB-related, or would change public contract/semantics.
- Each new item must include: severity, why deferred, impacted files/area, exact decision needed, recommended choice.
- Do not add low-risk cleanup work here; execute it in the single pass instead.
