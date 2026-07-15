# SIPM Agent API Local Performance Baseline

Date: 2026-07-15

## Purpose

This document records the Phase 0 Agent API baseline before pagination and read-model changes. It is intended to make later performance work measurable and repeatable. It is not a production capacity claim.

The benchmark harness is [`scripts/benchmark_agent_api.py`](../scripts/benchmark_agent_api.py). It creates a temporary SQLite database, seeds a deterministic space and work hierarchy, calls the real FastAPI application through an in-process ASGI transport, and reports:

- Minimum, p50, p95, and maximum request latency.
- SQL statement count per request.
- Serialized response size.

The temporary database is deleted after the run. The harness does not modify the application schema, repository database, or deployed Oracle environment.

## Baseline Command

```powershell
python scripts/benchmark_agent_api.py --iterations 10
```

Default dataset:

- 1 space.
- 10 programs.
- 250 projects.
- 2 solutions per project, 500 total.
- 4 tasks per solution, 2,000 total.
- 10 measured requests per case after authentication warmup.

## Results

| Case | SQL statements | Response bytes | p50 ms | p95 ms |
|---|---:|---:|---:|---:|
| Manifest | 5 | 476 | 9.52 | 12.99 |
| Program list | 6 | 1,191 | 10.38 | 12.71 |
| Work graph, 50 projects | 10 | 137,645 | 35.18 | 41.84 |
| Work graph, 200 projects | 10 | 546,845 | 95.26 | 224.89 |
| Work graph, one project | 10 | 3,973 | 11.03 | 12.15 |
| Validate one project update | 6 | 256 | 8.24 | 9.67 |

## Interpretation

- Work-graph SQL statement count is currently bounded rather than growing per project. The implementation batches programs, projects, solutions, and tasks instead of issuing an obvious N+1 query chain.
- Response size grows materially with the number of projects and nested children. The current 200-project maximum page is approximately 547 KB even with the graph's summary-only fields.
- The maximum page had substantially higher and less stable local latency than the default page. This supports adding cursor pagination, explicit `has_more`, detail endpoints, and response-size limits before spaces contain much larger work hierarchies.
- A one-project graph is small, but it pays the same 10-statement request cost as a broad graph. Dedicated project, solution, and task detail endpoints should be measured against this baseline when implemented.
- Authentication and space resolution account for part of every query count. The benchmark intentionally measures complete authenticated endpoint requests rather than isolated service functions.

## Limitations

- SQLite query planning and latency do not represent deployed Oracle behavior.
- In-process ASGI transport excludes network, proxy, TLS, and process-boundary latency.
- Results depend on local hardware and concurrent system load.
- The default dataset represents a useful development baseline, not the final target scale described in the full-scale workflow roadmap.
- Exact counts and timing may change as authentication, caching, and response contracts evolve.

For those reasons, future changes should compare results from the same harness and dataset, while production-readiness decisions should also use representative Oracle query plans and environment-level load testing.

## Repeating At Larger Volumes

The dataset is configurable without editing the script:

```powershell
python scripts/benchmark_agent_api.py `
  --projects 2000 `
  --solutions-per-project 3 `
  --tasks-per-solution 8 `
  --iterations 20
```

Large runs should record:

- Dataset dimensions.
- Command and environment.
- Query-count changes.
- Response-size changes.
- p50 and p95 changes.
- Whether memory use or serialization becomes the limiting factor.

## Phase 0 Baseline Status

- Repeatable harness: complete.
- Deterministic local seed: complete.
- Query count: recorded.
- Response size: recorded.
- Local p50 and p95: recorded.
- Production Oracle benchmark: not verified and not required for the application-only Phase 0 baseline.
- Database changes: none.

## Post-Implementation Smoke Baseline

After the paginated graph, direct reads, search, audit, and supporting discovery endpoints were implemented, the same harness was rerun on July 15, 2026 with 100 projects, 200 solutions, 800 tasks, and three iterations per case:

| Case | Max SQL statements | Response bytes | p50 ms | p95 ms |
|---|---:|---:|---:|---:|
| Manifest | 2 | 874 | 1.98 | 2.43 |
| Program list | 8 | 1,371 | 7.30 | 16.14 |
| Work graph, 50 projects | 10 | 120,669 | 23.39 | 27.40 |
| Work graph, up to 200 projects | 10 | 239,543 | 33.55 | 33.86 |
| Work graph, one project | 10 | 3,527 | 9.22 | 9.79 |
| Validate one project update | 6 | 267 | 6.30 | 7.39 |

This smoke run confirms bounded graph query count and latency comfortably below the roadmap's local engineering targets. It does not replace representative Oracle load testing. No index or other database change is justified by this evidence.
