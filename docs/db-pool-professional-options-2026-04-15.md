# SIPM DB Pool Professional Options

## Goal

Pick the most professional way to avoid cold or post-idle database latency in a low-traffic dev deployment, without creating a messy custom pool lifecycle that will be hard to remove later.

## Option 1: Small Bounded App Pool With Startup Prewarm And Keep-Warm

### Summary

Keep the current SQLAlchemy pool model, but make it intentionally small and explicit:

```env
SIPM_DB_POOL_SIZE=1
SIPM_DB_MAX_OVERFLOW=0
SIPM_DB_POOL_RECYCLE_SECONDS=-1
SIPM_DB_POOL_PRE_PING=true
```

Then add two opt-in app behaviors:

- startup prewarm: open one connection and run `SELECT 1`
- keep-warm heartbeat: every 300 seconds, run `check_db_connection()`

If we add one extra pool tuning knob, also support:

```env
SIPM_DB_POOL_USE_LIFO=true
```

### Why This Is Professional

- Explicitly bounded connection footprint.
- Predictable behavior across low traffic periods.
- Feature-flagged and reversible.
- Minimal code surface and easy to delete later.
- Keeps control in the app instead of relying on external probes for correctness.

### Trade-Offs

- Each pod and worker process will hold its own warm connection.
- Adds a small amount of periodic DB traffic.
- Still uses per-process local pools, so it does not solve cross-pod scaling by itself.

### Best Fit

Best option for **this repo right now**.

## Option 2: Small Bounded App Pool With Startup Prewarm Only

### Summary

Use the same small dev pool profile:

```env
SIPM_DB_POOL_SIZE=1
SIPM_DB_MAX_OVERFLOW=0
SIPM_DB_POOL_RECYCLE_SECONDS=-1
SIPM_DB_POOL_PRE_PING=true
```

But only prewarm once at application startup. Do not run a background heartbeat.

### Why This Is Professional

- Cleaner than a custom close-and-reopen cycle.
- Very small implementation.
- Lower steady-state DB activity than a keep-warm loop.
- Good if the DB idle timeout is long enough that post-idle reconnects are rare.

### Trade-Offs

- Fixes cold boot but not necessarily long idle periods.
- First request after a long quiet window may still reconnect.
- Less consistent user experience than Option 1.

### Best Fit

Best if you want the **smallest code change** and can tolerate some post-idle latency.

## Option 3: Centralize Pooling At The Oracle Layer With DRCP

### Summary

Use Oracle Database Resident Connection Pooling so many app processes and pods can share a database-side pool more efficiently. Keep a small local app pool on top if needed.

### Why This Is Professional

- Strongest enterprise pattern once replicas and worker counts grow.
- Better fit for multi-process and multi-pod topologies.
- Reduces the penalty of every process owning an independent large local pool.

### Trade-Offs

- Not a minimal app-only change.
- Requires DBA/platform support and rollout coordination.
- Must be validated against the current `TAConnection` integration and Oracle driver mode.
- More operational complexity than the app-level fixes above.

### Best Fit

Best as the **scale-up path**, not the first dev-phase fix.

## Recommendation

### Recommended Now

Choose **Option 1**.

Why:

- It is the best balance of professionalism, predictability, and low implementation risk.
- It directly addresses the actual problem: tiny user base, bursty traffic, and post-idle reconnect latency.
- It keeps the connection footprint intentionally small, which matters if multiple pods exist.

### Recommended If You Want The Simplest First Step

Choose **Option 2**.

Use it if you want to prove that a tiny pool plus one startup warm-up is enough before adding a periodic heartbeat.

### Recommended Later If Replica Count Grows

Investigate **Option 3**.

That becomes more attractive once local per-process pools start multiplying across pods and workers in a way that the database team cares about.

## Decision Table

| Option | Professionalism | Change Size | Idle Latency Protection | Multi-Pod Efficiency | Best Use |
| --- | --- | --- | --- | --- | --- |
| 1. Small pool + prewarm + keep-warm | High | Small | High | Medium | Best current choice |
| 2. Small pool + prewarm only | High | Very small | Medium | Medium | Best minimal step |
| 3. Oracle DRCP | Very high | Medium to large | High | High | Best future scale path |

## Sources

- SQLAlchemy pooling and `pool_use_lifo`: https://docs.sqlalchemy.org/en/21/core/pooling.html
- SQLAlchemy engine configuration: https://docs.sqlalchemy.org/en/20/core/engines.html
- python-oracledb connection handling and DRCP: https://python-oracledb.readthedocs.io/en/latest/user_guide/connection_handling.html
