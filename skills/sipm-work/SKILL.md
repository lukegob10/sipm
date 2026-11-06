---
name: sipm-work
description: Use a lightweight workflow for a developer's SIPM work. Use when listing active Tasks assigned to an SOE ID, pulling one Task and its Project/Solution/GitHub context into a local folder, proposing shared context or blocker updates, or reporting implementation complete. Use sipm-agent for broad administration, complex patches, or review workflows.
---

# SIPM Work

Use the shared `skills/sipm-agent/scripts/sipm_agent.py` helper. This skill is intentionally limited to the developer work loop; SIPM remains the canonical task system and never runs code or launches agents.

## Configure

Keep credentials out of prompts and files:

Enter the API token when prompted; terminal input is hidden and is not stored in shell history.

```bash
export SIPM_BASE_URL="https://<sipm-host>/project-manager"
IFS= read -r -s -p "SIPM API token: " SIPM_AGENT_TOKEN
printf "\n"
export SIPM_AGENT_TOKEN
# Optional: export SIPM_SPACE_ID="exact-space-id"
```

Never print, echo, or commit the token. Use HTTPS for deployed services; HTTP is suitable for local development. Resolve the space rather than guessing it. Use the final scheme, host, and port; the helper refuses redirects to a different origin.

## Work Loop

Run the examples from the SIPM repository root, and replace the quoted angle-bracket placeholders with actual values. First discover accessible spaces and use the intended space's exact ID or unambiguous slug in the commands below:

```bash
python skills/sipm-agent/scripts/sipm_agent.py list-spaces --all
```

1. List the active shared Tasks assigned to the developer's exact SOE ID:

```bash
python skills/sipm-agent/scripts/sipm_agent.py list-assigned-work \
  --space "<resolved-space-id-or-slug>" --soeid "<soeid>" --all
```

The result contains hierarchy, actionability, acceptance criteria, and the effective GitHub repository. It excludes completed, abandoned, archived, or parent-archived Tasks and excludes the user's private drag order.

2. Pull one Task into an empty local folder:

```bash
python skills/sipm-agent/scripts/sipm_agent.py checkout-task \
  --space "<resolved-space-id-or-slug>" --task-id "<task-id>" --output-dir "<empty-folder>"
```

The checkout contains `TASK.md`, `task.json`, and `context.json`. Treat it as a snapshot. The command does not clone GitHub, run code, launch an agent, claim the Task, or change SIPM.

3. When the user wants shared task context, blocker state, or status changed, propose the narrowest update and explain that approval is required:

```bash
python skills/sipm-agent/scripts/sipm_agent.py propose-update \
  --space "<resolved-space-id-or-slug>" --entity-type task --id "<task-id>" \
  --fields-json '{"blocked":true,"blocker_note":"Waiting for test credentials"}' \
  --reason "Record the implementation blocker"
```

If submission has an ambiguous outcome, retain the idempotency key printed by the helper and look up the existing request before retrying:

```bash
python skills/sipm-agent/scripts/sipm_agent.py list-change-requests \
  --space "<resolved-space-id-or-slug>" --status all --idempotency-key "<key>"
```

4. When implementation is complete, propose the existing shared Task status transition:

```bash
python skills/sipm-agent/scripts/sipm_agent.py propose-update \
  --space "<resolved-space-id-or-slug>" --entity-type task --id "<task-id>" \
  --fields-json '{"status":"complete"}' \
  --reason "Implementation and acceptance checks are complete"
```

## Boundaries

- Never infer a person's SOE ID from a display name when assignment accuracy matters.
- Never alter private My Work queue order through the Agent API.
- Do not overwrite a non-empty checkout folder.
- Do not treat checkout as a lock or claim; re-read the Task before proposing an update.
- All Task writes use optimistic concurrency and the approval-gated change-request flow.
- Escalate broad inventory, hierarchy creation, multi-entity changes, approval, or audit work to `sipm-agent`.
