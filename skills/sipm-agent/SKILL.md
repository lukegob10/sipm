---
name: sipm-agent
description: Work with SIPM's approval-gated agent API for project manager data transport. Use when Codex needs to read SIPM spaces/work graphs, validate agent patches, submit pending change requests for projects, solutions, or tasks, or help an external coding agent interact with SIPM through configurable base URL, token, space, and proxy settings.
---

# SIPM Agent

## Overview

Use this skill to interact with SIPM through the controlled Agent API. Agent writes must be submitted as change requests; do not bypass the approval gate with normal program, project, solution, or task write endpoints.

The bundled command wrapper is `scripts/sipm_agent.py`. It uses Python stdlib only and reads credentials/config from environment variables or CLI flags.

## Configuration

Prefer environment variables so secrets are not written into prompts, scripts, or repo files:

```bash
SIPM_BASE_URL=http://sipm/project-manager
SIPM_AGENT_TOKEN=<service-account-api-token>
SIPM_SPACE_ID=<optional-default-space-id>
SIPM_PROXY=http://proxy-host:port
```

Rules:
- `SIPM_BASE_URL` must point at the app root, including `/project-manager` when SIPM is behind that proxy path.
- `SIPM_AGENT_TOKEN` must be a service-account bearer token.
- `SIPM_SPACE_ID` is optional when a command can resolve `--space main` through `/api/spaces`.
- `SIPM_PROXY` is optional. If omitted, Python's normal proxy environment handling still applies.
- Never print or commit tokens.

## Command Workflow

Run commands from the skill folder or pass the full script path.

Check connectivity and discover spaces:

```bash
python skills/sipm-agent/scripts/sipm_agent.py list-spaces
```

Read scoped work context:

```bash
python skills/sipm-agent/scripts/sipm_agent.py work-graph --space main --project-name "HomeLab Server"
```

List or inspect programs:

```bash
python skills/sipm-agent/scripts/sipm_agent.py list-programs --space main
python skills/sipm-agent/scripts/sipm_agent.py get-program --space main --program-id <program-id>
```

Submit a new program for approval:

```bash
python skills/sipm-agent/scripts/sipm_agent.py propose-program-create \
  --space main \
  --program-name "Test Program" \
  --description "Program created by the agent API" \
  --reason "Create test program"
```

Resolve a solution by names:

```bash
python skills/sipm-agent/scripts/sipm_agent.py resolve-solution --space main --project-name "HomeLab Server" --solution-name Alpha
```

Submit a solution update as a pending approval request:

```bash
python skills/sipm-agent/scripts/sipm_agent.py propose-solution-update \
  --space main \
  --project-name "HomeLab Server" \
  --solution-name Alpha \
  --description "Short proposed description." \
  --reason "Update Alpha solution description"
```

Validate or submit a prepared patch JSON file:

```bash
python skills/sipm-agent/scripts/sipm_agent.py validate-patch --space main --patch-file patch.json
python skills/sipm-agent/scripts/sipm_agent.py submit-change-request --space main --patch-file patch.json
```

## Patch Contract

Read `references/api-contract.md` before building raw patch files or adding new commands.

V1 supports only:
- entities: `program`, `project`, `solution`, `task`
- operations: `create`, `update`
- max operations: `25`

Update operations require:
- `id`
- `if_updated_at`
- allowed mutable fields only

Create operations require:
- `program_name` for programs
- `project_id` for solutions
- `solution_id` for tasks

Submission requires:
- `dry_run=false`
- `reason`
- `idempotency_key`

## Operating Rules

- Use `/api/agent/programs` and `/api/agent/work-graph` to fetch stable IDs and `updated_at` before proposing updates.
- Use `/api/agent/patches/validate` when assembling a complex patch.
- Use `/api/agent/change-requests` to submit proposals.
- Expect submitted changes to remain pending until a real user approves them in SIPM.
- Treat `if_updated_at` failures as normal concurrency protection; refetch work graph and create a fresh proposal.
- Do not use normal write endpoints with service-account tokens. They should return `AGENT_APPROVAL_REQUIRED`.
