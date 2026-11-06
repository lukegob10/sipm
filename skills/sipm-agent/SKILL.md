---
name: sipm-agent
description: Operate SIPM through its full scoped, approval-gated Agent API. Use for space discovery, broad program/project/solution/task administration, bounded work graphs, complex or multi-entity patch proposals, change-request lifecycle management, explicitly authenticated human-delegated review, and audit verification. Use the sipm-work skill instead for a developer's assigned queue and local task checkout.
---

# SIPM Agent

Use `scripts/sipm_agent.py`, a stdlib-only wrapper around the Agent API. An API token is an additional credential for a normal user account. Never use normal work-item write endpoints with an API token; submit proposals through the Agent API for interactive human review.

## Configuration

Keep credentials out of prompts and files:

Enter the API token when prompted; terminal input is hidden and is not stored in shell history.

```bash
export SIPM_BASE_URL="https://<sipm-host>/project-manager"
IFS= read -r -s -p "SIPM API token: " SIPM_AGENT_TOKEN
printf "\n"
export SIPM_AGENT_TOKEN
# Optional: export SIPM_SPACE_ID="exact-space-id"
# Optional: export SIPM_PROXY="http://proxy:port"
```

`SIPM_BASE_URL` is the app root, including `/project-manager` when deployed there. Use HTTPS for deployed services; HTTP is suitable for local development. Use the final scheme, host, and port: the helper refuses redirects to a different origin to protect credentials. Never print, echo, or commit tokens. An API token reads and proposes; a short-lived human access-session token only enters delegated-review commands. API tokens inherit their owner's active role and space memberships.

## Conversational Boundary

Translate each user turn into the narrowest stage that satisfies it:

1. **Discover scope** — resolve the space; do not guess it.
2. **Locate** — use typed server-side search; do not download the graph to find a name.
3. **Inspect** — fetch one direct detail before deciding or updating.
4. **Understand context** — use a bounded summary graph only when relationships matter; request `full` only when genuinely needed.
5. **Validate** — validate complex or multi-operation patches before submission.
6. **Propose** — submit one coherent user intent with a reason and idempotency key.
7. **Track** — retrieve, poll, cancel, or replace the pending request in place; do not silently submit duplicates.
8. **Review** — API tokens cannot approve. Human-delegated review requires a human access-session token, an inspected diff, and explicit user confirmation bound to its ID and `updated_at`.
9. **Verify** — use the returned entity IDs and audit feed instead of reloading an entire space.

Do not combine unrelated user intentions merely because a patch can contain 25 operations. A hierarchy created for one outcome is coherent; unrelated housekeeping is not.

## Fast Path

Run the examples from the SIPM repository root, and replace the quoted angle-bracket placeholders with actual values.

Start by checking capabilities and resolving a space:

```bash
python skills/sipm-agent/scripts/sipm_agent.py manifest
python skills/sipm-agent/scripts/sipm_agent.py list-spaces --all
```

Locate and inspect one item:

```bash
python skills/sipm-agent/scripts/sipm_agent.py search-work --space "<resolved-space-id-or-slug>" --entity-type solution --exact-name Alpha
python skills/sipm-agent/scripts/sipm_agent.py get-work --space "<resolved-space-id-or-slug>" --entity-type solution --id "<solution-id>"
```

Resolve assignment and approval identities before proposing them:

```bash
python skills/sipm-agent/scripts/sipm_agent.py list-people --space "<resolved-space-id-or-slug>" --soeid "<soeid>"
python skills/sipm-agent/scripts/sipm_agent.py list-teams --space "<resolved-space-id-or-slug>" --all
python skills/sipm-agent/scripts/sipm_agent.py list-team-members --space "<resolved-space-id-or-slug>" --team-id "<team-id>" --all
```

Use contextual graph data sparingly:

```bash
python skills/sipm-agent/scripts/sipm_agent.py work-graph --space "<resolved-space-id-or-slug>" --project-id "<project-id>" --projection summary
```

Before constructing a raw patch, fetch the live contract:

```bash
python skills/sipm-agent/scripts/sipm_agent.py reference-data
```

For one update, the wrapper fetches `updated_at` and builds the optimistic operation:

```bash
python skills/sipm-agent/scripts/sipm_agent.py propose-update \
  --space "<resolved-space-id-or-slug>" --entity-type solution --id "<solution-id>" \
  --fields-json '{"description":"Short proposed description"}' \
  --reason "Clarify Alpha scope" --validate-only
```

After the validation result is clean, run the same command without `--validate-only`. For multi-entity work, use `validate-patch` and `submit-change-request` with the contract in `references/api-contract.md`.

For generated submission keys, the helper prints the idempotency key to stderr before sending the proposal. Retain it: if the result is ambiguous, look up the existing request with `list-change-requests --space "<resolved-space-id-or-slug>" --status all --idempotency-key "<key>"` before retrying. Do not submit a new generated key merely because the response was lost.

## Request Lifecycle

```bash
python skills/sipm-agent/scripts/sipm_agent.py list-change-requests --space "<resolved-space-id-or-slug>" --status pending
python skills/sipm-agent/scripts/sipm_agent.py get-change-request --space "<resolved-space-id-or-slug>" --request-id "<id>"
python skills/sipm-agent/scripts/sipm_agent.py replace-change-request --space "<resolved-space-id-or-slug>" --request-id "<id>" --patch-file corrected-patch.json
python skills/sipm-agent/scripts/sipm_agent.py poll-change-request --space "<resolved-space-id-or-slug>" --request-id "<id>"
python skills/sipm-agent/scripts/sipm_agent.py cancel-change-request --space "<resolved-space-id-or-slug>" --request-id "<id>"
```

When a pending proposal still represents the same user intent, replace it in place so its request ID and queue position remain stable. Replacement revalidates the complete proposal and uses `updated_at` to prevent overwriting a request that changed after retrieval. If the request is terminal or the intent is unrelated, submit a new request instead.

## Human-Delegated Review

Only enter this flow when the user explicitly asks to approve or reject. From an authenticated human browser session, call `POST /api/agent/delegated-session` to obtain a 10-minute, session-bound delegated token, then configure it as `SIPM_HUMAN_TOKEN`. Do not expose the token in conversation.

Enter the delegated token separately with hidden terminal input, then export it:

```bash
IFS= read -r -s -p "SIPM human token: " SIPM_HUMAN_TOKEN
printf "\n"
export SIPM_HUMAN_TOKEN
```

Set the exact previously resolved space ID for delegated review. With `SIPM_SPACE_ID`, these commands do not need an API token for space discovery:

```bash
export SIPM_SPACE_ID="<exact-space-id>"
```

First retrieve and present the complete diff:

```bash
python skills/sipm-agent/scripts/sipm_agent.py review-request --request-id "<id>"
```

After explicit confirmation, pass the exact `updated_at` and `content_fingerprint` from that response:

```bash
python skills/sipm-agent/scripts/sipm_agent.py delegated-approve \
  --request-id "<id>" --observed-updated-at "<updated_at>" \
  --observed-fingerprint "<content_fingerprint>" \
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
