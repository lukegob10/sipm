# SIPM Space User Data Guide

This guide is for the common day-to-day case:

- you work in one or two spaces
- you mainly read project, solution, and subcomponent data
- you sometimes make light edits
- you sometimes export data for analysis

It intentionally skips global admin, space governance, planning, analytics, and other lower-frequency APIs.

## Base Setup

- UI root: `http://127.0.0.1:8000/project-manager/`
- API base: `http://127.0.0.1:8000/project-manager/api`
- OpenAPI docs: `http://127.0.0.1:8000/project-manager/docs`

## What Most Users Need

For normal space work, the most relevant routes are:

- session bootstrap: `/auth/me`
- current space lookup and switching: `/auth/active-space`, `/spaces`
- project data: `/projects`, `/projects/{project_id}`, `/projects/export`
- solution data: `/solutions`, `/projects/{project_id}/solutions`, `/solutions/{solution_id}`, `/solutions/export`
- subcomponent data: `/subcomponents`, `/solutions/{solution_id}/subcomponents`, `/subcomponents/{subcomponent_id}`, `/subcomponents/export`
- light edits: `PATCH /projects/{project_id}`, `PATCH /solutions/{solution_id}`, `PATCH /subcomponents/{subcomponent_id}`

## Access Expectations

- Read and export flows usually need `member` access in the active space.
- Edits usually need `space_admin` access in the active space.
- The active space is resolved from `X-Space-Id` or the `active_space_id` cookie.

## Session And Space Workflow

### 1. Start a session

In this repo's local dev setup, the easiest way to get working cookies is:

```bash
curl -i -c cookies.txt http://127.0.0.1:8000/project-manager/api/auth/me
```

That gives you the current user and sets the session cookies.

### 2. See your current active space

```bash
curl -b cookies.txt \
  http://127.0.0.1:8000/project-manager/api/auth/active-space
```

### 3. See which spaces you can work in

```bash
curl -b cookies.txt \
  http://127.0.0.1:8000/project-manager/api/spaces
```

### 4. Switch spaces when needed

```bash
curl -b cookies.txt \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{"space_id":"<space-id>"}' \
  http://127.0.0.1:8000/project-manager/api/auth/active-space
```

If you do not want to switch the cookie, you can also send `X-Space-Id` directly on requests.

## Most Useful Endpoints By Task

### Project work

| Method | Path | Typical use |
| --- | --- | --- |
| `GET` | `/projects` | List projects in the active space. |
| `GET` | `/projects/{project_id}` | Fetch one project in detail. |
| `PATCH` | `/projects/{project_id}` | Light project edits such as status, sponsor, description, or priority. |
| `GET` | `/projects/export` | Download project data as CSV. |

Common project filters on `GET /projects`:

- `status`
- `sponsor`
- `sponsor_user_soeid`

Common project fields people edit:

- `project_name`
- `status`
- `description`
- `success_criteria`
- `sponsor`
- `sponsor_user_soeid`
- `strategic_objective`
- `priority`

### Solution work

| Method | Path | Typical use |
| --- | --- | --- |
| `GET` | `/solutions` | List solutions across the active space. |
| `GET` | `/projects/{project_id}/solutions` | List solutions under a specific project. |
| `GET` | `/solutions/{solution_id}` | Fetch one solution in detail. |
| `PATCH` | `/solutions/{solution_id}` | Light solution edits such as status, assignee, due date, RAG, or repo URL. |
| `GET` | `/solutions/export` | Download solution data as CSV. |

Common solution filters:

- `project_id`
- `status`
- `owner`
- `assignee`
- `owner_user_soeid`
- `assignee_user_soeid`
- `phase`
- `priority`
- `due_before`
- `due_after`

Common solution fields people edit:

- `solution_name`
- `version`
- `github_repo_url`
- `status`
- `rag_status`
- `rag_reason`
- `priority`
- `due_date`
- `planned_start_date`
- `current_phase`
- `description`
- `success_criteria`
- `problem_statement`
- `owner`
- `owner_user_soeid`
- `assignee`
- `assignee_user_soeid`
- `approver`
- `approver_user_soeid`
- `key_stakeholder`
- `blockers`
- `risks`
- `impact_confidence`
- `rag_confidence`
- `capacity_hours`

### Subcomponent work

| Method | Path | Typical use |
| --- | --- | --- |
| `GET` | `/subcomponents` | List subcomponents across the active space. |
| `GET` | `/solutions/{solution_id}/subcomponents` | List subcomponents under one solution. |
| `GET` | `/subcomponents/{subcomponent_id}` | Fetch one subcomponent in detail. |
| `PATCH` | `/subcomponents/{subcomponent_id}` | Light subcomponent edits such as status, assignee, due date, blocked flag, or estimate. |
| `PATCH` | `/subcomponents/actions/batch` | Bulk update multiple subcomponents at once. |
| `GET` | `/subcomponents/{subcomponent_id}/activity` | See recent change history for one subcomponent. |
| `GET` | `/subcomponents/export` | Download subcomponent data as CSV. |

Common subcomponent filters:

- `project_id`
- `solution_id`
- `status`
- `priority`
- `due_before`
- `due_after`
- `assignee`
- `assignee_user_soeid`

Common subcomponent fields people edit:

- `subcomponent_name`
- `github_repo_url`
- `status`
- `priority`
- `due_date`
- `assignee`
- `assignee_user_soeid`
- `estimate_hours`
- `blocked`
- `blocker_note`
- `done_criteria`
- `capacity_hours`

## Recommended Day-To-Day Read Patterns

### Pull all projects in one space

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  http://127.0.0.1:8000/project-manager/api/projects
```

### Pull only active projects

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  "http://127.0.0.1:8000/project-manager/api/projects?status=active"
```

### Pull all active solutions assigned to someone

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  "http://127.0.0.1:8000/project-manager/api/solutions?status=active&assignee=Dev%20User"
```

### Pull all in-progress subcomponents for one solution

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  "http://127.0.0.1:8000/project-manager/api/solutions/<solution-id>/subcomponents?status=in_progress"
```

### Pull all overdue-style work candidates

The API does not expose an explicit overdue filter on subcomponents, but it does expose due-date filters. A common extraction pattern is:

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  "http://127.0.0.1:8000/project-manager/api/subcomponents?due_before=2026-04-17"
```

## Recommended Light Edit Patterns

These are the edits a space admin is most likely to make during normal work.

### Update a project status or priority

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  -H "Content-Type: application/json" \
  -X PATCH \
  -d '{
    "status": "active",
    "priority": 2
  }' \
  http://127.0.0.1:8000/project-manager/api/projects/<project-id>
```

### Update a solution owner, assignee, due date, or RAG

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  -H "Content-Type: application/json" \
  -X PATCH \
  -d '{
    "assignee": "Dev User",
    "assignee_user_soeid": "lg22254",
    "due_date": "2026-04-30",
    "rag_status": "amber",
    "rag_reason": "Waiting on dependency"
  }' \
  http://127.0.0.1:8000/project-manager/api/solutions/<solution-id>
```

### Update a subcomponent status, assignment, or blocker state

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  -H "Content-Type: application/json" \
  -X PATCH \
  -d '{
    "status": "in_progress",
    "assignee": "Dev User",
    "assignee_user_soeid": "lg22254",
    "blocked": true,
    "blocker_note": "Waiting for upstream data"
  }' \
  http://127.0.0.1:8000/project-manager/api/subcomponents/<subcomponent-id>
```

### Bulk update multiple subcomponents

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  -H "Content-Type: application/json" \
  -X PATCH \
  -d '{
    "subcomponent_ids": ["<sub-1>", "<sub-2>", "<sub-3>"],
    "status": "on_hold",
    "blocked": true
  }' \
  http://127.0.0.1:8000/project-manager/api/subcomponents/actions/batch
```

## Recommended Extraction Patterns

### Export projects to CSV

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  -o projects.csv \
  http://127.0.0.1:8000/project-manager/api/projects/export
```

### Export solutions to CSV

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  -o solutions.csv \
  http://127.0.0.1:8000/project-manager/api/solutions/export
```

### Export subcomponents to CSV

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  -o subcomponents.csv \
  http://127.0.0.1:8000/project-manager/api/subcomponents/export
```

## Working Across Two Spaces

If you regularly work in two spaces, there are two simple patterns:

- keep one active-space cookie and switch it with `/auth/active-space`
- keep the same cookie jar but always send `X-Space-Id`

Using `X-Space-Id` is usually simpler for scripts because you can reuse the same session and change only the header:

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-a>" \
  http://127.0.0.1:8000/project-manager/api/projects

curl -b cookies.txt \
  -H "X-Space-Id: <space-b>" \
  http://127.0.0.1:8000/project-manager/api/projects
```

## Minimal Endpoint Set For Normal Space Work

If you want the smallest practical set to learn first, start here:

- `GET /auth/me`
- `GET /auth/active-space`
- `POST /auth/active-space`
- `GET /spaces`
- `GET /projects`
- `GET /projects/{project_id}`
- `PATCH /projects/{project_id}`
- `GET /projects/export`
- `GET /solutions`
- `GET /projects/{project_id}/solutions`
- `GET /solutions/{solution_id}`
- `PATCH /solutions/{solution_id}`
- `GET /solutions/export`
- `GET /subcomponents`
- `GET /solutions/{solution_id}/subcomponents`
- `GET /subcomponents/{subcomponent_id}`
- `PATCH /subcomponents/{subcomponent_id}`
- `PATCH /subcomponents/actions/batch`
- `GET /subcomponents/{subcomponent_id}/activity`
- `GET /subcomponents/export`

## Notes

- `GET` routes are the main read and extraction path.
- `PATCH` routes are the main simple-edit path.
- CSV export routes are the easiest way to move data into Excel or downstream analysis.
- If you only need one route to confirm identity and start work, use `/auth/me`.
