# Oracle Performance Enhancement Plan

## Objective
Make SIPM feel consistently fast on Oracle by reducing query latency, avoiding unnecessary round-trips, and improving first-load UX.

## Success Metrics
- API read endpoints: p95 < 300 ms under normal interactive load.
- API write endpoints: p95 < 500 ms.
- Deliverables initial render after login: < 2.0 s on typical corporate network.
- Search/filter interactions: visible update < 300 ms.
- Error rate from DB timeouts/connection issues: < 0.5%.

## Current State Snapshot
- Backend uses SQLAlchemy with `oracle+oracledb` and TAConnection creator.
- SQLAlchemy pool controls are already present:
  - `SIPM_DB_POOL_SIZE`
  - `SIPM_DB_MAX_OVERFLOW`
  - `SIPM_DB_POOL_TIMEOUT_SECONDS`
  - `SIPM_DB_POOL_RECYCLE_SECONDS`
  - `SIPM_DB_POOL_PRE_PING`
- App includes scoped in-memory smart cache for selected endpoints.
- Frontend already supports incremental view loading, but several pages still fetch broad datasets.

## Priority Plan

## P0: Baseline and Measurement (Week 1)
- Add endpoint-level timing logs for all API handlers with route, duration, and status.
- Add slow-query logging in SQLAlchemy (`>200 ms`) in non-prod and perf test environments.
- Capture baseline p50/p95 per endpoint and top SQL by elapsed time.
- Define a repeatable perf scenario:
  - Login
  - Load Deliverables
  - Filter by Sponsor/Status
  - Open Project/Solution
  - Download CSV

Expected impact: Gives a factual hotspot list and prevents guessing.

## P1: Oracle SQL and Index Tuning (Weeks 1-3)
- Review execution plans for top 10 slow SQL statements.
- Add/adjust composite indexes based on real predicates and sort order, especially where `space_id` and `deleted_at` are used together.
- Ensure foreign-key columns used in joins are indexed.
- Gather fresh optimizer stats after major data changes (`DBMS_STATS`).
- Validate cardinality/histograms on highly skewed columns (status, owner, assignee) when needed.
- For soft-delete patterns, consider function-based indexes if predicates include nullable `deleted_at` logic.

Expected impact: 20-60% latency reduction on hot reads if current plans are suboptimal.

## P2: SQLAlchemy and Driver Efficiency (Weeks 2-4)
- Remove N+1 query patterns using eager loading (`selectinload`/`joinedload`) where appropriate.
- Return only required columns for list/grid endpoints.
- Add pagination defaults for heavy list endpoints.
- Tune oracledb fetch behavior for large reads (arraysize/prefetchrows) where profiling supports it.
- Keep bind parameters everywhere and avoid dynamic SQL text shape changes that hurt plan reuse.
- Confirm pool sizing against actual concurrency and DB limits.

Expected impact: Fewer DB round-trips and lower CPU time per request.

## P3: API Response and Caching Strategy (Weeks 3-5)
- Expand scoped cache usage to expensive read endpoints with short TTLs.
- Add explicit cache invalidation hooks on writes for affected spaces/entities.
- Cache derived dashboard aggregates by space and date window.
- Add conditional fetch support (ETag/If-None-Match) for high-frequency read endpoints.

Expected impact: Major improvement for repeated navigation and dashboard views.

## P4: Frontend Responsiveness (Weeks 3-6)
- Avoid full-entity refetch on small edits; refresh only impacted entities.
- Debounce filter inputs (150-300 ms) and cancel stale in-flight requests.
- Use skeleton/loading states to reduce perceived latency.
- Virtualize very large tables if row counts regularly exceed a few hundred.
- Keep auth gating strict so internal views never flash before session check.

Expected impact: Faster perceived performance and fewer redundant network calls.

## P5: Operational Hardening (Weeks 5-8)
- Add dashboards/alerts for:
  - p95 route latency
  - DB connection pool wait time
  - slow query count
  - 401/423 auth churn
- Add a weekly query-review cadence with top regressions.
- Add performance regression checks to CI for critical user journeys.

Expected impact: Sustains gains and prevents slowdowns from reappearing.

## 30/60/90-Day Rollout
- 30 days:
  - Baseline complete
  - Top slow SQL identified
  - First index/query fixes deployed
- 60 days:
  - Endpoint pagination/projection complete
  - Cache coverage expanded for top read paths
  - Frontend filter/request optimizations shipped
- 90 days:
  - Observability dashboards and alerts live
  - Perf regression suite in CI
  - Formal before/after report

## Suggested Backlog (Implementation Order)
1. Instrument route and SQL timings.
2. Benchmark current p95 for core user flows.
3. Tune top 10 SQL statements (plans + indexes + stats).
4. Remove N+1 and over-fetching on list endpoints.
5. Add pagination/projections where missing.
6. Expand scoped cache + invalidation coverage.
7. Add frontend debounce/cancel and targeted refresh.
8. Add dashboards/alerts and CI perf checks.

## Oracle-Focused Verification Queries (DBA/Privileged)
```sql
-- Top SQL by elapsed time (sample)
SELECT sql_id,
       executions,
       elapsed_time/1e6 AS elapsed_seconds,
       cpu_time/1e6 AS cpu_seconds,
       buffer_gets,
       rows_processed
FROM v$sql
WHERE executions > 0
ORDER BY elapsed_time DESC
FETCH FIRST 20 ROWS ONLY;
```

```sql
-- Check table/index stats freshness (sample)
SELECT owner,
       table_name,
       last_analyzed,
       num_rows
FROM all_tab_statistics
WHERE table_name LIKE 'TB_TA_PM_%'
ORDER BY last_analyzed NULLS FIRST;
```

## Notes on Separate Login URL
A separate `/login` route can improve architecture and reduce accidental UI exposure risk, but it is not required for performance. Perceived speed gains come more from query, caching, and request-shape optimization.
