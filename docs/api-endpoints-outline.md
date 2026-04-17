# SIPM Endpoint Outline

## Base URLs

- UI root: `http://127.0.0.1:8000/project-manager/`
- API base: `http://127.0.0.1:8000/project-manager/api`
- OpenAPI JSON: `http://127.0.0.1:8000/project-manager/openapi.json`
- Swagger UI: `http://127.0.0.1:8000/project-manager/docs`
- ReDoc: `http://127.0.0.1:8000/project-manager/redoc`
- Health: `http://127.0.0.1:8000/health`
- Readiness: `http://127.0.0.1:8000/health/ready`

## How To Access The API

### Auth model

The current repo-root `.env` enables reverse-proxy auth plus the local dev mock header injector.

In local dev, the simplest way to get a working session is:

```bash
curl -i -c cookies.txt http://127.0.0.1:8000/project-manager/api/auth/me
```

That request provisions or resolves the current user and sets the auth cookies used by protected endpoints.

Then resolve the active space:

```bash
curl -b cookies.txt http://127.0.0.1:8000/project-manager/api/auth/active-space
```

If you want to target a specific space, send `X-Space-Id` or switch the active-space cookie:

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  http://127.0.0.1:8000/project-manager/api/projects
```

### Access rules

- `public`: no auth required
- `session`: needs the SIPM auth cookies
- `member`: authenticated user with access to the active space
- `space_admin`: space admin in the active space, or global admin
- `global_admin`: global admin only

### WebSocket access

- URL: `ws://127.0.0.1:8000/project-manager/api/ws`
- Auth: `access_token` cookie or `?token=<access-token>`
- Space targeting: `X-Space-Id`, `?space_id=<space-id>`, or `active_space_id` cookie

### Useful notes

- All API routes below are relative to `/project-manager/api` unless noted otherwise.
- Most protected routes use the active space from `X-Space-Id` or the `active_space_id` cookie.
- Every response includes `X-Request-ID`.

## Operational Endpoints

| Method | Path | Access | What it does |
| --- | --- | --- | --- |
| `GET` | `/health` | `public` | Lightweight liveness check that returns `{"status":"ok"}`. |
| `GET` | `/health/ready` | `public` | Readiness check for auth config, proxy auth config, frontend bundle, and DB connectivity. |
| `GET` | `/project-manager/docs` | `public` | Swagger UI for the FastAPI app. |
| `GET` | `/project-manager/openapi.json` | `public` | Full OpenAPI schema for the backend. |
| `GET` | `/project-manager/redoc` | `public` | ReDoc documentation view. |
| `GET` | `/project-manager/` | `public` | Single-page app entry point. |
| `GET` | `/project-manager/reset-password` | `public` | Frontend reset-password route. |

## Auth And Session

| Method | Path | Access | What it does |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | `public`, only when proxy auth is disabled | Creates a local user and issues session cookies. |
| `POST` | `/auth/login` | `public`, only when proxy auth is disabled | Local username/password login that issues session cookies. |
| `POST` | `/auth/refresh` | `session` | Refreshes the auth cookies using the refresh token cookie. |
| `POST` | `/auth/reset-password` | `public`, only when proxy auth is disabled | Resets a password using a temporary password. |
| `POST` | `/auth/logout` | `session` | Clears auth cookies. |
| `GET` | `/auth/me` | `public` or `session` | Returns the current user; under proxy auth it can also bootstrap a session from identity headers. |
| `GET` | `/auth/active-space` | `session` | Returns the resolved active space, role, and analytics flag. |
| `POST` | `/auth/active-space` | `session` | Switches the active space by setting the active-space cookie. |

## Projects

| Method | Path | Access | What it does |
| --- | --- | --- | --- |
| `GET` | `/projects` | `member` | Lists projects in the active space; filters include `status`, `sponsor`, and `sponsor_user_soeid`. |
| `POST` | `/projects` | `space_admin` | Creates a project. |
| `GET` | `/projects/{project_id}` | `member` | Returns one project. |
| `PATCH` | `/projects/{project_id}` | `space_admin` | Updates a project. |
| `DELETE` | `/projects/{project_id}` | `space_admin` | Soft-deletes a project. |
| `POST` | `/projects/import` | `space_admin` | Bulk creates or updates projects from CSV bytes. |
| `GET` | `/projects/export` | `member` | Exports projects as CSV. |

## Solutions

| Method | Path | Access | What it does |
| --- | --- | --- | --- |
| `GET` | `/solutions` | `member` | Lists solutions across the active space; supports filters like `project_id`, `status`, `owner`, `assignee`, `phase`, `priority`, `due_before`, and `due_after`. |
| `GET` | `/projects/{project_id}/solutions` | `member` | Lists solutions for one project with the same filter set. |
| `POST` | `/projects/{project_id}/solutions` | `space_admin` | Creates a solution under a project. |
| `GET` | `/solutions/{solution_id}` | `member` | Returns one solution. |
| `PATCH` | `/solutions/{solution_id}` | `space_admin` | Updates a solution. |
| `DELETE` | `/solutions/{solution_id}` | `space_admin` | Soft-deletes a solution. |
| `POST` | `/solutions/import` | `space_admin` | Bulk creates or updates solutions from CSV bytes; may auto-create referenced projects. |
| `GET` | `/solutions/export` | `member` | Exports solutions as CSV. |

## Phases

| Method | Path | Access | What it does |
| --- | --- | --- | --- |
| `GET` | `/phases` | `session` | Lists the global phase catalog. |
| `GET` | `/solutions/{solution_id}/phases` | `session` | Lists enabled phases for a solution in order. |
| `POST` | `/solutions/{solution_id}/phases` | `space_admin` | Upserts the enabled phase configuration for a solution. |

## Subcomponents

| Method | Path | Access | What it does |
| --- | --- | --- | --- |
| `GET` | `/subcomponents` | `member` | Lists subcomponents across the active space; filters include `project_id`, `solution_id`, `status`, `priority`, date filters, and assignee fields. |
| `GET` | `/solutions/{solution_id}/subcomponents` | `member` | Lists subcomponents for one solution with the same filter set. |
| `POST` | `/solutions/{solution_id}/subcomponents` | `space_admin` | Creates a subcomponent under a solution. |
| `GET` | `/subcomponents/{subcomponent_id}` | `member` | Returns one subcomponent. |
| `PATCH` | `/subcomponents/{subcomponent_id}` | `space_admin` | Updates one subcomponent. |
| `PATCH` | `/subcomponents/actions/batch` | `space_admin` | Bulk updates subcomponents by ID. |
| `DELETE` | `/subcomponents/{subcomponent_id}` | `space_admin` | Soft-deletes a subcomponent. |
| `GET` | `/subcomponents/{subcomponent_id}/activity` | `session` | Returns recent audit activity for one subcomponent. |
| `POST` | `/subcomponents/import` | `space_admin` | Bulk creates or updates subcomponents from CSV bytes; may auto-create projects and solutions. |
| `GET` | `/subcomponents/export` | `member` | Exports subcomponents as CSV. |

## Teams

These are the generic team-management endpoints, separate from the planning-board team endpoints.

| Method | Path | Access | What it does |
| --- | --- | --- | --- |
| `GET` | `/teams` | `member` | Lists teams in the active space. |
| `POST` | `/teams` | `space_admin` | Creates a team. |
| `GET` | `/teams/{team_id}` | `member` | Returns one team with members. |
| `PATCH` | `/teams/{team_id}` | `space_admin` | Updates team metadata and capacity defaults. |
| `DELETE` | `/teams/{team_id}` | `space_admin` | Soft-deletes a team and its team members. |
| `GET` | `/teams/{team_id}/members` | `member` | Lists members attached to a team. |
| `POST` | `/teams/{team_id}/members` | `space_admin` | Adds a team member record. |
| `PATCH` | `/teams/{team_id}/members/{member_id}` | `space_admin` | Updates a team member record. |
| `DELETE` | `/teams/{team_id}/members/{member_id}` | `space_admin` | Soft-deletes a team member record. |

## Spaces

| Method | Path | Access | What it does |
| --- | --- | --- | --- |
| `GET` | `/spaces` | `session` | Lists spaces the current user can access. |
| `POST` | `/spaces` | `global_admin` | Creates a space. |
| `PATCH` | `/spaces/{space_id}` | `global_admin` | Updates space metadata and active/archive state. |
| `GET` | `/spaces/{space_id}/members` | `space_admin` for that space, or `global_admin` | Lists memberships in a space. |
| `POST` | `/spaces/{space_id}/members` | `space_admin` for that space, or `global_admin` | Adds a user to a space by `user_id`. |
| `POST` | `/spaces/{space_id}/members/by-soeid` | `space_admin` for that space, or `global_admin` | Adds a user to a space by SOEID. |
| `PATCH` | `/spaces/{space_id}/members/{membership_id}` | `space_admin` for that space, or `global_admin` | Updates a membership role or status. |
| `DELETE` | `/spaces/{space_id}/members/{membership_id}` | `space_admin` for that space, or `global_admin` | Removes a membership. |

## Users

| Method | Path | Access | What it does |
| --- | --- | --- | --- |
| `GET` | `/users` | `member` | Lists users in the active space; supports `team_tag` and `active_only`. |
| `GET` | `/users/export` | `member` | Exports the active space roster as CSV. |
| `PATCH` | `/users/{user_id}` | `space_admin` | Updates a user in the active space. |
| `PATCH` | `/users/by-soeid/{soeid}` | `space_admin` | Updates a user in the active space by SOEID. |
| `POST` | `/users/import` | `space_admin` | Bulk creates or updates users from CSV bytes and ensures active membership in the current space. |
| `GET` | `/users/global-admins` | `global_admin` | Lists global admin accounts. |
| `POST` | `/users/{user_id}/global-admin` | `global_admin` | Grants global admin to a user by `user_id`. |
| `DELETE` | `/users/{user_id}/global-admin` | `global_admin` | Revokes global admin from a user by `user_id`. |
| `POST` | `/users/by-soeid/{soeid}/global-admin` | `global_admin` | Grants global admin to a user by SOEID. |
| `DELETE` | `/users/by-soeid/{soeid}/global-admin` | `global_admin` | Revokes global admin from a user by SOEID. |
| `POST` | `/users/{user_id}/password-reset-request` | `global_admin` | Issues a temporary password for a user by `user_id`. |
| `POST` | `/users/by-soeid/{soeid}/password-reset-request` | `global_admin` | Issues a temporary password for a user by SOEID. |

## Planning: Work Allocation Board

These are the newer planning-board endpoints used by the `#/planning` work-allocation UI.

| Method | Path | Access | What it does |
| --- | --- | --- | --- |
| `GET` | `/planning/work-allocation/teams` | `member` | Lists planning-board teams. |
| `POST` | `/planning/work-allocation/teams` | `space_admin` | Creates a planning-board team. |
| `PATCH` | `/planning/work-allocation/teams/{team_id}` | `space_admin` | Updates a planning-board team. |
| `DELETE` | `/planning/work-allocation/teams/{team_id}` | `space_admin` | Deletes a planning-board team. |
| `GET` | `/planning/work-allocation/people` | `member` | Lists planning-board people. |
| `POST` | `/planning/work-allocation/people` | `space_admin` | Creates a planning-board person. |
| `PATCH` | `/planning/work-allocation/people/{person_id}` | `space_admin` | Updates a planning-board person. |
| `DELETE` | `/planning/work-allocation/people/{person_id}` | `space_admin` | Deletes a planning-board person. |
| `GET` | `/planning/work-allocation/tasks` | `member` | Lists planning-board tasks; supports `month` and `search`. |
| `POST` | `/planning/work-allocation/tasks` | `space_admin` | Creates a planning-board task. |
| `PATCH` | `/planning/work-allocation/tasks/{task_id}` | `space_admin` | Updates a planning-board task. |
| `DELETE` | `/planning/work-allocation/tasks/{task_id}` | `space_admin` | Deletes a planning-board task. |
| `GET` | `/planning/work-allocation/allocations` | `member` | Lists task allocations for a given month. |
| `POST` | `/planning/work-allocation/allocations` | `space_admin` | Creates a task allocation for a person or team. |
| `PATCH` | `/planning/work-allocation/allocations/{allocation_id}` | `space_admin` | Reassigns or resizes an allocation. |
| `DELETE` | `/planning/work-allocation/allocations/{allocation_id}` | `space_admin` | Deletes an allocation. |
| `GET` | `/planning/work-allocation/report.pdf` | `member` | Downloads the monthly work-allocation report as PDF. |

## Planning: Legacy Allocation API

These older planning endpoints still exist beside the work-allocation board routes.

| Method | Path | Access | What it does |
| --- | --- | --- | --- |
| `GET` | `/resource-allocations` | `member` | Lists resource allocations; filters include `from`, `to`, `assignee`, `assignee_user_soeid`, `team_id`, and `window_id`. |
| `POST` | `/resource-allocations` | `space_admin` | Creates a legacy resource allocation record. |
| `PATCH` | `/resource-allocations/{allocation_id}` | `space_admin` | Updates a legacy allocation. |
| `DELETE` | `/resource-allocations/{allocation_id}` | `space_admin` | Deletes a legacy allocation. |
| `GET` | `/resource-allocations/summary` | `space_admin` | Aggregates allocation totals by assignee and month. |
| `GET` | `/planning/windows` | `member` | Lists planning windows. |
| `POST` | `/planning/windows` | `space_admin` | Creates a planning window. |
| `PATCH` | `/planning/windows/{window_id}` | `space_admin` | Updates a planning window. |
| `DELETE` | `/planning/windows/{window_id}` | `space_admin` | Deletes a planning window. |

## Audit

| Method | Path | Access | What it does |
| --- | --- | --- | --- |
| `GET` | `/audit` | `space_admin` | Returns audit log entries; filters include `entity_type`, `entity_id`, `field`, `user_id`, `since`, `until`, `all_spaces`, and `limit`. |

## Analytics

Usage analytics must be enabled and the analytics tables must exist.

| Method | Path | Access | What it does |
| --- | --- | --- | --- |
| `POST` | `/analytics/ingest` | `session` | Accepts frontend usage events and performance samples for the current user and active space. |
| `GET` | `/analytics/summary` | `global_admin` | Returns summary analytics for a time window; supports `days`, `all_spaces`, and `space_id`. |
| `GET` | `/analytics/routes` | `global_admin` | Returns route-level usage statistics for a time window. |
| `GET` | `/analytics/performance` | `global_admin` | Returns aggregated performance metrics for a time window. |

## Realtime Sync

| Method | Path | Access | What it does |
| --- | --- | --- | --- |
| `WS` | `/ws` | `session` | Opens the realtime sync channel used by the frontend for live updates. |

## Quick Curl Examples

### List projects

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  http://127.0.0.1:8000/project-manager/api/projects
```

### Create a project

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  -H "Content-Type: application/json" \
  -X POST \
  -d '{
    "project_name": "Example Project",
    "status": "not_started",
    "sponsor": "Dev User"
  }' \
  http://127.0.0.1:8000/project-manager/api/projects
```

### Import projects from CSV

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  -H "Content-Type: text/csv" \
  --data-binary @projects.csv \
  http://127.0.0.1:8000/project-manager/api/projects/import
```

### Download the planning report PDF

```bash
curl -b cookies.txt \
  -H "X-Space-Id: <space-id>" \
  -o work-allocation-report.pdf \
  "http://127.0.0.1:8000/project-manager/api/planning/work-allocation/report.pdf?month=2026-04"
```
