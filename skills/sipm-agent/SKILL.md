---
name: sipm-agent
description: Operate SIPM through its scoped, approval-gated Agent API. Use to discover SIPM spaces, locate or inspect programs/projects/solutions/tasks, understand bounded work context, validate and submit atomic change proposals, poll or cancel owned requests, perform explicitly authenticated human-delegated review, or verify results through the audit feed.
---

# SIPM Agent

Use `scripts/sipm_agent.py`, a stdlib-only wrapper around the Agent API. Never use normal work-item write endpoints with a service-account token.

## Configuration

Keep credentials out of prompts and files:

```bash
SIPM_BASE_URL=http://sipm/project-manager
SIPM_AGENT_TOKEN=<service-account-token>
SIPM_SPACE_ID=<optional-exact-default-space-id>
SIPM_HUMAN_TOKEN=<optional-human-access-session-token-for-delegated-review>
SIPM_PROXY=<optional-proxy>
```

`SIPM_BASE_URL` is the app root, including `/project-manager` when deployed there. Never print, echo, or commit tokens. A service token reads and proposes; a short-lived human access-session token only enters delegated-review commands.

## Conversational Boundary

Translate each user turn into the narrowest stage that satisfies it:

1. **Discover scope** — resolve the space; do not guess it.
2. **Locate** — use typed server-side search; do not download the graph to find a name.
3. **Inspect** — fetch one direct detail before deciding or updating.
4. **Understand context** — use a bounded summary graph only when relationships matter; request `full` only when genuinely needed.
5. **Validate** — validate complex or multi-operation patches before submission.
6. **Propose** — submit one coherent user intent with a reason and idempotency key.
7. **Track** — retrieve, poll, cancel, or replace the pending request; do not silently submit duplicates.
8. **Review** — service accounts cannot approve. Human-delegated review requires a human access-session token, an inspected immutable diff, and explicit user confirmation bound to its ID and `updated_at`.
9. **Verify** — use the returned entity IDs and audit feed instead of reloading an entire space.

Do not combine unrelated user intentions merely because a patch can contain 25 operations. A hierarchy created for one outcome is coherent; unrelated housekeeping is not.

## Fast Path

Start by checking capabilities and resolving a space:

```bash
python skills/sipm-agent/scripts/sipm_agent.py manifest
python skills/sipm-agent/scripts/sipm_agent.py list-spaces --all
```

Locate and inspect one item:

```bash
python skills/sipm-agent/scripts/sipm_agent.py search-work --space main --entity-type solution --exact-name Alpha
python skills/sipm-agent/scripts/sipm_agent.py get-work --space main --entity-type solution --id <solution-id>
```

Resolve assignment and approval identities before proposing them:

```bash
python skills/sipm-agent/scripts/sipm_agent.py list-people --space main --soeid <soeid>
python skills/sipm-agent/scripts/sipm_agent.py list-teams --space main --all
python skills/sipm-agent/scripts/sipm_agent.py list-team-members --space main --team-id <team-id> --all
```

Use contextual graph data sparingly:

```bash
python skills/sipm-agent/scripts/sipm_agent.py work-graph --space main --project-id <project-id> --projection summary
```

Before constructing a raw patch, fetch the live contract:

```bash
python skills/sipm-agent/scripts/sipm_agent.py reference-data
```

For one update, the wrapper fetches `updated_at` and builds the optimistic operation:

```bash
python skills/sipm-agent/scripts/sipm_agent.py propose-update \
  --space main --entity-type solution --id <solution-id> \
  --fields-json '{"description":"Short proposed description"}' \
  --reason "Clarify Alpha scope" --validate-only
```

After the validation result is clean, run the same command without `--validate-only`. For multi-entity work, use `validate-patch` and `submit-change-request` with the contract in `references/api-contract.md`.

## Request Lifecycle

```bash
python skills/sipm-agent/scripts/sipm_agent.py list-change-requests --space main --status pending
python skills/sipm-agent/scripts/sipm_agent.py get-change-request --space main --request-id <id>
python skills/sipm-agent/scripts/sipm_agent.py poll-change-request --space main --request-id <id>
python skills/sipm-agent/scripts/sipm_agent.py cancel-change-request --space main --request-id <id>
```

On a stale entity, refetch the direct detail, explain the conflict, and create a fresh proposal with a fresh idempotency key. Never rewrite the stored request.

## Human-Delegated Review

Only enter this flow when the user explicitly asks to approve or reject. From an authenticated human browser session, call `POST /api/agent/delegated-session` to obtain a 10-minute, session-bound delegated token, then configure it as `SIPM_HUMAN_TOKEN`. Do not expose the token in conversation.

First retrieve and present the complete diff:

```bash
python skills/sipm-agent/scripts/sipm_agent.py review-request --space main --request-id <id>
```

After explicit confirmation, pass the exact `updated_at` from that response:

```bash
python skills/sipm-agent/scripts/sipm_agent.py delegated-approve \
  --space main --request-id <id> --observed-updated-at <updated_at> \
  --review-note "Explicitly approved by the authenticated user"
```

Never substitute `SIPM_AGENT_TOKEN` for `SIPM_HUMAN_TOKEN`, infer approval from an earlier unrelated statement, or approve a request whose diff changed.

## Operating Rules

- Prefer exact IDs. If only a name is known, use `search-work` and stop on ambiguity.
- Use cursor traversal only when the user's intent needs all matches.
- Use summary projections by default; full projections can become large.
- Read `references/api-contract.md` before creating raw patches or changing this wrapper.
- Treat validation errors as structured guidance; do not weaken the contract to force a request through.
- Soft archive is approval-gated. It is not hard delete and does not imply restore.
- Verify applied work with `get-work` and `audit-feed` scoped to the returned entity or request correlation.
- If server manifest/reference versions differ from this skill, trust the live manifest and reference data, then update the skill before using unsupported behavior.
