# SIPM Agent Handoff Protocol

## Summary

SIPM should act as the human-in-the-loop task and context source for agentic coding work. It should not automatically trigger a coding agent in the first version.

The first protocol should create durable draft coding jobs from SIPM work items, let a developer review and claim them in the coding harness, and only execute the coding workflow after that person approves the work.

Core flow:

```text
SIPM work item
  -> draft agent job
  -> harness available queue
  -> user claims
  -> user reviews prompt/checklist
  -> harness executes
  -> branch/PR/test results reported back to SIPM
```

## Key Interfaces

Add an `agent_jobs` domain that records:

- Source type and source ID: `solution` or `subcomponent`.
- Space ID and source work metadata.
- Title, repository URL, base ref, generated branch name.
- Generated prompt and review checklist.
- Status, assignee, claimant, and harness run ID.
- Branch URL, PR URL, result summary, test evidence, and timestamps.

Suggested statuses:

- `draft_ready`
- `claimed`
- `reviewing`
- `running`
- `waiting_for_user`
- `pr_opened`
- `completed`
- `failed`
- `cancelled`

Suggested SIPM endpoints:

- `POST /api/agent-handoff/drafts`
  - Creates a non-running draft from a solution or subcomponent.
- `GET /api/agent-handoff/jobs?scope=available|mine|space`
  - Lets the harness show claimable or owned work.
- `POST /api/agent-handoff/jobs/{job_id}/claim`
  - Atomically claims a job.
- `POST /api/agent-handoff/jobs/{job_id}/events`
  - Records harness status, branch, PR, tests, and final outcome.

## Behavior

- Subcomponent jobs use the effective GitHub repository URL: subcomponent override first, then inherited solution repository.
- Solution jobs emit one solution-level job unless the user explicitly chooses selected subcomponents as separate jobs.
- SIPM generates a prompt and checklist from project context, solution context, subcomponent context when present, acceptance criteria, done criteria, blockers, risks, repo/base branch, expected branch name, and expected PR notes.
- SIPM does not call Cursor or start an agent in v1.
- The harness owns clone, branch creation, agent execution, testing, push, draft PR creation, and workspace cleanup after human approval.
- SIPM stores the execution trail and links.
- SIPM does not automatically mark the source work item complete; completion remains a user-confirmed PM action.

## Identity And Authorization

The harness should authenticate to SIPM with a user plus device token.

- A developer can see assigned jobs and unclaimed jobs in spaces where they have access.
- A developer can claim an available job.
- Only the claimant, assignee, or a space admin can update active execution state.
- Space admins can reassign or cancel jobs.
- Every claim, launch, status update, PR link, and completion event should be auditable.

## Test Plan

- Verify packet generation for solution jobs and subcomponent jobs.
- Verify inherited repository URL behavior for subcomponents.
- Verify missing required context creates an incomplete draft, not a runnable or claimable job.
- Verify user/device auth, space isolation, assigned visibility, unclaimed visibility, and admin override.
- Verify atomic claim behavior under concurrent claim attempts.
- Verify event ingestion is idempotent.
- Verify only the claiming user/device can update a running job.
- Verify harness contract: list available jobs, claim, show prompt/checklist, post status, post PR/test result.

## Assumptions

- The custom coding harness is the execution layer.
- Cursor is the developer working environment, not the SIPM protocol owner.
- SIPM v1 stores no Cursor or external agent-provider secrets.
- Branch and draft PR creation are performed by the harness.
- Cursor's documented background-agent API launch endpoint starts an agent immediately, so SIPM should not use it as a draft-job mechanism unless Cursor adds a separate draft or deep-link capability.

## Reference

- Cursor Background Agent launch API: https://docs.cursor.com/background-agent/api/launch-an-agent
