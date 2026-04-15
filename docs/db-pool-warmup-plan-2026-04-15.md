# SIPM Dev DB Pool Warm-Up Plan

## Problem

In the current dev phase, SIPM has a very small and bursty user base. That means the app often sits idle long enough for the next request to pay a reconnect cost. For a production-scale workload that is acceptable; for 3-5 intermittent dev users it makes the app feel slow.

## What The Code Does Today

- `src/main/backend/main.py` calls `init_db()` during app lifespan startup.
- `src/main/backend/app/db/db.py` only creates the SQLAlchemy engine/session lazily inside `_ensure_session_local()`.
- `init_db(create_schema=False)` is effectively a no-op, so normal startup does **not** open a real DB connection.
- The first real DB touch happens later through `check_db_connection()` or `get_session()`.
- `GET /health/ready` already calls `check_db_connection()`, so that endpoint can warm one pooled connection.
- Current defaults from `.env.example` are:
  - `SIPM_DB_POOL_SIZE=5`
  - `SIPM_DB_MAX_OVERFLOW=10`
  - `SIPM_DB_POOL_TIMEOUT_SECONDS=30`
  - `SIPM_DB_POOL_RECYCLE_SECONDS=1800`
  - `SIPM_DB_POOL_PRE_PING=true`

## Important Clarification

`pool_size=5` does **not** mean SQLAlchemy pre-creates five connections at startup. SQLAlchemy `QueuePool` opens connections only on first use, so the current app is still effectively cold until something calls `engine.connect()` or opens a session.

That means there are two likely sources of the latency you are seeing:

1. The pool is never explicitly prewarmed, so cold start and post-idle access both pay a connect cost.
2. `SIPM_DB_POOL_RECYCLE_SECONDS=1800` forces replacement of connections older than 30 minutes on checkout, so sparse dev usage may be reconnecting even when the database itself would have allowed the connection to live longer.

## Options

### 1. Zero-code stopgap: use readiness as a prewarm hook

Use `GET /health/ready` once immediately after app startup. Because it already runs `check_db_connection()`, it will create and validate one pooled connection.

For dev or preprod only, an external probe could also hit `/health/ready` every few minutes to keep one connection warm.

Pros:

- No code change.
- Fully reversible.
- Uses code that already exists.

Cons:

- Ties warm-up behavior to an ops probe.
- Helps only as much as the probe cadence helps.
- Not ideal as the long-term pattern.

### 2. Env-only experiment: stop forcing 30-minute recycle in dev

Change only the dev environment:

```env
SIPM_DB_POOL_RECYCLE_SECONDS=-1
```

or, if you want a softer test:

```env
SIPM_DB_POOL_RECYCLE_SECONDS=7200
```

Rationale:

- `pool_pre_ping=true` already protects correctness when the DB has closed a stale connection.
- If the current 1800-second recycle is the main cause of the reconnects, raising or disabling it in dev should reduce first-hit latency with no code change.

Pros:

- Fastest useful experiment.
- Reversible by env only.
- Keeps the existing pool design intact.

Cons:

- If the database or network is closing idle sessions sooner anyway, this will not fully eliminate reconnect latency.
- It does not prewarm on startup by itself.

### 3. Recommended minimal code change: opt-in startup prewarm

Add an explicit warm-up helper that opens one connection and runs `SELECT 1`, then returns it to the pool. Call it during lifespan startup behind a new env flag such as:

```env
SIPM_DB_PREWARM_ON_STARTUP=true
SIPM_DB_PREWARM_CONNECTIONS=1
```

Implementation shape:

- Add `warm_db_pool(connection_count: int = 1)` in `src/main/backend/app/db/db.py`.
- In `src/main/backend/main.py`, call it after startup validation when startup is enabled.
- Default the feature to `false` so prod behavior stays unchanged unless explicitly enabled.

Pros:

- Fixes cold start deterministically.
- Small, isolated change.
- Easy to remove after full rollout.

Cons:

- Does not help after long idle gaps unless the connection is still alive.

### 4. Small extension if needed: dev-only keep-warm task

If startup prewarm is not enough, add a background task that runs `check_db_connection()` on a fixed interval, for example:

```env
SIPM_DB_KEEPWARM_INTERVAL_SECONDS=300
```

Recommended behavior:

- Disabled by default.
- Dev/preprod use only.
- Single connection target; do not try to keep a large pool hot.

Pros:

- Best fit for a tiny, intermittent user base.
- Keeps the app responsive after long idle windows.
- Still easy to disable later.

Cons:

- Adds ongoing DB traffic, though very small.
- Slightly more code than startup-only prewarm.

### 5. Optional pool hygiene for low-traffic mode: support `pool_use_lifo`

If we want one extra tuning knob, add support for:

```env
SIPM_DB_POOL_USE_LIFO=true
```

Why it matters:

- For a low-traffic app, LIFO tends to reuse the hottest connection first instead of round-robining across older pooled connections.
- SQLAlchemy explicitly recommends `pool_use_lifo=True` together with `pool_pre_ping=True` when server-side idle timeout behavior matters.

Pros:

- Good fit for sparse usage.
- Low-risk addition.

Cons:

- Requires a small code change and new test coverage.
- Only helps if more than one connection has accumulated in the pool.

## Q&A: Close Then Reopen Right Away

### Would an "idle max" that closes the newest connection and immediately reopens it work?

Technically yes, but it is not the best design for this problem.

Why:

- Closing and immediately reopening does **not** preserve the same database connection. It creates connection churn on purpose.
- You still end up with an open connection after the reopen, so it does not really reduce steady-state connection count.
- It adds needless reconnect overhead and log noise.
- Across multiple pods or worker processes, it multiplies that churn.

If the real goal is:

- keep one connection warm
- avoid a long-idle disconnect
- avoid paying reconnect cost on the next user request

then the better pattern is a **keep-warm heartbeat**, not forced close-and-reopen.

Recommended shape:

1. Check out one connection.
2. Run a trivial query such as `SELECT 1`.
3. Return it to the pool.
4. Repeat on an interval shorter than the database idle timeout.

That resets the server-side idle timer without intentionally throwing the connection away.

### Does SQLAlchemy already support this better than forced reopen?

Yes. The current app already has the pieces needed for the useful version:

- `pool_pre_ping=true` validates a connection when it is checked out.
- `check_db_connection()` already performs a simple `SELECT 1`.
- A small keep-warm loop can reuse that function.

Two important details:

- `pool_pre_ping` does **not** keep a connection alive by itself. It only checks liveness on checkout.
- `pool_recycle` also does **not** refresh connections in the background. SQLAlchemy recycles on checkout after the configured age threshold is exceeded.

So if we want one warm connection available during quiet periods, we need either:

- a periodic checkout/query/return loop, or
- an external probe that does the same thing through `/health/ready`.

### If we want to touch the same warm connection repeatedly, how do we do that?

Two levers help:

1. Use `pool_use_lifo=true`
2. Keep the dev pool small, ideally `pool_size=1`

Why this matters:

- FIFO tends to round-robin through the pool, which can keep several connections warm.
- LIFO tends to reuse the most recently returned connection first.
- With `pool_size=1`, the app naturally keeps a single hot slot instead of several.

For this repo's current dev stage, a strong low-risk profile is:

```env
SIPM_DB_POOL_SIZE=1
SIPM_DB_MAX_OVERFLOW=0
SIPM_DB_POOL_RECYCLE_SECONDS=-1
SIPM_DB_POOL_PRE_PING=true
# if implemented:
SIPM_DB_POOL_USE_LIFO=true
SIPM_DB_KEEPWARM_INTERVAL_SECONDS=300
```

This gives each app process one intentional warm connection and avoids holding a larger idle pool open.

## Multi-Pod Behavior

Yes: multiple pods multiply connections.

More precisely, the multiplication is:

```text
total possible connections ~= pod_count * worker_processes_per_pod * (pool_size + max_overflow)
```

Important clarification:

- The SQLAlchemy engine and its pool live in process memory.
- Each pod has its own process space.
- If a pod runs multiple worker processes, each worker gets its own engine and its own pool.

So a dev-friendly configuration should assume multiplication across both:

- pod replicas
- worker count inside each pod

Examples:

- `3` pods, `1` worker each, `pool_size=1`, `max_overflow=0` -> about `3` persistent pooled connections max
- `3` pods, `2` workers each, `pool_size=1`, `max_overflow=0` -> about `6` persistent pooled connections max
- `3` pods, `2` workers each, `pool_size=5`, `max_overflow=10` -> as many as `90` total connections under burst if every pool reaches overflow

That is why a tiny dev pool is the safest shape if we add keep-warm behavior.

## Another Interesting Fix

The most interesting low-change alternative is not forced reopen. It is a **single-hot-connection dev profile**:

- reduce `SIPM_DB_POOL_SIZE` from `5` to `1`
- reduce `SIPM_DB_MAX_OVERFLOW` from `10` to `0` or `1`
- disable forced 30-minute recycle in dev with `SIPM_DB_POOL_RECYCLE_SECONDS=-1`
- keep `SIPM_DB_POOL_PRE_PING=true`
- add `pool_use_lifo` if we want deterministic reuse of the hottest connection
- optionally run a keep-warm ping every 5 minutes

Why this is attractive:

- It matches the current user volume.
- It minimizes the per-pod connection footprint.
- It keeps the change reversible.
- It avoids building a custom connection churn mechanism that we will later delete.

## Revised Recommendation

If the goal is "always have one warm connection ready" with minimal change, I would now narrow the recommendation to this:

1. Change the dev env to:
   - `SIPM_DB_POOL_SIZE=1`
   - `SIPM_DB_MAX_OVERFLOW=0`
   - `SIPM_DB_POOL_RECYCLE_SECONDS=-1`
2. Use `/health/ready` as the immediate no-code warm-up step after startup.
3. If that is still not enough, add an opt-in keep-warm loop that calls `check_db_connection()` every 300 seconds.
4. If we implement one extra pool knob, make it `pool_use_lifo`, not forced close-and-reopen.

## Recommended Path

1. Run the env-only experiment first in dev:
   - `SIPM_DB_POOL_SIZE=1`
   - `SIPM_DB_MAX_OVERFLOW=0`
   - `SIPM_DB_POOL_RECYCLE_SECONDS=-1`
   - Hit `/health/ready` once after startup
2. Measure first-request latency after 5, 30, and 60+ minutes idle.
3. If idle latency is still visible, implement the smallest permanent fix:
   - opt-in `SIPM_DB_PREWARM_ON_STARTUP=true`
   - opt-in `SIPM_DB_KEEPWARM_INTERVAL_SECONDS=300`
4. If we still see avoidable churn with more than one pooled connection, add `SIPM_DB_POOL_USE_LIFO=true`.

## What I Would Actually Do First

For the current repo and rollout stage, the most pragmatic path is:

- Do **not** redesign pooling.
- Do **not** disable pooling with `NullPool` because that would force a reconnect on every request.
- First try the dev-only env change to stop forced 30-minute recycle.
- If that is not enough, add a one-connection startup prewarm and a dev-only keep-warm interval behind env flags that default to off.

That gives you a reversible fix with minimal blast radius and a clean rollback once real traffic patterns justify the current lazy behavior again.

## Validation

Success criteria for the change:

- Cold boot first authenticated request is noticeably faster.
- First request after 30-60 minutes idle is noticeably faster.
- No change to prod unless the new env flags are explicitly enabled.
- No increase in DB session usage beyond one intentionally warmed connection in dev.

## Sources

- SQLAlchemy engine/pool behavior: https://docs.sqlalchemy.org/en/20/core/engines.html
- SQLAlchemy connections and pool checkout behavior: https://docs.sqlalchemy.org/en/20/core/connections.html
- SQLAlchemy pooling, `pool_pre_ping`, and `pool_use_lifo`: https://docs.sqlalchemy.org/en/21/core/pooling.html
