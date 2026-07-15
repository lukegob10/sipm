# SIPM Agent API Full-Scale Workflow Roadmap

Date: 2026-07-14

## Executive Summary

SIPM is moving toward an interaction model in which agents, integrations, and conversational interfaces are the primary way users work with the application. The browser UI remains useful for visualization and administration, but the Agent API must become a complete, stable, scalable product surface rather than a small automation add-on.

The target is an agent workflow that can discover its capabilities, select a space, find and inspect work, propose changes, retrieve and monitor those proposals, obtain human approval when required, verify the resulting state, and recover from conflicts without reverse-engineering the browser API.

The current implementation has a strong starting point:

- Service-account bearer authentication and strict space scoping.
- Agent manifest and work graph.
- Program, project, solution, and task create/update proposals.
- Dry-run validation and optimistic concurrency.
- Idempotency keys.
- Human approval, audit logging, cache invalidation, and realtime publication.
- Program creation through an approval-gated `program:create` operation.

The main gap is workflow completeness. An agent can submit a change request, but it cannot retrieve or monitor that request with its service-account credentials. The read graph also exposes fewer fields than the write API accepts, large collections do not have cursor pagination, and the current approval endpoints require a browser-authenticated user.

This roadmap closes those gaps in phases. The default rule is to avoid database changes. Any database change must be proposed separately with its purpose, SQL, migration and rollback plan, compatibility impact, test plan, and evidence that an application-only solution is insufficient.

## Implementation Status — July 15, 2026

- Phases 0–5 are implemented and integration-tested.
- Phase 6 people, team, role, membership, and capacity reads are implemented with cursor pagination and space isolation.
- Unrestricted document upload/removal is intentionally not exposed; it still requires the dedicated content-type, malware, quota, storage, and sensitive-data security design described in Phase 6.
- Comments and durable notifications are not currently independent SIPM product models, so the Agent API does not invent them. Change-request polling and the audit feed cover the current workflow.
- Phase 7 remains unimplemented by design. Repeatable local benchmarks show bounded query counts and do not justify an index or schema proposal. Idempotency uniqueness under true concurrent writers remains the strongest optional future database-hardening candidate.
- No database schema, canonical SQL, or migration file was changed for this roadmap implementation.

## Product Outcome

The completed Agent API should support this end-to-end workflow:

1. Discover supported capabilities and contract versions.
2. Authenticate a service account or a human-delegated agent session.
3. Discover and select an accessible space.
4. Search or retrieve complete work state using stable IDs.
5. Validate a proposed, bounded set of mutations.
6. Submit an immutable change request for approval.
7. Retrieve and monitor the request through a terminal state.
8. Let a real human approve or reject through the UI or an explicitly delegated agent interaction.
9. Return created entity IDs and final per-operation results.
10. Verify the resulting entities and audit history.
11. Recover from stale data, rejection, cancellation, partial client failure, or retry without duplicating work.

No step should require loading frontend JavaScript, scraping UI state, guessing enum values, or making an unbounded collection request.

## Guiding Principles

### The Agent API Is A Product Contract

- Agent endpoints use stable request and response schemas.
- Every route has an explicit and stable `operation_id`.
- The manifest advertises only capabilities that actually work for the authenticated principal.
- Browser-specific payloads and frontend state do not leak into the Agent API.
- Normal business rules remain shared with the browser routes; the Agent API must not become a second implementation of the domain.
- Breaking changes require a version transition, compatibility window, and migration guidance.

### Human Approval Remains A Real Security Boundary

- Service accounts may propose changes but must not approve their own proposals.
- A human may review through the UI or through a human-delegated identity with explicit confirmation.
- Replacing cookie-only approval must not mean weakening approval to any bearer token.
- Approval authorization must be based on the acting human's space role and future permission model.
- Every approval, rejection, cancellation, and failed apply remains attributable in the audit history.

### Submitted Requests Are Immutable

A submitted request represents exactly what a reviewer was asked to evaluate. Its operations, reason, and diff should not be edited in place.

To change a pending proposal:

- Cancel the old request.
- Submit a new request with a new idempotency key.
- Optionally link it as a replacement when durable replacement linkage is approved.

This preserves review integrity and makes retries, audit, and incident analysis understandable.

### Scale Is A Contract Requirement

The design must assume:

- Many users per deployment.
- Many spaces per user or service account.
- Thousands of projects per space.
- Tens or hundreds of thousands of solutions and tasks per space.
- Many concurrent agents polling and proposing changes.
- Long-running audit and change-request histories.

Consequently:

- Every collection is bounded.
- Cursor pagination is preferred over offset pagination.
- Responses indicate whether more data is available.
- Filtering and sorting happen in the database, not after loading full collections.
- Detail endpoints exist so callers do not retrieve an entire graph to inspect one entity.
- Large counts are optional because exact `COUNT(*)` calls can become expensive.
- Query count and response-size budgets are part of endpoint acceptance criteria.
- Space isolation is enforced in every query, including lookup, pagination, audit, and idempotency paths.

## Database Change Policy

### Default Rule

Implement the roadmap without changing the database whenever correctness and acceptable measured performance can be achieved with the existing schema.

Examples that should not require a schema change:

- Service-account list and detail access to its own change requests.
- Correcting the manifest.
- Adding detail endpoints.
- Returning complete read fields.
- Adding request and graph filters.
- Cursor encoding and decoding.
- Adding filtered OpenAPI and reference-data endpoints.
- Agent-readable audit access over the existing change log.
- Supporting a `cancelled` status in the existing string status column.
- In-transaction client references for newly created hierarchy items.
- Approval through an existing human user identity, if the existing authentication model can prove that identity safely.
- Soft archive operations using existing `deleted_at` columns.

### Database Change Gate

No migration may be implemented as an incidental part of an endpoint phase. A proposed database change requires a short design section or separate design document containing:

1. The concrete correctness or measured performance problem.
2. Why the existing schema cannot solve it safely.
3. The proposed model and SQL changes.
4. Backfill requirements.
5. Forward migration and rollback procedures.
6. Compatibility with running application versions.
7. Locking and deployment risk for Oracle and test databases.
8. Expected query-plan or integrity improvement.
9. Tests and production verification.
10. Explicit approval before implementation.

### Known Optional Database Changes

These changes may become valuable, but they are not automatically authorized by this roadmap:

| Proposed change | Why it may be needed | Application-only first step | Approval evidence |
|---|---|---|---|
| Unique constraint on `(space_id, proposed_by_user_id, idempotency_key)` | Prevent concurrent duplicate submissions | Keep the existing lookup and add concurrency tests | Demonstrate duplicate creation under concurrent requests or accept the constraint as correctness hardening |
| Composite indexes for graph cursors | Keep ordered space-scoped scans fast at high volume | Add keyset pagination and measure representative data | Query plans and latency exceed the phase performance budget |
| Composite audit cursor index such as `(space_id, created_at, change_id)` | Efficient incremental audit feed | Use existing change-log indexes and benchmark | Audit query plan or p95 latency is unacceptable |
| `supersedes_change_request_id` | Durable replacement lineage | Cancel old request and place the old ID in structured client metadata or reason | Product requires server-queryable replacement chains |
| `expires_at` on change requests | Automatic expiration policy | Compute policy from `created_at` and reject late approvals in application logic | Product requires per-request expiration or indexed expiry jobs |
| Token scopes or delegated-consent records | Fine-grained human-agent permissions | Use existing human identity and role model only if it is safe | Security review determines existing tokens are too broad |

## Current Agent API Inventory

### Existing Agent Endpoints

| Endpoint | Current behavior | Main limitation |
|---|---|---|
| `GET /api/agent/manifest` | Returns version, capabilities, writable entities/actions, and limits | Advertises `apply_patch`, which always fails; omits the real change-request workflow |
| `GET /api/agent/programs` | Lists active programs in a space | Raw list without cursor pagination |
| `GET /api/agent/programs/{program_id}` | Retrieves one program | Works, but other entity types lack equivalent agent detail routes |
| `GET /api/agent/work-graph` | Returns programs and nested project/solution/task context | Summary fields only, project-level limit, no cursor, no `task_id` filter |
| `POST /api/agent/patches/validate` | Validates a patch without persisting it | Errors and schema discovery could be more machine-readable |
| `POST /api/agent/patches/apply` | Always returns `AGENT_APPROVAL_REQUIRED` | Should not be advertised as an available service-account capability |
| `POST /api/agent/change-requests` | Stores a pending approval request | Agent cannot retrieve the request later |
| `GET /api/agent/change-requests` | Lists requests for an interactive user | Service account cannot list its own requests; no cursor |
| `GET /api/agent/change-requests/{id}` | Retrieves a request for an interactive user | Service account cannot retrieve its own request |
| Approval/rejection endpoints | Human cookie session applies or rejects pending work | Cannot support a human approving through an agent interaction |

### Existing Write Coverage

The patch system supports:

- Entities: `program`, `project`, `solution`, `task`.
- Operations: `create`, `update`.
- Maximum of 25 operations per request.
- Optimistic concurrency through `if_updated_at`.
- Per-operation validation and results.
- Program creation through the same approval workflow as other entities.

Important gaps:

- No archive/delete operation.
- No reference from one create operation to an entity created earlier in the same patch.
- Update field allowlists are derived from create schemas, which can hide update-only fields.
- No change-request cancel or replacement lifecycle.
- No agent-safe document workflow.
- No complete agent-safe reference data for users, phases, statuses, and allowed transitions.

## Phase 0: Contract Alignment And Safety Baseline

### Goal

Make the current API truthful, documented, and measurable before expanding it.

### Deliverables

#### Correct The Manifest

The manifest should advertise actual behavior, including:

- `read_programs`
- `read_work_graph`
- `validate_patch`
- `submit_change_request`
- `read_own_change_requests` after Phase 1
- `cancel_own_change_request` after Phase 1
- `human_review_required: true`
- Supported entities and operations.
- Maximum operation count and page size.
- Agent API contract version.
- Links to the filtered OpenAPI and reference-data endpoints once available.

Remove `apply_patch` from service-account capabilities while direct application is intentionally forbidden. The route may remain as an explicit denial boundary for compatibility, but it must not be presented as usable.

#### Standardize Error Envelopes

Every Agent API error should contain:

```json
{
  "code": "STALE_ENTITY",
  "message": "Project has changed since if_updated_at",
  "request_id": "correlation-id",
  "details": {}
}
```

Requirements:

- Stable machine-readable code.
- Human-readable message.
- Correlation request ID.
- Optional structured details.
- No raw database or internal exception text.
- Consistent treatment of authentication, authorization, validation, conflict, not-found, and rate-limit failures.

#### Record Baseline Performance

Measure current endpoint behavior on representative seeded data before changing pagination or graph shape:

- Query count.
- Response size.
- p50 and p95 latency.
- Memory use where practical.
- Behavior at maximum current limits.

### Database Impact

None.

### Exit Criteria

- The manifest matches executable behavior.
- Agent errors have a consistent documented shape.
- Existing agent tests pass.
- Baseline performance results are recorded.
- No database files or migration SQL are changed.

## Phase 1: Complete The Change-Request Lifecycle

### Goal

Let a proposing agent retrieve, monitor, cancel, and reconcile its own submissions without granting approval authority.

### Endpoint Changes

#### `GET /api/agent/change-requests`

Service-account behavior:

- Return only requests proposed by the authenticated service account.
- Always enforce the selected space.
- Never allow a service account to list other proposers' requests.

Human reviewer behavior:

- Preserve space-wide review access based on the human's role.
- Keep service-account ownership filtering separate from reviewer filtering.

Recommended query parameters:

- `status`: repeatable or comma-separated status filter.
- `idempotency_key`: exact lookup for retry recovery.
- `created_since` and `updated_since`.
- `limit`, with a conservative default and hard maximum.
- `cursor`.
- `include=operations,diff,validation` so list callers can avoid large payloads.

Recommended response:

```json
{
  "records": [],
  "next_cursor": null,
  "has_more": false
}
```

Exact global counts should not be calculated on every list request. If counts are needed, expose them through an explicit summary option or endpoint.

#### `GET /api/agent/change-requests/{change_request_id}`

- A service account may retrieve only a request it proposed in the selected space.
- A human reviewer may retrieve requests allowed by their space role.
- Cross-space, non-owned service-account lookups should return 404 to avoid resource disclosure.
- The response must include terminal status, review note, failure information, final validation, per-operation results, created entity IDs, and timestamps.

#### `POST /api/agent/change-requests/{change_request_id}/cancel`

- Only the proposing service account may cancel its own pending request.
- Human administrators may be allowed to cancel based on product policy.
- Approved, rejected, failed, or already cancelled requests are immutable.
- Cancellation is audited and published through normal realtime invalidation.
- A cancelled request's idempotency key continues to identify that original immutable request.

#### Replacement Behavior

Initial no-database behavior:

1. Cancel the old request.
2. Submit a new request with a new idempotency key.
3. Return both identifiers to the client workflow.

Do not add durable `supersedes_change_request_id` until the database change gate is approved.

### CLI And Skill Changes

Add commands:

- `list-change-requests`
- `get-change-request`
- `wait-change-request`
- `cancel-change-request`

`wait-change-request` should:

- Poll with bounded exponential backoff and jitter.
- Stop on `approved`, `rejected`, `failed`, or `cancelled`.
- Respect a caller-specified timeout.
- Print final operation IDs and entity IDs.
- Never retry non-retryable authentication or validation failures indefinitely.

### Scalability Requirements

- Use keyset/cursor pagination ordered by a stable tuple such as `created_at` plus `change_request_id`.
- Apply ownership, space, and status filters before ordering and limiting.
- Avoid loading operations, diff, and validation JSON for summary lists unless requested.
- Establish a response-size cap.
- Test concurrent polling and submission behavior.

### Database Impact

No required schema change. The existing status string can represent `cancelled`.

The idempotency unique constraint remains an optional hardening proposal subject to the database change gate.

### Exit Criteria

- A service account can submit, retrieve, list, poll, and cancel its own request.
- It cannot retrieve another service account's request.
- It cannot approve or reject any request.
- Cursor traversal returns each matching record exactly once under stable test data.
- CLI commands and API documentation cover the entire lifecycle.
- Existing interactive approval behavior remains intact.

## Phase 2: Scalable Space And Work Discovery

### Goal

Let agents find the correct space and work item without retrieving entire unbounded collections.

### Space Discovery

Add an agent-safe paginated space surface, either by upgrading the existing accessible-space endpoint contract or adding:

- `GET /api/agent/spaces`
- `GET /api/agent/spaces/{space_id}`

Required filters:

- Exact `space_id`.
- Exact or normalized slug.
- Name search with a bounded result set.
- Active status where relevant.
- Cursor and limit.

The endpoint must not expose inaccessible spaces. A user or service account with hundreds of spaces must not receive an unbounded array.

### Work Detail Endpoints

Add stable, complete detail routes:

- `GET /api/agent/projects/{project_id}`
- `GET /api/agent/solutions/{solution_id}`
- `GET /api/agent/tasks/{task_id}`

Each response should include:

- Every field the agent is allowed to update.
- Parent IDs and stable display labels.
- `created_at` and `updated_at`.
- Effective or derived values where they affect decisions.
- Optional lightweight links to related resources.

This closes the read/write asymmetry and prevents callers from loading a full graph to inspect one item.

### Work Search

Add a paginated search/list contract that can locate work by:

- Entity type.
- Stable ID.
- Parent ID.
- Exact name and bounded text search.
- Status.
- Owner, assignee, sponsor, or approver identifier.
- Due-date range.
- Updated-since timestamp.
- Archived/active state where authorized.
- Cursor, limit, and stable sort.

This may be separate type-specific list endpoints or one clearly typed `/agent/work-items` endpoint. The implementation should favor simple SQL and explicit schemas over an overly generic query language.

### Work Graph V2

Retain the graph for contextual reasoning, but make it bounded and explicit:

- Add `task_id` filtering.
- Add `cursor` and `next_cursor` at the project boundary.
- Add `has_more`.
- Add `fields` or named projections such as `summary` and `full`.
- Define whether filters select parent graphs or filter nested children.
- Include complete fields only when explicitly requested.
- Keep child loading batched and avoid N+1 queries.

The graph should not be the only way to read work.

### Scalability Requirements

- Cursor tokens are opaque, versioned, and validated.
- Sorting always includes a unique tie-breaker ID.
- Invalid or cross-space cursors fail safely.
- Server-side limits have conservative defaults and hard maximums.
- Name search cannot trigger an unbounded full-space scan.
- Detail reads meet a tighter latency budget than graph reads.
- Large graph responses are capped by record count and serialized byte size.

### Initial Performance Targets

These are engineering targets to validate, not claims about current behavior:

- Detail endpoints: p95 under 500 ms at representative production volume.
- Paginated list endpoints: p95 under 750 ms for default page size.
- Work graph summary: p95 under 1,500 ms for the default page.
- No endpoint returns more than its documented maximum records.
- Query count remains bounded as page size grows.

### Database Impact

No initial schema change. Implement and benchmark against existing indexes first.

If query plans or p95 targets fail, propose exact composite indexes through the database change gate before changing SQL schema files.

### Exit Criteria

- Agents can locate spaces, projects, solutions, and tasks without broad downloads.
- Every writable field is readable through an agent detail contract.
- All collection responses are paginated and self-describing.
- Pagination, filtering, and space isolation have integration tests.
- Representative scale tests meet or document deviations from the performance targets.

## Phase 3: Patch Expressiveness And Full Work Management

### Goal

Support realistic multi-entity work creation and maintenance without repeated approval cycles or unsafe direct writes.

### Separate Create And Update Field Contracts

Build field allowlists from the correct schema for each operation:

- Create uses the entity's create schema.
- Update uses the entity's update schema.
- Archive uses an explicit archive contract.

Expose the allowed fields through reference data so clients do not infer them from errors.

### Client References For Hierarchical Creation

Support references to entities created earlier in the same patch:

```json
{
  "client_operation_id": "create-project",
  "op": "create",
  "entity": "project",
  "ref": "new-project",
  "fields": {
    "project_name": "Example"
  }
}
```

```json
{
  "client_operation_id": "create-solution",
  "op": "create",
  "entity": "solution",
  "project_ref": "new-project",
  "ref": "new-solution",
  "fields": {
    "solution_name": "Delivery"
  }
}
```

Requirements:

- References are unique within the patch.
- References can only point backward unless a dependency graph is explicitly implemented.
- Validation detects missing references, cycles, and type mismatches.
- Diff output clearly labels temporary references.
- Apply resolves references in one transaction.
- Results map every client operation and reference to the persisted entity ID.
- A failure rolls back the entire patch.

This should be implementable in application memory during validation and apply; it does not require storing reference mappings in the database.

### Archive Operations

Add approval-gated `archive` for entities with existing soft-delete support.

Requirements:

- Explicit entity ID and `if_updated_at`.
- Preflight validation of dependent active children.
- Clear cascade or rejection policy per entity.
- Diff describes what becomes inaccessible.
- Audit and realtime invalidation match normal UI deletes.
- Restore is not implied unless a separate restore contract is designed.

Hard delete is out of scope for the Agent API.

### No-Op And Transition Validation

- Reject or explicitly mark operations that produce no change.
- Return allowed status values and transitions.
- Validate parent moves and their cross-space boundaries.
- Preserve completion timestamps and other domain side effects through shared services.
- Keep the maximum patch size bounded.

### Database Impact

None expected for client references or soft archive operations.

### Exit Criteria

- One request can create a program/project/solution/task hierarchy atomically.
- Create and update field contracts match the underlying domain schemas.
- Agents can propose safe soft archives.
- Results return all created IDs.
- Atomic rollback and reference failure paths are tested.

## Phase 4: Human-Delegated Agent Review

### Goal

Allow a user to approve or reject through an agent-driven interaction without allowing service-account self-approval or relying exclusively on browser cookies.

### Principal Model

Keep two clearly different principals:

1. **Automation principal:** a service account that can read and propose within assigned spaces.
2. **Human-delegated principal:** a real user identity whose agent session can perform only actions the user is authorized to perform.

The API must know which principal is acting. A prompt statement such as “the user approved” is not authentication.

### Endpoint Behavior

The existing review routes may be retained, but their authentication dependency must distinguish:

- Browser cookie user.
- Safely authenticated human-delegated user.
- Service account, which remains forbidden.

Before a delegated approval:

- Retrieve and present the immutable diff.
- Obtain explicit confirmation for that request ID.
- Verify that the request is still pending.
- Revalidate optimistic concurrency.
- Apply using the acting human's identity.
- Return the final applied or failed result.

### Security Design Gate

Before implementation, document:

- How the agent obtains a human-delegated credential.
- Credential lifetime and revocation.
- Whether existing user API tokens are sufficient or too broad.
- How explicit confirmation is bound to the request being approved.
- Protection against confused-deputy and replay attacks.
- Required user role or permission.
- Audit fields and correlation IDs.

### Database Impact

Potentially none if an existing safely authenticated human credential is sufficient.

If token scopes, consent grants, or one-time approval records are required, stop at the database change gate and obtain explicit approval before adding tables or columns.

### Exit Criteria

- A user can approve or reject from an agent interaction using a verified human identity.
- A service account cannot approve, even if it proposed the request.
- The approval is bound to the reviewed immutable request.
- Space-role and cross-space tests pass.
- Security review signs off on the credential and confirmation model.

## Phase 5: Audit, Verification, And Contract Discovery

### Goal

Let agents verify outcomes, synchronize incrementally, and generate clients from a focused contract.

### `GET /api/agent/audit-feed`

Recommended filters:

- `since` and `until`.
- `entity_type` and `entity_id`.
- `user_id`.
- `request_id`.
- Change-request ID when correlation is available.
- Cursor and limit.

Requirements:

- Space-scoped service-account access.
- Cursor pagination with stable ordering.
- Bounded payloads.
- No exposure of secrets or unrelated tenant activity.
- Suitable for incremental synchronization without full graph reloads.

### `GET /api/agent/reference-data`

Return agent-relevant reference values:

- Entity types and operations.
- Create/update/archive fields by entity.
- Status enums and allowed transitions.
- RAG and confidence enums.
- Phases and phase identifiers.
- Patch and pagination limits.
- Supported filters and projections.

Reference data should be cacheable with a version or ETag.

### `GET /api/agent/openapi.json`

Return a filtered document containing only supported Agent API routes.

Requirements:

- Explicit stable operation IDs.
- Request and response schemas.
- Authentication and space headers.
- Examples.
- Error envelopes.
- Pagination schemas.
- Extensions identifying agent-safe and approval-gated operations.

### Database Impact

None initially. Reuse the existing audit log and OpenAPI generation.

An audit cursor index may be proposed later only if measurement justifies it.

### Exit Criteria

- Agents can verify an approved change without reloading an entire space.
- Incremental audit traversal is complete and non-duplicating under stable data.
- Reference data describes every supported patch field and enum.
- The filtered OpenAPI validates and can generate a smoke-test client.

## Phase 6: Extended End-User Workflow Coverage

### Goal

Cover the supporting resources required for daily end-user work after the core work hierarchy is complete.

### People And Team Reads

Agent-safe, paginated reads for:

- Users available in the selected space.
- Teams and membership.
- Roles relevant to assignment and approval.
- Capacity information where authorized.

These endpoints enable an agent to resolve assignees, owners, sponsors, and reviewers instead of submitting guessed identifiers.

### Solution Documents

Agent-safe operations may include:

- List document metadata.
- Download an authorized document.
- Propose document attachment or removal when storage and security rules are defined.

File upload requires separate security consideration for size limits, content types, malware scanning, storage quotas, and sensitive-data handling. Do not add unrestricted binary upload merely for endpoint parity.

### Activity And Comments

If product collaboration adds comments or user-facing activity, the Agent API should support bounded reads and appropriately authorized writes. System audit entries and human collaboration comments should remain distinct concepts.

### Notifications Or Events

Polling is acceptable initially. At higher concurrency, consider:

- Long polling.
- Webhooks with signatures and retry policy.
- Existing realtime channels adapted for service accounts.

Do not add a new durable event-delivery table without passing the database change gate.

### Database Impact

No Agent API-specific schema change is assumed. New product capabilities such as comments or notifications may have their own separately approved product data designs.

### Exit Criteria

- An agent can resolve people and team references at scale.
- Supporting endpoints are paginated, permission-aware, and documented.
- File operations, if added, pass a dedicated security review.

## Phase 7: Optional Database Hardening

### Goal

Introduce only the database changes proven necessary for integrity or measured scale after the earlier application-only phases are complete.

### Candidate 1: Idempotency Uniqueness

Potential constraint:

```text
UNIQUE (space_id, proposed_by_user_id, idempotency_key)
```

Benefit:

- Makes duplicate prevention correct under concurrent submissions.

Required analysis:

- Existing duplicate detection and cleanup.
- Oracle constraint naming and migration safety.
- Expected exception mapping to the existing idempotent response or conflict response.
- Rollback procedure.

### Candidate 2: Cursor Query Indexes

Potential index shapes depend on final query order and filters. Do not guess them in advance. Capture production-like query plans for:

- Space-scoped project update traversal.
- Proposer-scoped change-request traversal.
- Space/status change-request review traversal.
- Space-scoped audit traversal.

Add only indexes that materially improve the measured plan and do not impose unjustified write cost.

### Candidate 3: Durable Replacement And Expiration

Potential columns:

- `supersedes_change_request_id`
- `expires_at`

Add these only if the product requires server-queryable replacement chains or per-request expiry beyond application policy derived from `created_at`.

### Exit Criteria

- Each migration has independent approval.
- Forward and rollback SQL are tested.
- Schema models, canonical SQL, migrations, and documentation remain aligned.
- Query-plan or integrity evidence is recorded after deployment.

## Cross-Cutting Requirements

### Authorization Matrix

Every endpoint must document and test:

| Principal | Read work | Submit | Read own requests | Review requests | Approve/reject | Admin resources |
|---|---:|---:|---:|---:|---:|---:|
| Service account | Assigned spaces | Yes | Yes | No, except own status | Never | No |
| Human member | Assigned spaces | Product decision | Own and role-allowed | Based on role | Based on role | No |
| Space administrator | Space | Product decision | Space | Yes | Yes | Space only |
| Global administrator | Explicitly selected scope | Product decision | Authorized scope | Yes | Yes | Yes |

The exact human-member review policy must be decided. It should not remain accidental merely because the current minimum role is `member`.

### Pagination Contract

Use one shared pagination shape across Agent API collections:

```json
{
  "records": [],
  "next_cursor": "opaque-or-null",
  "has_more": true
}
```

Rules:

- Cursor is opaque to clients.
- Cursor contains or signs the contract version, sort position, and relevant filter fingerprint.
- Page order uses a unique tie-breaker.
- Changing filters invalidates the cursor.
- Default and maximum page sizes are documented.
- Cursors never bypass current authorization or space scope.
- Offset pagination is not introduced for large mutable collections.

### Concurrency And Idempotency

- Updates require `if_updated_at` or an equivalent version precondition.
- Request submission requires an idempotency key.
- Retrying an identical idempotency key returns the original request.
- Reusing a key with different content returns a stable conflict error.
- Approval always revalidates the patch.
- Client-reference patches apply atomically.
- Concurrent-submit and concurrent-approve tests are required.

### Rate And Resource Limits

Document limits for:

- Requests per principal and space.
- Poll frequency.
- Page size.
- Patch operation count.
- Serialized request size.
- Serialized response size.
- Audit window.
- File size if document operations are introduced.

Rate limiting may initially use deployment infrastructure or an existing application mechanism. A new database-backed limiter is not part of this roadmap.

### Observability

Measure by endpoint and response class:

- Request count.
- Latency.
- Error code.
- Authentication principal type.
- Page size and response bytes.
- Patch operation count.
- Validation failures.
- Approval latency and terminal outcome.
- Database query count or slow-query evidence where available.

Do not log bearer tokens, document contents, or entire potentially sensitive patch bodies.

### Caching

- Reference data and the filtered OpenAPI may be cached aggressively with version-based invalidation.
- Detail and graph responses may reuse existing smart-cache behavior only if space and principal scoping remain correct.
- Change-request status must not be cached in a way that delays terminal-state polling beyond the documented consistency expectation.
- Cache invalidation continues to use normal mutation publication paths.

### Compatibility

- Keep the current context path behavior.
- Existing endpoint consumers receive a compatibility window for response-shape changes.
- Prefer additive fields and new versioned response models.
- The skill wrapper and API contract documentation are updated in the same change as backend behavior.
- Manifest version changes whenever an agent must alter its workflow.

## Test And Validation Strategy

### Contract Tests

- Manifest matches route behavior.
- Filtered OpenAPI contains every advertised operation and no unsupported operation.
- Error envelopes have stable codes and request IDs.
- Every response validates against its published schema.

### Authorization Tests

- Missing bearer token.
- Non-service token on service-only route.
- Service account in an inaccessible space.
- Cross-space entity and cursor lookup.
- Service account reading another proposer's request.
- Service-account approval denial.
- Human role boundaries for review and approval.

### Pagination Tests

- Empty, first, middle, and final pages.
- Identical timestamps resolved by unique ID ordering.
- Invalid, tampered, expired-version, and cross-filter cursors.
- No duplicates or omissions across stable pages.
- Hard maximum enforcement.

### Lifecycle Tests

- Submit, idempotent retry, retrieve, approve, and verify.
- Submit, retrieve, reject, and verify.
- Submit and cancel.
- Stale-at-approval failure.
- Retry with changed payload conflict.
- Concurrent submission with the same idempotency key.
- Created entity IDs returned for every create operation.

### Scale Tests

Build deterministic test data representing at least:

- Hundreds of accessible spaces for one principal.
- Thousands of projects in a space.
- Tens of thousands of nested solutions and tasks.
- Large pending and historical change-request sets.
- Large audit history.
- Concurrent polling and submission clients.

Record latency, query count, response size, and failures. Scale tests should be runnable outside the default unit suite if their runtime is substantial.

### Regression Tests

- Existing UI reads and writes remain unchanged.
- Existing approval queue behavior remains unchanged for browser users.
- Audit logging, cache invalidation, and realtime publication still occur.
- Lobby and space-role protections remain enforced.

## Goal Execution Contract

This section is intended to support a long-running implementation goal.

### Goal Objective

Evolve SIPM's Agent API into a complete, scalable, approval-gated end-user workflow according to this roadmap, implementing phases in order, preserving service-account separation of duties, and making no database change without first producing the required database change proposal and receiving explicit approval.

### Execution Rules

1. Work one phase at a time.
2. Begin each phase by confirming current behavior with tests and source inspection.
3. Prefer shared domain services over duplicate Agent API logic.
4. Keep patches bounded and independently reviewable.
5. Update backend code, schemas, tests, the SIPM agent skill, CLI, and API contract together.
6. Run targeted validation after each bounded change and broader agent tests before closing a phase.
7. Measure collection and graph changes with representative data.
8. Do not modify database models, canonical SQL, or migration SQL unless the database change gate has been completed and approved.
9. If a phase uncovers a database need, stop that portion, document the proposal, and continue with safe application-only work where possible.
10. Do not mark the overall goal complete merely because one endpoint or phase works.

### Required Phase Artifacts

For each phase, record:

- Implemented endpoints and behavior.
- Authorization decisions.
- Files changed.
- Tests added and commands run.
- Performance or query evidence where relevant.
- Compatibility notes.
- Remaining risks.
- Database impact: `none`, `proposed but not implemented`, or `approved and implemented`.

### Overall Completion Criteria

The goal is complete only when:

- The Product Outcome workflow can be demonstrated end to end.
- Service accounts can retrieve and monitor their own requests.
- Human approval works through at least one safe path and service-account self-approval remains impossible.
- Spaces and all major work collections are bounded and cursor-paginated.
- Complete detail reads exist for every writable core entity.
- Program, project, solution, and task creation/update workflows are documented and tested.
- Hierarchical creation can be performed without repeated ID-discovery approval cycles.
- Agents can verify results through detail reads and audit history.
- Manifest, reference data, filtered OpenAPI, skill, CLI, and backend behavior agree.
- Authorization, pagination, concurrency, lifecycle, and representative scale tests pass.
- Any database changes have separate recorded approval and migration evidence.
- Remaining extended-resource exclusions are explicitly documented rather than implied to work.

## Recommended Delivery Sequence

1. **Phase 0:** truthful contract, error consistency, and baseline measurement.
2. **Phase 1:** service-account request retrieval, polling, cancellation, and CLI support.
3. **Phase 2:** scalable space discovery, detail reads, search, and paginated graph.
4. **Phase 3:** correct field contracts, hierarchical client references, and archive proposals.
5. **Phase 4:** secure human-delegated review design and implementation.
6. **Phase 5:** audit feed, reference data, and filtered OpenAPI.
7. **Phase 6:** people, teams, documents, activity, and event delivery as product needs require.
8. **Phase 7:** only database hardening supported by explicit approval and evidence.

Phases 0 through 2 provide the first complete operational improvement: agents can discover, read, submit, retrieve, poll, and reconcile at scale while human approval remains safely separated. Phases 3 through 5 turn that operational workflow into a full end-user contract. Phases 6 and 7 extend breadth and harden proven scale requirements.

## Immediate Decisions Before Implementation

1. Decide whether a human `member` may approve change requests or whether approval requires a space administrator or future explicit permission.
2. Decide the initial human-delegated authentication mechanism before Phase 4.
3. Decide whether graph projections should be named (`summary`, `full`) or field-selected.
4. Decide default and maximum page sizes for spaces, work lists, graph pages, change requests, and audit.
5. Decide the maximum serialized Agent API response size.
6. Decide whether archive is required in the first full-workflow release or may follow create/update.
7. Confirm that database work remains separately approved even when it is a correctness hardening change such as idempotency uniqueness.

## Closure Ledger

### Defined By This Roadmap

- Full target workflow.
- Phased endpoint delivery.
- Scale and pagination requirements.
- Service-account and human separation of duties.
- Database avoidance policy and explicit change gate.
- Test, performance, documentation, and completion expectations.

### Requires Product Or Security Decision

- Minimum human approval role.
- Human-delegated authentication and confirmation model.
- Archive dependency policy.
- Page-size and response-size limits.
- Scope of documents and collaboration endpoints.

### Not Authorized By This Roadmap

- Direct service-account patch application.
- Service-account self-approval.
- Hard deletion through the Agent API.
- Unbounded list or graph endpoints.
- Silent database migrations.
- A new workflow-run persistence model inside SIPM.
- Storing model prompts, reasoning, or external agent run state in SIPM.
