# SIPM Capacity Assessment

Date: 2026-03-27

Scope: practical user-capacity estimate for the current SIPM application based on the present codebase, a 3-pod deployment, and an Oracle-backed runtime.

## Executive Summary

SIPM is in good shape for a larger internal rollout than the current `10-15` users, but it should be positioned as a departmental application right now, not as an enterprise-wide platform.

My best current estimate is:

- safe current band: `75-150` named users
- practical concurrent activity band: `20-40` concurrently active users overall
- planning-heavy concurrent band: `10-20` users actively using `#/planning` at the same time

With runtime tuning and proof from load testing, I think the application could likely move into this next band:

- tuned band: `150-300` named users
- tuned concurrent activity band: `30-60` concurrently active users overall

What I would not promise today without load testing, production telemetry, and deployment-resource confirmation:

- `500+` named users
- `100+` concurrently active users
- a company-wide rollout with hard SLA claims

## Bottom-Line Position

If this needs a short stakeholder answer, I would describe SIPM like this:

> SIPM should comfortably handle a broader internal rollout beyond the current team and is likely ready for low-hundreds total users, but the present deployment should still be treated as department-scale rather than enterprise-scale until we run a real load test and confirm Oracle and pod headroom.

## Assessment Basis

This estimate is based on:

- the existing application assessment in `docs/project-assessment-2026-03-26.md`
- current runtime configuration in `.env.example`
- Oracle session and pool setup in `src/main/backend/app/db/db.py`
- runtime and readiness behavior in `src/main/backend/main.py`
- Redis coordination and cross-pod realtime behavior in `src/main/backend/app/services/coordination.py` and `src/main/backend/app/services/realtime.py`
- current planning-board request behavior in `src/main/ui/js/routes/planning/api.js`

Important limitation:

- this repository does not include the live Kubernetes manifests or measured production telemetry
- I could not verify pod CPU and memory requests, autoscaling policy, ingress limits, Oracle session quotas, or real production latency from source control
- there is no repo-visible load-test harness or prior benchmark record

Because of that, this is an engineering estimate, not a measured performance certification.

## Assumptions Behind The Numbers

The user-capacity ranges in this document assume:

- `3` application pods, as described for the live deployment
- one app process per pod unless the live deployment explicitly configures more
- the deployment is close to the repo-default DB pool settings
- Redis is present and healthy in non-dev runtime
- usage is human-driven browser activity, not API automation or batch integration traffic
- active-space data volume is still in a normal internal-tool range, not thousands of simultaneous planning records in one space

If the live deployment overrides worker count, DB pool size, or pod resources, the estimates should be adjusted.

## What The Current Runtime Tells Us

### 1. The app is built to run across multiple pods

The code is not worker-local only.

- `ENV=uat|prod` requires `SIPM_COORDINATION_BACKEND=redis`
- Redis is used for cross-worker cache invalidation and realtime refresh fanout
- that means the application is already designed to behave correctly across multiple pods, not just on one instance

This is a good sign for scale-out reliability.

### 2. Oracle is the first real capacity constraint

The default DB settings in `.env.example` are:

- `SIPM_DB_POOL_SIZE=5`
- `SIPM_DB_MAX_OVERFLOW=10`
- `SIPM_DB_POOL_TIMEOUT_SECONDS=30`

Assuming one app process per pod and three pods total, that implies:

- about `15` steady pooled Oracle connections across the cluster
- about `45` concurrent Oracle connections at burst ceiling across the cluster
- requests above that will queue, then eventually fail if they cannot get a connection within `30` seconds

If each pod runs multiple app processes, this ceiling changes, but Oracle pressure also rises proportionally.

That does not mean the app can only have `45` users. It means the first hard technical ceiling is around how many DB-active requests can be in flight at once.

### 3. Websockets are probably not the first bottleneck

The realtime defaults are:

- `SIPM_WS_MAX_CONNECTIONS_GLOBAL=400`
- `SIPM_WS_MAX_CONNECTIONS_PER_USER=8`

If the deployment is one process per pod, three pods implies a websocket ceiling of roughly:

- `~1,200` total websocket sessions cluster-wide

That is much higher than the DB-connection ceiling, so websockets are unlikely to be the first scaling limit for this application.

### 4. Some read paths benefit from short-lived caching

Several list and detail routes use the shared smart cache with short TTLs, generally in the `20-30` second range, and invalidate through the coordination layer.

That helps for:

- repeated list/detail reads
- repeated admin and reference-data requests
- keeping multi-pod reads reasonably fresh without hammering Oracle on every repeated read

### 5. The planning board is heavier than the average route

The `#/planning` experience is the surface that matters most for rollout risk.

Current frontend behavior shows:

- initial board load issues `4` parallel API calls: tasks, teams, people, and allocations
- month changes issue `2` parallel API calls
- planning routes read active-space-wide task, people, team, and allocation data directly from Oracle
- planning routes do not get as much benefit from the short-lived cache as several other read surfaces do

So if many users are simultaneously active in planning, the app will hit Oracle much harder than the rest of the product.

## Capacity Estimate By Usage Pattern

The right answer depends less on raw account count and more on how people use the app.

### Scenario A: Typical internal usage

Profile:

- users browse projects, solutions, subcomponents, dashboards, and admin views
- activity is human-paced, not machine-driven
- only a subset of users are actively clicking at the same time
- planning usage exists but is not the dominant activity for everyone

Estimate:

- `75-150` named users is a reasonable current support range
- `20-40` concurrently active users is a reasonable current operating range

This is the band I would be comfortable discussing today.

### Scenario B: Planning-heavy rollout

Profile:

- many users spend time in `#/planning`
- multiple people load boards, switch months, assign work, and refresh around the same meeting windows
- PDF report generation and planning mutations happen during the same bursts

Estimate:

- `50-100` named users is the safer current band
- `10-20` simultaneously active planning users is the safer concurrent band

This lower band exists because planning creates parallel request bursts and reads full active-space datasets.

### Scenario C: Tuned next step after measurement

If the deployment has healthy CPU and memory headroom, Oracle can support more sessions, and the pool and pod sizing are tuned with evidence, then the app can likely move into:

- `150-300` named users
- `30-60` concurrently active users overall
- `15-30` simultaneously active planning users

I would only use this band after a real load test and after confirming Oracle session limits and pod resources.

## What The App Can Realistically Take On Today

Today, I think SIPM can realistically support:

- a larger internal rollout beyond the current boss-and-team usage
- one or more additional project-management groups
- a department-scale user base
- low-hundreds total accounts, if daily concurrency stays moderate

Today, I would not market it as ready for:

- broad enterprise rollout across many departments
- heavy automation or integration-driven traffic
- large simultaneous planning workshops without prior testing
- high-confidence SLA language around latency or uptime under load

## Main Scaling Risks

### Oracle connection pressure

This is the clearest near-term limit. The default pool math is simply not in enterprise territory yet.

### Unknown pod resource sizing

Three pods help availability and scale-out, but if each pod is small on CPU or memory, real throughput can still be modest. The repo does not show the actual container resource reservations.

### Planning-board query shape

Planning reads whole sets of teams, people, tasks, and month allocations for the active space. As a single space gets larger, pressure rises with both user count and data volume.

### Limited observability

The application has readiness checks and request IDs, which is good, but the repo still does not show production-grade metrics, tracing, or performance dashboards. That makes it harder to know when the app is nearing saturation.

### No benchmark history

There is strong test coverage for correctness, but no repo-visible load-test or performance-test evidence.

## Recommended Rollout Posture

If the goal is to widen adoption soon, my recommendation is:

1. Approve a next-wave rollout into the `50-100` total user range without major architecture changes.
2. Treat `75-150` total users as a reasonable current target range, not a guaranteed hard limit.
3. Before promising anything above that, confirm:
   - actual pod CPU and memory requests and limits
   - actual Oracle session allowance and observed DB latency
   - whether the live deployment keeps the default DB pool sizes or overrides them
4. Run one focused load test centered on `#/planning`, because that is the most likely first bottleneck.
5. Add lightweight production telemetry before any broader expansion:
   - request rate
   - p95 and p99 latency
   - DB pool wait time
   - Oracle error rate
   - websocket connection count

## Final Assessment

SIPM is already beyond the size and maturity of a small throwaway internal tool. It should be able to support materially more than the current `10-15` users.

My practical assessment is:

- yes, this application can take on a broader internal audience now
- yes, it should handle low-hundreds total users if usage stays department-scale and concurrency is moderate
- no, the current evidence does not justify claiming enterprise-wide or high-concurrency capacity yet

If a single number is required for planning purposes, my recommendation is to position the current application at roughly:

- `~100` total users with confidence

and treat anything meaningfully above that as a measured tuning exercise rather than an assumption.
