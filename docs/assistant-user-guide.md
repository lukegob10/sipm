# Jira-lite Assistant User Guide

Version: 2026-02-09
Audience: members, space admins, global admins, and AI assistant support flows
Purpose: canonical source for user-facing guidance and issue triage in Jira-lite.

## Scope And How To Use This Guide
Use this document when a user asks:
- How to do a task in Jira-lite
- Why an action failed
- What role or access is required
- What screen to use next

Assistant response standard:
1. Confirm active space and current view.
2. Give exact click path (menu group > screen > control label).
3. Explain expected result and likely failure causes.
4. If blocked, provide next check with exact field/error text.

Response style requirements:
- Keep answers issue-focused and concise.
- Use short numbered steps for actions; avoid long background sections.
- Do not add unrelated commentary or feature tours unless user asks.
- Ask at most one clarifying question when required data is missing.

## Product Map And Naming
Navigation groups and current screen names:
- Build: Deliverables, Subcomponents, Planning, Kanban, Calendar, Dashboard
- AI & Docs: Document Studio (Workbench), Solution Designer (Structure Studio), AI Assistant
- Admin: Team Capacity, Spaces, Access

Route aliases (hash routes):
- `#/master` Deliverables
- `#/subcomponents-workbench` Subcomponents Workbench
- `#/planning` Planning
- `#/kanban` Kanban
- `#/calendar` Calendar
- `#/dashboard` Dashboard
- `#/workbench` Document Studio
- `#/structure-studio` Solution Designer
- `#/ai` AI Assistant
- `#/team-capacity` Team Capacity
- `#/spaces` Spaces
- `#/access` Access

Top bar controls:
- `connection-status` pill (online/offline)
- Space switcher
- Space role pill (`member`, `space_admin`, or `global admin`)
- Current user pill
- Logout and theme toggle

## Core Operating Model
Active space drives data scope:
- All operational data reads/writes are scoped to active space.
- Switching space reloads data and resets AI chat thread context.
- If user reports missing data, verify active space first.

Role model:
- `member`: delivery execution and standard planning operations
- `space_admin`: space operations and elevated delete/admin actions in that space
- `global_admin`: platform-wide admin, all active spaces

Important guardrails:
- Space must retain at least one active `space_admin`.
- Platform must retain at least one active `global_admin`.

## Authentication, Session, And Login Issues
Login and account creation:
- Login tab: SOEID + password
- Create account tab: name + SOEID + password

Password reset flow (`/reset-password`):
1. User clicks `Have a temp password?`.
2. Verify SOEID + temporary password.
3. Set new password and confirm.

Session behavior:
- Access tokens auto-refresh in background.
- Idle modal warns before sign-out (`Stay signed in` or `Log out`).
- On auth failures, UI shows sign-in requirement and routes to login screen.

Common auth errors and meaning:
- `Login failed. Check your username or password.`: invalid credentials or inactive account
- `Account locked. Try again later.`: too many failed logins (lockout)
- `Password reset required`: must complete reset flow first
- `Space is not accessible`: user attempted switching to space without active access

## Realtime Sync And Connection Status
Realtime updates:
- App connects to `/api/ws`.
- On entity changes, backend sends refresh events and UI reloads affected data.

User-visible behavior:
- Status pill shows `Online` when websocket is connected.
- If disconnected, data may appear stale until reconnect or manual action.

If data looks stale:
1. Check status pill.
2. Switch view (or space) to force refresh.
3. Retry action and verify no auth error occurred.

## Build: Deliverables (`#/master`)
Purpose:
- Primary workspace for projects, solutions, and in-context subcomponents.

Key actions:
- `Create Project`, `Create Solution`
- Inline update for status, priority, RAG (solutions)
- Presets: `My Items`, `Overdue`, `Blocked`, `Clear Filters`
- Bulk actions: set status, assign owner (solutions)
- CSV: `Projects CSV`, `Upload Projects`, `Solutions CSV`, `Upload Solutions`

Modal workflows:
- Project modal: details and lifecycle actions (save/create/delete)
- Solution modal tabs: `Details`, `Phases`, `Subcomponents`, `Activity`
- Subcomponents tab supports table/swimlane views and full CRUD

Important validation and role gates:
- Duplicate names blocked in scope:
- Project update conflict: `Project name already exists`
- Solution conflict: `Solution name and version already exist for this project`
- Subcomponent conflict: `Subcomponent name already exists in this solution`
- Deletes require `space_admin` (project, solution, subcomponent)
- Solution activity/audit views can be restricted; members may see unavailable activity data

## Build: Subcomponents Workbench (`#/subcomponents-workbench`)
Purpose:
- Cross-project operational queue for all subcomponents in active space.

Key actions:
- Presets: all, my assignments, due soon (14 days), overdue, blocked, unassigned, stale
- Multi-filtering: search, project, solution, assignee, status, priority max
- Bulk actions: set status, reassign, shift due date by days
- Quick Edit drawer for fast updates with activity feed
- Saved views per user+space in browser local storage

Keyboard shortcuts:
- `/` focus search
- `ArrowUp` / `ArrowDown` move active row
- `e` open quick edit drawer
- `Esc` close drawer

Common issues:
- `Enter a due date shift in whole days...`: invalid shift value
- `Activity unavailable for this role.`: user lacks access to required activity context
- Empty list with active filters: clear filters or apply different preset

## Build: Planning (`#/planning`)
Purpose:
- Month-based FTE planning and utilization balancing.

Primary flow:
1. Select/create planning window.
2. Add allocations by type (`solution`, `subcomponent`, `project`).
3. Review KPIs and roster load.
4. Adjust allocations or remove invalid entries.

Key controls:
- `Planning Window` selector and `Manage`
- `Add Allocation`
- Filters: person/work-item search, team tag, over/under allocated
- Allocation chip click opens details modal
- Allocation chip delete removes allocation

Validation and role gates:
- Allocation create/update: member or higher
- Allocation delete: `space_admin` required
- Planning window create/update: member or higher
- Planning window delete: `space_admin` required
- Required fields error: `Type, item, assignee, month, and FTE-months are required.`
- Window required error: `Select or create a planning window first.`

## Build: Kanban (`#/kanban`)
Purpose:
- Solution flow by project and phase group.

Key controls:
- Project filter
- Owner filter

Use cases:
- Identify stalled phase movement
- Weekly project execution review

## Build: Calendar (`#/calendar`)
Purpose:
- Due-date workload visibility by month and day.

Key controls:
- Month picker, prev/next month buttons
- Project filter, owner filter
- Click day cell to open day-detail modal

Use cases:
- Deadline collision detection
- Near-term readiness checks

## Build: Dashboard (`#/dashboard`)
Purpose:
- Portfolio and capacity health snapshot.

Panels include:
- Space capacity summary
- Top projects/solutions
- Completed last quarter
- Upcoming this quarter
- Backlog

Use cases:
- Stakeholder updates
- Portfolio health checkpoints

## AI & Docs: AI Assistant (`#/ai`)
Purpose:
- Conversational support for drafting and structured write operations.

How it works:
- User messages route to `/ai/chat`.
- Write-type outputs typically require approval.
- User can approve by replying `yes`/`approve`/`save`, reject with `no`/`discard`.
- `Auto-save` toggle can auto-approve drafts and persists in browser local storage.
- `New chat` resets thread context.

Best practice prompts:
- Include target screen, entity name, and intended result.
- For changes, ask for a preview before approval.

Common issues:
- `Would you like me to save this?`: pending approval state
- `Entity not found`: wrong ID/scope/space
- Unrelated answer: verify active space and provide concrete entity names

GenAI configuration failures (admin/operator-facing):
- Missing/invalid key returns config-style errors
- Permission-denied model responses block refine/generate endpoints

## AI & Docs: Document Studio / Workbench (`#/workbench`)
Purpose:
- Draft/refine lifecycle for charter, plan, SOW, and checklist artifacts.

Doc types:
- `charter`
- `plan`
- `sow`
- `checklist`

Key controls:
- Project selector
- Assist level: light/medium/heavy
- `Reset to Template`, `Validate`, `Download Rendered`, `Refine`, `Save`, `Mark Final`
- Revision history (except checklist) with revision delete
- Checklist month selector and `Generate`
- SOW approval controls: `Request`, `Approve`, `Reject`

Behavior details:
- Checklist saves as monthly checklist items (not revisioned doc records).
- `Mark Final` for SOW requires approval state = `approved`.
- Finalization also enforces template validation requirements.

Common errors:
- `approval_required`: approve SOW before finalizing
- `Invalid AI output`: LLM returned non-conforming payload
- `Save before finalizing.`: revision does not exist yet

## AI & Docs: Solution Designer / Structure Studio (`#/structure-studio`)
Purpose:
- Generate, refine, and commit solution/subcomponent decomposition from project context.

Inputs:
- Project
- Decomposition level (`simple` or `detailed`)
- Source documents (latest charter and plan)

Workflow:
1. Load context and sufficiency signal.
2. Generate draft solutions/subcomponents.
3. Accept/discard/refine individual items.
4. Optionally bulk accept/discard.
5. Commit accepted items.

Key rules:
- Subcomponents can only commit when parent solution is also accepted.
- If source sufficiency is low, generation may return minimal draft.
- Detailed refinement modal targets one selected draft item.

Common errors:
- `Generation blocked until required inputs are provided.`: insufficient inputs and strict generation mode
- Commit validation errors when parent-child acceptance is inconsistent
- `No targeted edits were generated from the instruction.`: refine instruction lacked actionable target detail

## Admin: Team Capacity (`#/team-capacity`)
Purpose:
- Maintain roster attributes used by planning (team tag, capacity FTE-month).

Key actions:
- Select member (datalist), update team tag and capacity, save
- `Deactivate Member` sets user inactive
- Filter by team tag or name
- Reload and clear filters
- Roster CSV import/export

Permissions:
- Write operations require `space_admin` or higher.
- Non-admin users may see read-only behavior depending on role/view access.
- Space admins cannot modify global-admin user accounts unless they are also global admin.

## Admin: Spaces (`#/spaces`)
Purpose:
- Space lifecycle and per-space membership administration.

Space actions:
- Create space (global admin only)
- Archive/reactivate space (global admin only)
- Switch active space

Membership actions:
- Add member by SOEID with role (`member`/`space_admin`) and status
- Promote/demote role
- Activate/deactivate membership
- Remove membership

Permission model:
- Global admin can manage memberships in any space.
- Space admin can manage memberships only in their currently active space.

Safety rule:
- Space cannot lose its last active `space_admin`.

## Admin: Access (`#/access`)
Purpose:
- Platform-wide global admin governance.

Key actions:
- Grant global admin by SOEID
- Revoke global admin by SOEID or from list row action

Safety rule:
- At least one active global admin must remain.

## CSV Import And Export Reference
Use export first to obtain exact headers, then edit and re-upload.

Projects CSV:
- Required: `project_name`, `sponsor`
- Supports update/create by `project_name`
- Duplicate names in same CSV rejected (strict-first)

Solutions CSV:
- Required: `project_name`, `solution_name`, `owner`
- Supports update/create by (`project_name`, `solution_name`, `version`)
- Can auto-create missing project
- `current_phase` must exist
- Duplicate solution+version rows in same CSV rejected

Subcomponents CSV:
- Required: `project_name`, `solution_name`, `subcomponent_name`, `assignee`
- Supports update/create in solution context
- Can auto-create missing project and solution
- Duplicate subcomponent rows in same CSV rejected

Team Capacity (Users) CSV:
- Required: `soeid`, `display_name`
- Optional: `team_tag`, `capacity_fte_month` (or legacy `capacity_hours`)
- Import ensures active membership in current space

Import result interpretation:
- Success can still contain row-level errors (partial success).
- UI shows created/updated counts and first few error messages.

## Role And Permission Quick Matrix
Member:
- Can create/update projects, solutions, subcomponents
- Can create/update planning windows and allocations
- Cannot delete projects/solutions/subcomponents
- Cannot delete allocations/windows
- Cannot manage global admins

Space admin:
- Member permissions plus delete operations in space
- Can manage team capacity and user updates in active space
- Can manage memberships in active space

Global admin:
- Full cross-space admin capabilities
- Can create/archive spaces
- Can grant/revoke global admin

## Troubleshooting Matrix
Cannot see Admin menu:
- User likely not `space_admin`/`global_admin` in active space.
- Verify top-bar role pill and active space.

Space data missing or wrong:
1. Confirm selected space in switcher.
2. Confirm membership is active for that space.
3. Refresh by switching view or space.

Action fails with permission error:
- Check role requirement for that action (delete/admin actions are elevated).
- For memberships, space_admin must be in the same active space.

Login fails repeatedly:
- Validate SOEID/password.
- Check for lockout (`Account locked. Try again later.`).
- If reset required, complete temp-password reset flow.

SOW cannot finalize:
- If message is `approval_required`, run SOW approval first.
- Re-run `Validate` and resolve required-section errors.

Document refine/generate failed:
- If `Invalid AI output`, retry once.
- If GenAI config/permission error, escalate to environment/model configuration owner.

CSV upload reports errors:
- Download export template and align headers.
- Fix required fields and duplicates.
- Re-upload only corrected rows.

Subcomponents activity not visible:
- User may lack role to read required activity context.
- Confirm role, space, and item existence.

Live status not online:
- Reconnect by reload.
- Verify auth/session is still valid.

## Support Playbooks (Common Requests)
Create first project/solution/subcomponents:
1. Build > Deliverables.
2. `Create Project` and save required fields.
3. `Create Solution` under project.
4. In solution modal, open `Subcomponents` tab and add tasks.

Allocate next month work:
1. Build > Planning.
2. Select or create planning window.
3. `Add Allocation`.
4. Pick type/item/assignee/month/FTE-months.
5. Save and review over/under-utilization.

Add user to a space:
1. Admin > Spaces.
2. Select target space under `Manage Space`.
3. Enter SOEID, role, and status.
4. Submit and verify in membership table.

Grant global admin:
1. Admin > Access.
2. Enter SOEID.
3. Click `Grant Global Admin`.
4. Verify user appears in global admin list.

## Assistant Escalation Rules
Escalate to admin/operator when:
- User hits auth lockout/reset loops.
- Global/space admin constraints block required org change.
- AI endpoints fail with configuration/permission errors.
- Data inconsistency persists after space verification and refresh.

When escalating, include:
- Exact screen and route
- Exact action attempted
- Exact error text
- Active space and user role
