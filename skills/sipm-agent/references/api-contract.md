# SIPM Agent API Contract

## Base

All paths are under:

```text
<SIPM_BASE_URL>/api
```

For the home-lab proxy this is commonly:

```text
http://sipm/project-manager/api
```

## Auth

Agent endpoints require:

```text
Authorization: Bearer <SIPM_AGENT_TOKEN>
X-Space-Id: <space_id>
Content-Type: application/json
```

The bearer token must belong to an active service account that is an active member of the requested space.

## Read Endpoints

`GET /spaces`

Returns spaces accessible to the authenticated token. Use this to resolve `main` to a `space_id`.

`GET /agent/manifest`

Returns V1 capabilities.

`GET /agent/work-graph`

Query params:

```text
project_id
solution_id
status
owner_user_soeid
assignee_user_soeid
updated_since
limit
```

Returns a nested project -> solution -> task graph with stable IDs and `updated_at`.

## Patch Shape

```json
{
  "dry_run": false,
  "reason": "Human-readable reason",
  "idempotency_key": "caller-generated-key",
  "operations": [
    {
      "client_operation_id": "stable-client-id",
      "op": "update",
      "entity": "solution",
      "id": "solution-id",
      "if_updated_at": "2026-05-29T04:02:50",
      "fields": {
        "description": "New description"
      }
    }
  ]
}
```

## Validation

`POST /agent/patches/validate`

Validates a patch without committing or creating a pending approval row.

## Submit for Approval

`POST /agent/change-requests`

Validates the patch, stores a pending approval request, and returns its diff. It does not mutate project manager data.

## Approval

Approval and rejection use cookie-authenticated interactive user endpoints. Agent service-account tokens must not approve or reject their own proposals.
