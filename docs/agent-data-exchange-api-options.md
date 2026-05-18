# Agent Data Exchange API Options

## Goal

Support local coding agents and automation skills that can safely pull SIPM work data, edit it as a text artifact, and send it back without bypassing API auth, space scoping, validation, audit logging, cache invalidation, or live refresh.

## Current State

The app already exposes CSV import/export flows for projects, solutions, and subcomponents. CSV is good for spreadsheet workflows and is reasonably LLM-friendly, but it is lossy compared with the API model:

- Types are flattened into strings.
- Relationships rely on name matching unless IDs are included and preserved.
- Partial updates are awkward because the importer has to infer intent row by row.
- Agent workflows need extra file parsing and column-shape discipline.

## Recommendation

Keep CSV as the human/spreadsheet interchange format. Add JSON bulk exchange as the coding-agent interchange format.

JSON will not create a huge speedup by itself for full-dataset exports. The main performance win comes from selective filters, pagination, and delta export. JSON still helps agents because it preserves structure, IDs, nulls, booleans, nested context, and validation metadata without CSV parsing overhead.

## Proposed Minimal Endpoint Set

Add six JSON-focused endpoints, parallel to the CSV mental model:

- `GET /api/projects/export.json`
- `POST /api/projects/import.json`
- `GET /api/solutions/export.json`
- `POST /api/solutions/import.json`
- `GET /api/subcomponents/export.json`
- `POST /api/subcomponents/import.json`

Each export endpoint should support filters such as:

- `project_id`
- `solution_id`
- `status`
- `owner_user_soeid`
- `assignee_user_soeid`
- `updated_since`
- `include_closed`
- `limit` and `cursor`

Each import endpoint should support:

- `dry_run=true`
- upsert by stable IDs when present
- safe fallback matching by natural keys where IDs are absent
- row/object-level validation errors
- response counts for created, updated, skipped, and failed records
- normal mutation publishing so active users see changes without refresh

## User Matching

Agent-facing JSON should avoid fuzzy person matching wherever possible. Exports should include both display names and stable user identifiers, such as `owner_user_soeid`, `assignee_user_soeid`, `approver_user_soeid`, and `sponsor_user_soeid`. Imports should prefer those stable identifiers, then only fall back to names when no identifier is supplied.

This means a coding agent can filter for "work owned by this SOEID" or update an assignee without re-solving a person from free text. A separate user lookup endpoint may be useful later, but it is not required for the first JSON import/export pass if stable user fields are included consistently.

## JSON Shape

Prefer a wrapper object over a raw array so the file can carry context:

```json
{
  "space_id": "space-123",
  "exported_at": "2026-05-18T00:00:00Z",
  "entity": "projects",
  "records": []
}
```

For imports, allow `records` plus optional mode flags:

```json
{
  "mode": "upsert",
  "records": []
}
```

## Pros And Cons

JSON pros:

- Best fit for coding agents and local scripts.
- Preserves IDs, nulls, arrays, and nested relationships.
- Easier to diff, validate, and round-trip safely than CSV.
- Enables narrow filtered exports instead of pulling every project or solution.

JSON cons:

- Less friendly for business users editing in Excel.
- Requires stricter schema/version handling.
- More dangerous if imports allow broad updates without dry-run and validation previews.

CSV pros:

- Works well for templates, bulk spreadsheet edits, and simple text review.
- Existing import/export behavior already works and should remain supported.
- Easier for non-developers to understand.

CSV cons:

- More fragile for identifiers, dates, blanks vs nulls, and relationship matching.
- Harder for agents to make precise partial updates.
- Whole-file workflows encourage stale local copies.

## Design Guardrails

- Do not expose direct database access to agents.
- Keep all writes behind existing API auth, active-space scope, validation, auditing, cache invalidation, and realtime broadcast behavior.
- Make `dry_run` cheap and first-class.
- Prefer filtered exports over whole-space exports for agent tasks.
- Include stable IDs in every JSON export so agents can patch exact records.
- Consider optimistic concurrency later, such as `updated_at` preconditions, if overwrite risk becomes real.

## Bottom Line

CSV should stay. JSON bulk import/export should be added for agent workflows. The highest-value version is not just "CSV but JSON"; it is JSON plus filters, dry-run validation, stable IDs, and normal live-refresh publishing.
