# SIPM Agent API Contract

All paths are below `<SIPM_BASE_URL>/api`. Service-account calls use `Authorization: Bearer <SIPM_AGENT_TOKEN>`; scoped calls also require `X-Space-Id`. An authenticated human cookie session may call `POST /agent/delegated-session` to issue a 10-minute, session-bound delegated bearer token for review commands.

## Discovery And Reads

- `GET /agent/manifest` — truthful capabilities and safety flags.
- `GET /agent/spaces` and `/{space_id}` — accessible, cursor-paginated space discovery; no space header required.
- `GET /agent/work-items` — typed, cursor-paginated locator for program/project/solution/task.
- `GET /agent/{programs|projects|solutions|tasks}/{id}` — complete direct detail with concurrency timestamps.
- `GET /agent/work-graph` — project-boundary cursor pagination, `task_id`, and `summary|full` projection. Filters select matching parent graphs; returned parents include their full child set for the chosen projection.
- `GET /agent/audit-feed` — scoped incremental verification.
- `GET /agent/reference-data` — authoritative create/update/archive fields, enums, phases, filters, and limits.
- `GET /agent/openapi.json` — Agent-only OpenAPI paths.
- `GET /agent/people` — paginated assignable users with space role and capacity.
- `GET /agent/teams` and `/teams/{id}/members` — paginated team membership, role, and capacity.

All cursors are opaque and filter-bound. Do not edit or reuse one with changed filters.

## Patch Envelope

The server accepts at most 25 operations over `program`, `project`, `solution`, and `task`. Supported operations are `create`, `update`, and `archive`.

```json
{
  "dry_run": false,
  "reason": "Human-readable reason",
  "idempotency_key": "caller-generated-unique-key",
  "operations": []
}
```

Retrieve live field allowlists from `/agent/reference-data`. Do not infer update fields from create fields.

Update requires `id`, `if_updated_at`, and at least one material field. No-op updates are rejected. Archive requires `id` and `if_updated_at`, accepts no fields, and is soft-delete only.

## Atomic Hierarchy Creation

Create operations may define a unique `ref`. Later operations may use a typed backward reference. Missing, forward, duplicate, or type-mismatched references fail validation.

```json
{
  "dry_run": false,
  "reason": "Create one delivery hierarchy",
  "idempotency_key": "delivery-hierarchy-2026-07-15",
  "operations": [
    {"client_operation_id":"p0","op":"create","entity":"program","ref":"program","fields":{"program_name":"Delivery"}},
    {"client_operation_id":"p1","op":"create","entity":"project","ref":"project","program_ref":"program","fields":{"project_name":"Migration"}},
    {"client_operation_id":"s1","op":"create","entity":"solution","ref":"solution","project_ref":"project","fields":{"solution_name":"Execution"}},
    {"client_operation_id":"t1","op":"create","entity":"task","ref":"task","solution_ref":"solution","fields":{"task_name":"Kickoff"}}
  ]
}
```

Application is transactional. Results map `ref` and `client_operation_id` to persisted entity IDs.

## Validation And Submission

- `POST /agent/patches/validate` validates without persistence.
- `POST /agent/change-requests` stores an immutable pending proposal and diff; it does not mutate work data.
- `GET /agent/change-requests` and `/{id}` list/get only the service account's own requests.
- `POST /agent/change-requests/{id}/cancel` idempotently cancels an owned pending request.

Submitting the same idempotency key with the same immutable payload returns the existing request. A different payload under the key conflicts.

## Review

Service accounts never approve or reject. Browser-cookie review remains supported. Delegated review is separate:

- `GET /agent/change-requests/{id}/delegated-review`
- `POST /agent/change-requests/{id}/delegated-approve`
- `POST /agent/change-requests/{id}/delegated-reject`

The POST body must contain `confirm_change_request_id` equal to the path ID and `if_request_updated_at` copied from the reviewed response. The human session must still be active and have space access. Changed, terminal, replayed, or mismatched requests fail.

## Errors

Agent errors use:

```json
{"code":"STABLE_CODE","message":"safe message","request_id":"correlation-id","details":{}}
```

Handle `INVALID_CURSOR`, `STALE_ENTITY`, `NO_CHANGES`, `CHANGE_REQUEST_CHANGED`, and authorization codes explicitly. Do not retry validation or authorization failures unchanged.
