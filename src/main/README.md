# SIPM App (Work Allocation Board MVP)

This app now uses `#/planning` as a **Work Allocation Board** for FTE-month task allocation.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r src/main/requirements.txt
uvicorn backend.main:app --reload --app-dir src/main
```

Then open `http://127.0.0.1:8000/#/planning`.

## Planning MVP Features

- Backlog tasks with search and effort filter.
- Team columns with person cards and capacity bars.
- Drag/drop assignment:
  - Backlog -> person
  - Backlog -> team header
  - Assigned task -> backlog (unassign)
- Task details side panel (edit/unassign/delete).
- Month selector (`YYYY-MM`) and month-scoped allocations.
- Inline add team/person/task.
- Undo last action (client-side stack).

## Seed Data

On first load of `GET /api/planning/work-allocation/tasks` in a low-data space:

- Seeds 2 teams
- Seeds up to 6 sample people (when active roster is near-empty)
- Seeds 10 backlog tasks with varied FTE-month sizes

This is persisted to the existing app database.

## Work Allocation API

- `GET/POST/PATCH/DELETE /api/planning/work-allocation/teams`
- `GET/POST/PATCH/DELETE /api/planning/work-allocation/people`
- `GET/POST/PATCH/DELETE /api/planning/work-allocation/tasks`
- `GET/POST/DELETE /api/planning/work-allocation/allocations`

Validation highlights:

- A task can have only one allocation per month (no split allocation in MVP).
- Assignee must exist (person or team).
