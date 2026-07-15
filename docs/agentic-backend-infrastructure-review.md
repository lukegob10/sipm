# Agentic Backend Infrastructure Review

Date: 2026-05-26

## Purpose

This review proposes backend-only changes that would make SIPM easier and safer for coding agents such as Roo, scheduled automation jobs, and external project-management skills to use. The frontend should remain unchanged. The goal is to expose better backend "piping" for agents without giving agents direct database access or bypassing SIPM auth, space isolation, validation, audit logging, cache invalidation, or live refresh behavior.

## Research Notes

The current direction in agent tooling is not to make agents scrape browser screens. It is to expose stable machine contracts:

- Model Context Protocol (MCP) positions tools, resources, and prompts as server-exposed capabilities for AI applications, with JSON-RPC as the base message protocol and a modular separation between resources, prompts, tools, lifecycle, logging, and authorization. See [MCP overview](https://modelcontextprotocol.io/specification/2025-11-25/basic) and [MCP introduction](https://modelcontextprotocol.io/docs/getting-started/intro).
- MCP's newer HTTP authorization guidance expects bearer tokens in the `Authorization` header and explicitly avoids tokens in URL query strings. See [MCP authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization).
- FastAPI already generates OpenAPI, but agent/tool usability depends heavily on clear operation IDs, response models, summaries, and extensions. FastAPI supports explicit `operation_id` values and `openapi_extra` metadata. See [FastAPI path operation advanced configuration](https://fastapi.tiangolo.com/advanced/path-operation-advanced-configuration/).
- OpenAPI tooling treats `operationId` as the stable identifier for generated clients and tool wrappers, so uniqueness and naming quality matter. See [Redocly operation-operationId-unique](https://redocly.com/docs/cli/rules/oas/operation-operationId-unique).
- FastAPI's client-generation guidance shows how tags and operation IDs flow into generated client methods, which is also relevant to agent-generated API clients. See [FastAPI generate clients](https://fastapi.tiangolo.com/advanced/generate-clients/).

The practical implication for SIPM: do not start with a separate agent runtime that owns business logic. Start with a small, stable agent API surface and optional MCP/OpenAPI wrappers that call the same backend services as the existing UI routes.

## Current Backend Strengths

SIPM already has several useful pieces for agent workflows:

- FastAPI app with OpenAPI available under the configured context path.
- Service-account API tokens through `Authorization: Bearer <token>`.
- Active-space enforcement via `X-Space-Id` and `current_space`.
- Route-level role dependencies such as `require_space_role("member")` and `require_global_admin`.
- Request correlation through `X-Request-ID`.
- Compact JSON request logs with user, space, auth method, status, and duration.
- Audit logging through `ChangeLog` and `safe_log_changes`.
- Cache invalidation and realtime refresh publishing through mutation helpers.
- Existing CSV import/export for projects, solutions, tasks, and users.
- Existing WebSocket refresh channel for browser sessions.
- Existing `docs/agent-data-exchange-api-options.md`, which already recommends JSON import/export as the next agent interchange layer.

These are the right foundations. The missing piece is an explicit agent-facing contract that is more discoverable, more idempotent, more batch-oriented, and less UI-shaped.

## Main Recommendation

Add an "Agent API" as a narrow backend layer under the existing FastAPI app:

```text
/project-manager/api/agent/*
```

This should be a facade over existing route/service behavior, not a separate business system. It should reuse:

- `require_user`
- `current_space`
- `require_space_role`
- service-account bearer token auth
- SQLAlchemy models and services
- audit logging
- mutation publication and cache invalidation
- request IDs

The Agent API should be optimized for automation tasks that need to inspect work, plan changes, validate changes, and apply changes predictably.

## Agent Boundary

SIPM should not own or track the lifecycle of the external agent. Roo, scheduled rules, MCP servers, and other automation runtimes live outside this project. SIPM does not need to know that an agent is cleaning data, running a scheduled workflow, or coordinating a larger project-management task.

The backend should only know:

- an authenticated service account or user made an API request
- the request targeted a specific space
- the request had a request ID
- the request read or mutated SIPM domain data
- successful mutations produced normal audit rows, cache invalidation, and realtime refresh events

Agent prompts, rules, schedules, retries, run history, model metadata, and workflow state should remain outside SIPM. External automation can keep its own run logs and pass `X-Request-ID` values for correlation when it calls SIPM.

## Agent API Design Principles

1. Keep agents behind normal API auth.
2. Require `X-Space-Id` for agent calls unless the service account has exactly one accessible space.
3. Prefer stable IDs and SOEIDs over display names.
4. Make read endpoints filtered, paginated, and projection-friendly.
5. Make write endpoints idempotent where possible.
6. Make `dry_run` a first-class option on every bulk write.
7. Return object-level validation errors instead of a single failed batch response.
8. Return mutation summaries that agents can reason about.
9. Require optimistic concurrency for broad updates.
10. Publish normal cache invalidation and realtime refresh events after successful writes.
11. Include machine-readable error codes.
12. Keep frontend-specific response shapes out of the Agent API.
13. Do not store external agent run state in SIPM.

## Proposed Endpoint Set

### 1. Agent Manifest

```http
GET /api/agent/manifest
```

Purpose: tell a coding agent what this backend supports without forcing it to infer workflows from the full OpenAPI document.

Response shape:

```json
{
  "name": "SIPM Agent API",
  "version": "0.1",
  "context_path": "/project-manager",
  "requires_space_id": true,
  "auth": {
    "type": "bearer",
    "service_account_required": true
  },
  "capabilities": [
    "read_work_graph",
    "validate_patch",
    "apply_patch",
    "export_json",
    "read_audit",
    "read_open_tasks"
  ],
  "entities": ["projects", "solutions", "tasks", "users", "teams"]
}
```

Why it helps: agent skills can bootstrap from one small endpoint instead of loading full app docs or probing routes.

### 2. Work Graph Read Model

```http
GET /api/agent/work-graph
```

Query parameters:

- `project_id`
- `solution_id`
- `owner_user_soeid`
- `assignee_user_soeid`
- `status`
- `updated_since`
- `include_closed`
- `include_audit_summary`
- `limit`
- `cursor`
- `fields`

Purpose: return a compact project -> solution -> task graph for analysis and reasoning.

This should not be the same shape as the browser state. It should be an agent-safe read model with stable IDs, names, statuses, dates, user SOEIDs, dependencies, and update timestamps.

Example:

```json
{
  "space_id": "space-123",
  "cursor": null,
  "records": [
    {
      "project_id": "p1",
      "project_name": "Example",
      "status": "in_progress",
      "updated_at": "2026-05-26T13:00:00Z",
      "solutions": [
        {
          "solution_id": "s1",
          "solution_name": "Example solution",
          "tasks": []
        }
      ]
    }
  ]
}
```

Why it helps: most agent workflows start by understanding the current work breakdown. Today an agent would need to chain several UI-oriented endpoints and reconstruct relationships.

### 3. JSON Export And Import

Build on `docs/agent-data-exchange-api-options.md` and add JSON import/export for entities already supported by CSV:

```http
GET  /api/agent/projects/export
POST /api/agent/projects/import
GET  /api/agent/solutions/export
POST /api/agent/solutions/import
GET  /api/agent/tasks/export
POST /api/agent/tasks/import
GET  /api/agent/users/export
POST /api/agent/users/import
```

Use wrapper objects instead of raw arrays:

```json
{
  "schema_version": "agent-projects.v1",
  "space_id": "space-123",
  "exported_at": "2026-05-26T13:00:00Z",
  "records": []
}
```

Import response:

```json
{
  "dry_run": true,
  "created": 0,
  "updated": 4,
  "skipped": 2,
  "failed": 1,
  "errors": [
    {
      "index": 3,
      "entity": "project",
      "code": "STATUS_INVALID",
      "message": "status must be one of: not_started, in_progress, complete"
    }
  ]
}
```

Why it helps: agents can diff, validate, and round-trip structured data without CSV ambiguity.

### 4. Patch Plan Validation

```http
POST /api/agent/patches/validate
POST /api/agent/patches/apply
```

Purpose: allow scheduled rules or Roo-style coding agents to submit a proposed set of changes as a patch plan.

Patch plan shape:

```json
{
  "idempotency_key": "scheduled-rule-2026-05-26T13:00:00Z",
  "reason": "Move stale in-progress work to at-risk status",
  "dry_run": true,
  "operations": [
    {
      "op": "update",
      "entity": "task",
      "id": "task-123",
      "if_updated_at": "2026-05-25T10:15:00Z",
      "fields": {
        "status": "at_risk"
      }
    }
  ]
}
```

Validation should check:

- auth and space access
- role permissions
- entity existence
- field allowlist
- enum values
- relationship constraints
- optimistic concurrency
- no-op operations
- expected mutation count limits

Apply should:

- reuse normal service logic
- commit atomically where practical
- write audit rows with the patch reason
- invalidate cache scopes
- publish realtime refresh
- return per-operation results

Why it helps: scheduled automation can be reviewed as a plan before it mutates production data.

### 5. Agent-Readable Audit Feed

```http
GET /api/agent/audit-feed
```

Query parameters:

- `since`
- `until`
- `entity_type`
- `entity_id`
- `user_id`
- `request_id`
- `limit`
- `cursor`

Purpose: expose an agent-friendly audit stream for change awareness and incremental sync.

This can wrap the existing `/api/audit` behavior but should support cursor pagination and service-account access rules.

Why it helps: agents can avoid re-exporting all data on every run.

### 6. OpenAPI Snapshot For Agents

```http
GET /api/agent/openapi.json
```

Purpose: provide a filtered OpenAPI document containing only the stable agent endpoints.

Recommendations:

- stable explicit `operation_id` for every Agent API route
- concise `summary` and `description`
- Pydantic request and response models for every route
- examples for patch plans and import errors
- `x-agent-safe: true`
- `x-sipm-space-scoped: true`
- `x-sipm-dry-run-supported: true` where applicable

Why it helps: Roo, MCP servers, and custom skills can consume a small contract without dragging in every browser-supporting endpoint.

## Optional MCP Layer

Do not make MCP the first backend change. Make the Agent API first, then optionally expose an MCP server that maps MCP tools/resources to the Agent API.

Good MCP resources:

- `sipm://manifest`
- `sipm://spaces/{space_id}/work-graph`
- `sipm://spaces/{space_id}/audit-feed`
- `sipm://schemas/agent-patch-plan`

Good MCP tools:

- `sipm_get_work_graph`
- `sipm_validate_patch_plan`
- `sipm_apply_patch_plan`
- `sipm_export_projects_json`
- `sipm_import_projects_json`
- `sipm_get_audit_feed`

Important security note: MCP should not become a privileged side door. It should authenticate to SIPM with a service-account token or OAuth-backed bearer token and call the same Agent API endpoints. Avoid local command execution in the SIPM backend. Keep arbitrary tool execution outside SIPM.

## Backend Changes Needed

### Route Structure

Add:

```text
src/main/backend/app/routes/agent/
  __init__.py
  manifest.py
  work_graph.py
  exchange.py
  patches.py
  audit_feed.py
  openapi.py
```

Then include `agent_router` from `backend/app/routes/__init__.py` under `/agent`.

### Schemas

Add:

```text
src/main/backend/app/schemas/agent.py
```

Define Pydantic models for:

- manifest
- work graph response
- JSON export envelopes
- import result
- patch plan
- patch operation
- patch validation result
- audit feed page

Do not return ad hoc dictionaries from these routes except for the first quick prototype.

### Services

Add:

```text
src/main/backend/app/services/agent_work_graph.py
src/main/backend/app/services/agent_patch_plan.py
```

Keep route functions thin. Put query composition, validation, and patch execution in services.

### Database

The Agent API should not require a new database table for external agent runs. The first backend phases can avoid schema changes if they expose manifest, work graph, JSON export/import, patch validation, and patch apply over existing entities.

If idempotency keys need durable deduplication later, prefer a small generic API idempotency table keyed by service account, space, endpoint, and idempotency key. Do not model it as an agent-run table.

### Audit

For agent writes, audit entries should include:

- normal entity type and entity ID
- normal changed fields
- acting service-account user ID
- request ID
- space ID
- patch reason when available

If the current `ChangeLog` model cannot store a patch reason directly, add it to the change JSON when practical or add a narrowly scoped column in a later schema revision. Do not add agent-run metadata to SIPM audit records.

### Auth And Permissions

Use service-account API tokens for v1. Recommended additions:

- Add optional token scopes before broad agent writes are enabled.
- Example scopes: `agent:read`, `agent:write`, `agent:admin`.
- Deny Agent API access to normal browser cookie sessions unless explicitly allowed.
- Require `X-Space-Id` for service-account calls to avoid accidental default-space mutation.
- Keep tokens out of query strings.

### Rate Limits And Blast Radius

Add conservative guardrails:

- max patch operations per request
- max import records per request
- max export page size
- required `dry_run` before apply for high-risk operation types
- idempotency key required for apply
- clear response when an operation is skipped as duplicate

## Suggested Phasing

### Phase 1: Agent-Readable Backend

Implement:

- `GET /api/agent/manifest`
- `GET /api/agent/work-graph`
- `GET /api/agent/openapi.json`
- explicit operation IDs and response models for new routes

No database migration required.

Value: agents can understand SIPM and read scoped work data safely.

### Phase 2: Agent Data Exchange

Implement:

- JSON export/import for projects, solutions, and tasks
- `dry_run`
- per-record errors
- stable IDs and SOEIDs
- filtered exports

No database migration required if reuse existing entities.

Value: agents can do structured bulk edits without CSV fragility.

### Phase 3: Patch Plans

Implement:

- `POST /api/agent/patches/validate`
- `POST /api/agent/patches/apply`
- idempotency keys
- optimistic concurrency
- per-operation results

No database migration required for a first version, although storing idempotency keys durably is better.

Value: scheduled rules can propose and apply controlled updates.

### Phase 4: MCP Adapter

Implement an external or internal MCP server that maps resources/tools to the Agent API.

Value: Roo or other agent clients can use SIPM through a standard tool interface while SIPM remains protected by its normal backend.

## What Not To Do

- Do not give agents direct Oracle access.
- Do not let an MCP server mutate database rows outside SIPM services.
- Do not build agent workflows against frontend DOM or browser-only state.
- Do not accept bearer tokens in query strings.
- Do not add a second backend with duplicate project/solution/task business rules.
- Do not make broad agent writes without `dry_run`, idempotency, and audit records.
- Do not expose all existing UI endpoints as "agent tools" without curating them.
- Do not store Roo, scheduled-rule, model, prompt, retry, or agent-run lifecycle state in SIPM.

## Acceptance Criteria For An Agent-Friendly Backend

SIPM is agent-friendly when a coding agent can:

1. Discover supported capabilities from a manifest.
2. Authenticate as a service account.
3. Select a space explicitly.
4. Read the work graph in one or two calls.
5. Export a filtered JSON dataset with stable IDs.
6. Validate proposed changes without mutating data.
7. Apply an idempotent patch plan.
8. Receive per-record or per-operation errors.
9. Correlate its call with `X-Request-ID`.
10. See its changes in audit history.
11. Trigger normal cache invalidation and browser refresh behavior.
12. Avoid loading the frontend or reverse-engineering browser state.

## First Implementation Slice

The smallest useful backend-only slice is:

```text
GET  /api/agent/manifest
GET  /api/agent/work-graph
POST /api/agent/patches/validate
```

This provides discovery, read context, and safe write preparation without committing to MCP yet. After that, add `POST /api/agent/patches/apply` with idempotency and audit behavior.

## Recommended Final Shape

Use SIPM as the source-of-truth application backend. Put agent-specific rules, prompts, schedules, run tracking, and skills outside SIPM, but require those external agents to enter through a curated SIPM Agent API. The Agent API should be a stable, documented, service-account-friendly facade over existing backend services. MCP can be added as an adapter later, but the core product improvement is the backend contract: manifest, work graph, JSON exchange, patch validation, patch apply, and audit feed.
