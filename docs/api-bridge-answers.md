# SIPM API Bridge Answers

## 1. What kind of API does the app expose?

The app exposes a REST API over HTTP. It is a FastAPI backend mounted under:

- App base: `/project-manager/`
- API base: `/project-manager/api`

It also exposes a WebSocket endpoint for realtime sync:

- WebSocket: `/project-manager/api/ws`

It does not expose a GraphQL API in this repo.

## 2. What operations does it support?

The app supports CRUD and reporting across several entities:

- Projects: create, list, get, update, delete
- Solutions: create, list, get, update, delete
- Subcomponents/tasks: create, list, get, update, delete
- Planning work allocation:
  - Teams: create, list, update, delete
  - People: create, list, update, delete
  - Tasks: create, list, update, delete
  - Allocations: create, list, update, delete

Filtering and reporting supported by the API includes:

- Project list filters: `status`, `sponsor`, `sponsor_user_soeid`
- Solution list filters: `project_id`, `status`, `owner`, `assignee`, `owner_user_soeid`, `assignee_user_soeid`, `phase`, `priority`, `due_before`, `due_after`
- Subcomponent/task list filters: `project_id`, `solution_id`, `status`, `priority`, `due_before`, `due_after`, `assignee`, `assignee_user_soeid`
- Planning task list filters: `month`, `search`
- Planning allocation list filter: `month`

Additional supported operations:

- CSV import/export for projects, solutions, subcomponents, and users
- PDF export for the work-allocation report
- Space management, team management, user administration, phases, audit, and analytics endpoints
- Realtime live-sync via WebSocket

I did not find dedicated comment or attachment-upload endpoints in the current backend.

## 3. How does it handle authentication?

Current runtime configuration is reverse-proxy header authentication, not API keys or OAuth.

In the checked-in local `.env`, the app is configured to:

- expect identity headers from a proxy: `SM_USER` and `name`
- provision/identify the user from those headers
- mint and use its own auth cookies for the session

For local development, the current `.env` also enables a mock proxy-header injector, so local requests can work without the enterprise proxy.

The codebase does include local `register`, `login`, `refresh`, and password reset endpoints, but those routes are disabled whenever proxy auth is enabled.

## 4. Where is it running?

From the repo and README, the default local/dev runtime is:

- UI: `http://127.0.0.1:8000/project-manager/`
- API: `http://127.0.0.1:8000/project-manager/api`

I can confirm the local/dev runtime from the repo. I do not see a checked-in public hosted URL, so if there is a separate reachable hosted deployment, that would need to be filled in manually.
