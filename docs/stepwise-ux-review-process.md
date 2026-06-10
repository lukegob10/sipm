# SIPM Stepwise UX Review Process

Purpose: define a repeatable UX review process for SIPM that improves the product workflow by workflow instead of trying to redesign the full application in one pass.

This document is the operating plan for future UX cleanup work. Each pass should produce a clear workflow map, click-count baseline, friction findings, proposed improvements, and validation notes before moving to the next workflow.

This process is intentionally separate from code quality review. A workflow can be technically correct and still be frustrating, slow to understand, too click-heavy, visually noisy, or unclear under error conditions.

## UX Review Principles

- Start with the user goal, not the screen or component.
- Count actions honestly: clicks, menu opens, navigation changes, modal opens, form submissions, required field edits, confirmation steps, reloads, and recovery actions all count.
- Separate necessary complexity from accidental friction.
- Keep common actions obvious and close to the user context.
- Keep rare, destructive, or admin-only actions discoverable but not dominant.
- Prefer one confident primary path over several competing paths.
- Make empty, loading, error, success, and permission states feel intentional.
- Avoid hiding critical work behind labels that only developers understand.
- Do not optimize for one-click speed when the action is destructive, cross-space, or hard to undo.
- Do not add shortcuts until the base workflow is understandable without them.
- Review desktop and mobile behavior separately when the workflow matters on both.
- Validate UX changes with real task completion, not only screenshots.

## Standard UX Pass Template

Use this sequence for every workflow.

1. Define the user goal.
   - Name the job the user is trying to complete.
   - Identify the user role: contributor, project owner, space admin, global admin, service-account operator, or executive viewer.
   - Identify the expected outcome in plain language.
   - Identify why this workflow matters to adoption.

2. Map the current path.
   - Start from a realistic entry point: fresh login, current route, dashboard, direct URL, modal, or deep link.
   - List every user action required to complete the goal.
   - Count clicks, menu opens, modal opens, field edits, saves, confirmations, route changes, and waits.
   - Note decision points where the user must know what to choose.
   - Note hidden prerequisites such as active space, role, existing project, or required reference data.

3. Classify the workflow.
   - `critical daily`: common work users do repeatedly.
   - `critical occasional`: important work done less often.
   - `admin critical`: setup, permissions, recovery, and governance.
   - `review and insight`: dashboards, reporting, planning review, and status checks.
   - `bulk or recovery`: import/export, bulk edit, reset, delete, and error recovery.

4. Identify friction.
   - Count avoidable clicks.
   - Identify duplicated entry points that compete with each other.
   - Identify missing entry points where users must navigate away from context.
   - Identify ambiguous labels, unclear button hierarchy, and hidden required fields.
   - Identify places where users must remember state from another screen.
   - Identify long forms that mix required and optional work without grouping.
   - Identify modals that interrupt flow or trap users in a narrow context.
   - Identify slow or unclear loading states.
   - Identify error messages that do not explain the next action.

5. Decide whether the friction is justified.
   - Keep extra confirmation for destructive or irreversible actions.
   - Keep role or space selection visible when it changes data boundaries.
   - Keep advanced controls secondary when they are not part of the common path.
   - Reduce clicks for high-frequency non-destructive actions.
   - Move details out of the main path when they are rarely needed.
   - Promote hidden actions when users need them to complete the core job.

6. Review information architecture.
   - Confirm the route name matches the user goal.
   - Confirm navigation groups match user mental models.
   - Confirm related work is co-located.
   - Confirm a user can recover orientation after route changes, space switches, modal closes, and browser refresh.
   - Confirm empty states explain what to do next without becoming marketing copy.

7. Review interaction quality.
   - Check focus behavior after opening and closing modals.
   - Check keyboard and pointer workflows.
   - Check disabled states and busy states.
   - Check inline validation before submit where possible.
   - Check success feedback lands near the action that succeeded.
   - Check destructive actions clearly name what will be deleted or changed.
   - Check bulk actions summarize scope before applying.
   - Check browser back/forward behavior.

8. Review visual clarity.
   - Confirm primary actions are visually distinct.
   - Confirm secondary and destructive actions do not compete with the primary path.
   - Confirm tables, cards, filters, and forms have stable layout under real data.
   - Confirm dense operational screens remain scannable.
   - Confirm text fits in buttons, pills, table cells, modals, and mobile widths.
   - Confirm color and icons carry meaning consistently.

9. Review resilience.
   - Confirm the workflow handles empty data, partial data, stale data, failed requests, expired sessions, permission loss, and live-sync refresh.
   - Confirm the user does not lose unsaved work without warning.
   - Confirm retries are obvious when the failure is recoverable.
   - Confirm session or space changes do not leave stale records visible.

10. Plan UX improvements.
   - List findings by severity.
   - Mark each finding as `must-fix`, `should-fix`, or `advisory`.
   - For each finding, name the user pain and the proposed interaction change.
   - Estimate the before and after action count.
   - Identify whether the change is copy-only, layout-only, behavior-only, or cross-layer.
   - Defer redesigns that are too large for the current workflow pass.

11. Validate.
   - Re-run the click-count path after the proposed change.
   - Capture desktop and mobile screenshots when layout changes.
   - Run route smoke tests for navigation-sensitive workflows.
   - Run focused frontend unit or Playwright tests for changed interactions.
   - Record any unresolved UX risk.

12. Close the pass.
   - Record what changed.
   - Record before and after action count.
   - Record validation.
   - Record remaining UX debt.
   - Decide the next workflow.

## UX Finding Severity

- Critical / must-fix: users cannot complete a core workflow, destructive action is unclear, permissions or spaces are visually misleading, or session failure leaves the app stale.
- High / must-fix: frequent workflow has avoidable confusion, repeated failed attempts, hidden primary action, misleading feedback, or excessive action count.
- Medium / should-fix: workflow is complete but slower or noisier than necessary, with avoidable navigation, modal, copy, or layout friction.
- Low / advisory: polish, consistency, visual hierarchy, or affordance improvements with limited task-completion impact.

## Action Count Rules

Count an action when the user must intentionally do it.

- Count route navigation.
- Count opening a menu.
- Count selecting from a menu.
- Count opening a modal.
- Count each required form field edit.
- Count changing a filter if the workflow requires it.
- Count save, submit, apply, confirm, cancel, or close.
- Count switching spaces.
- Count waiting only when the UI gives no clear progress or next state.
- Do not count passive reading unless the workflow depends on finding one detail among many.

Use this format:

```markdown
### Action Count

Start state: signed in, active space selected, on Deliverables.
Goal: create a solution under an existing project.

Current path:
1. Open Create menu.
2. Click Create Solution.
3. Choose project.
4. Enter solution name.
5. Enter owner.
6. Click Create Solution.

Current count: 6 actions.
Expected count for this workflow class: 4-6 actions.
Assessment: acceptable if project and owner are required; review whether owner can default to current user.
```

## Workflow Review Order

The order below prioritizes adoption risk, frequency, and user irritation.

### 1. Authentication, Session, And Recovery UX

Goal: make sign-in, expired session, temporary password reset, idle timeout, logout, and network failure states clear and calm.

Primary surfaces:

- Login screen.
- Register screen.
- Temporary password reset screen.
- Idle timeout modal.
- Session-expired notices.
- Live-sync reconnect status.
- Logout action.

Core questions:

- Does a wrong password stay on the form instead of looking like an app crash?
- Does copy avoid confirming whether a SOEID exists?
- Does an expired session explain what happened without technical token language?
- Does the app clear stale data when session state is no longer valid?
- Does the user know what to do after password reset is required?
- Does a network problem feel recoverable?
- Are duplicate submits prevented?

Representative tasks:

- Sign in successfully.
- Enter wrong password.
- Continue after idle warning.
- Let idle timeout expire.
- Use temporary password reset.
- Try an expired or invalid temporary password.
- Refresh the browser with an expired session.
- Attempt login while server is unreachable.

Exit criteria:

- All terminal session states return the user to a stable sign-in or reset state.
- Error messages are actionable, non-technical, and non-enumerating.
- No stale authenticated data remains visible after session loss.

### 2. First Landing And Orientation

Goal: make the first authenticated screen explain where the user is, which space is active, and what the next useful action is.

Primary surfaces:

- Topbar.
- Space switcher.
- Current user display.
- Connection status.
- Deliverables default route.
- Empty-state content.

Core questions:

- Does the user understand which space they are in?
- Is the default route the best first screen for most users?
- Is the create action obvious without being visually noisy?
- Are admin-only routes hidden or explained appropriately?
- Does the topbar compete with route content?

Representative tasks:

- Log in and identify active space.
- Switch active space.
- Return to the default deliverables view.
- Find where to create project, solution, or task.

Exit criteria:

- A new user can identify location, space, and next action within one screen.
- Space changes visibly refresh context.

### 3. Deliverables Overview

Goal: make the broad project and solution inventory scannable and efficient.

Primary surfaces:

- Deliverables route.
- Presets: My Items, Overdue, Blocked.
- Filters.
- Bulk actions.
- CSV menu.
- Project and solution modal entry points.

Core questions:

- Is the broad table showing the right columns for overview work?
- Are Project and Solution types visible and understandable?
- Are filters discoverable but not overwhelming?
- Are presets faster than manual filtering?
- Can a user reach project or solution details from the row without hunting?
- Are bulk actions clear about scope before applying?

Representative tasks:

- Find all blocked deliverables.
- Find work assigned to me.
- Open a project from the table.
- Open a solution from the table.
- Bulk update selected deliverables.
- Download or upload CSV.

Click-count targets:

- Apply common preset: 1 click.
- Open row detail from visible table: 1 click.
- Create top-level project from default screen: 2-4 actions before form entry.
- Bulk update selected visible rows: action count depends on row selection, but apply path should be 2-4 actions after selection.

Exit criteria:

- The overview supports scanning before editing.
- Broad-scope columns stay broad-scope; implementation details do not crowd the table.

### 4. Create Project, Solution, And Task

Goal: make creation flows predictable with the fewest necessary steps.

Primary surfaces:

- Topbar Create menu.
- Project modal.
- Solution modal.
- Task picker.
- Task form inside solution.
- Required-field indicators.

Core questions:

- Why does creating a project, solution, or task start in different places?
- Is the Create menu the right primary entry point?
- Does creating a task require too much context switching?
- Are required fields obvious before submit?
- Can defaults reduce form work without hiding important choices?
- Does the user return to the right context after save?

Representative tasks:

- Create a project.
- Create a solution under an existing project.
- Create a task under an existing solution.
- Create a task while already viewing a solution.

Click-count targets:

- Create project from default route: 2 actions before field entry.
- Create solution from default route: 2-3 actions before field entry.
- Create task when solution context is known: 1-2 actions before field entry.
- Create task when solution context is unknown: picker is acceptable, but should not exceed 3 actions before field entry.

Exit criteria:

- Creation entry points are consistent.
- Context-aware creation avoids asking for data the UI already knows.

### 5. Edit Project, Solution, And Task Details

Goal: make editing clear, local, and safe.

Primary surfaces:

- Project modal.
- Solution modal tabs: Details, Phases, Tasks, Activity.
- Task form.
- Delete confirmation.

Core questions:

- Does the modal title and submit button clearly distinguish create vs edit?
- Are tabs organized by user mental model rather than data model?
- Are destructive actions visually separate from save actions?
- Are delete confirmations specific enough?
- Does reset mean reset unsaved edits or clear the record?
- Does activity help users understand what changed?

Representative tasks:

- Edit project status.
- Edit solution phase.
- Add or remove solution phase.
- Edit task assignee.
- Delete a project, solution, or task.

Exit criteria:

- Users can edit without losing orientation.
- Destructive actions require clear confirmation.

### 6. Tasks Workbench

Goal: make focused task execution fast for high-volume users.

Primary surfaces:

- Tasks route.
- Search and filters.
- Presets.
- Saved views.
- Bulk actions.
- Side drawer.
- Keyboard shortcuts.

Core questions:

- Is this route the best place for daily execution?
- Are presets and filters duplicative or complementary?
- Are saved views understandable?
- Does the drawer support fast review and edit without route churn?
- Are keyboard shortcuts discoverable without clutter?
- Are selected rows and bulk scope obvious?

Representative tasks:

- Find my assigned tasks.
- Filter blocked tasks.
- Save and reuse a view.
- Edit a task in the drawer.
- Bulk update status or assignee.

Click-count targets:

- Apply a common preset: 1 click.
- Search and open a visible task: 1 text entry plus 1 click.
- Edit selected task from drawer: 1 click to open, 1 save after changes.
- Apply saved view: 1-2 actions.

Exit criteria:

- Daily task work is faster here than in the broad deliverables table.
- Bulk action scope is always visible.

### 7. Planning Board

Goal: make allocation and month planning understandable and resilient.

Primary surfaces:

- Planning route.
- Month selector.
- Board.
- Allocation drawer.
- Planning modal.
- Roster and capacity cues.

Core questions:

- Does the user understand what month they are editing?
- Is drag/drop behavior obvious?
- Are capacity limits visible before over-allocation?
- Is undo or recovery available for mistakes?
- Does changing month preserve orientation?
- Are unassigned and overloaded states clear?

Representative tasks:

- Switch month.
- Assign work to a person.
- Reassign work.
- Review overloaded team or person.
- Open allocation details.

Exit criteria:

- Users understand current planning period and allocation impact.
- Stale month or stale board state is not visible after changes.

### 8. Dashboard, PM Command Center, Gantt, Kanban, And Calendar

Goal: make review surfaces answer distinct questions instead of duplicating each other.

Primary surfaces:

- Dashboard.
- PM Command Center.
- Gantt.
- Kanban.
- Calendar.

Core questions:

- What question does each view answer?
- Are any views redundant?
- Does each view have a clear default scope?
- Can users drill down from insight to action?
- Are date windows and filters obvious?
- Do visual states match the same status definitions used elsewhere?

Representative tasks:

- Identify at-risk projects.
- See upcoming due dates.
- Review timeline overlap.
- Move work through status.
- Open a project or solution from an insight.

Exit criteria:

- Each review surface has a distinct purpose.
- Drill-down paths are obvious and low-friction.

### 9. Team Capacity

Goal: make capacity setup and review clear for managers and admins.

Primary surfaces:

- Team Capacity route.
- Capacity user form.
- Roster list.
- Filters.
- Upload/download roster.

Core questions:

- Is this route admin setup, ongoing planning, or both?
- Are capacity units clear?
- Is deactivation visually distinct from deletion?
- Are upload/download actions in the right place?
- Are filters enough to find people quickly?

Representative tasks:

- Find a team member.
- Update capacity.
- Deactivate a member.
- Download roster.
- Upload roster.

Exit criteria:

- Capacity changes feel safe and auditable.
- Managers can find and update users without table hunting.

### 10. Spaces, Access, And Governance

Goal: make space boundaries, membership, and admin controls understandable and safe.

Primary surfaces:

- Space switcher.
- Spaces route.
- Access route behavior within Spaces.
- Space create modal.
- Add member modal.
- Directory modal.
- Global admin controls.
- Password reset and service-account token controls.

Core questions:

- Does the user understand the difference between switching spaces and administering spaces?
- Are global admin controls visibly separate from space admin controls?
- Are archived spaces clearly read-only where appropriate?
- Are password reset and token issuance warnings strong enough?
- Is the current active space always clear before mutation?

Representative tasks:

- Switch active space.
- Create a space.
- Add a member.
- Change member role.
- Issue password reset.
- Generate service-account API token.
- Revoke API token.

Exit criteria:

- Space context is never ambiguous before a write.
- High-risk admin actions are clearly scoped and confirmed.

### 11. Import, Export, Bulk Edit, And Recovery

Goal: make high-impact batch workflows safe, understandable, and recoverable.

Primary surfaces:

- CSV menu.
- Upload modal.
- Download actions.
- Bulk action controls.
- Import result messages.
- Error summaries.

Core questions:

- Does the user know what entity type they are importing or exporting?
- Is the template easy to find?
- Are partial failures summarized clearly?
- Are failed rows actionable?
- Are bulk edits reversible or at least clearly scoped?
- Does the UI prevent applying hidden or stale selections?

Representative tasks:

- Download project CSV.
- Upload solution CSV.
- Review partial import errors.
- Bulk update statuses.
- Clear bulk selection.

Exit criteria:

- Batch workflows name their scope before execution.
- Partial failures tell the user what to fix next.

### 12. Mobile And Responsive UX

Goal: ensure core review and recovery workflows are usable on smaller screens.

Primary surfaces:

- Login and reset screens.
- Navigation.
- Deliverables table.
- Tasks workbench.
- Planning route.
- Modals.
- Space switcher.

Core questions:

- Can users sign in and recover session on mobile?
- Does navigation remain usable?
- Do tables overflow predictably?
- Are modal actions reachable without awkward scrolling?
- Do filters stack in a usable order?

Representative tasks:

- Sign in.
- Open deliverables.
- Open a project or solution.
- Use space switcher.
- Dismiss session warning.

Exit criteria:

- Mobile may be denser, but core recovery and review workflows must not be blocked.

## Workflow Inventory Worksheet

Use this worksheet during each UX pass.

```markdown
## UX Pass: <Workflow Name>

Mode: <critical daily | critical occasional | admin critical | review and insight | bulk or recovery>

### User Goal

As a <role>, I need to <goal>, so that <outcome>.

### Current Entry Points

- Primary:
- Secondary:
- Hidden/deep link:

### Current Path

1.
2.
3.

Current action count:
Expected action count:
Assessment:

### Friction Findings

- Severity / priority: finding.

### Proposed UX Changes

- Change:
- User impact:
- Before count:
- After count:
- Risk:

### Validation Plan

- Manual path:
- Desktop viewport:
- Mobile viewport:
- Automated tests:

### Closure Notes

- Changed:
- Deferred:
- Remaining risk:
```

## Baseline UX Questions For Every Pass

- What is the user trying to finish?
- Is this workflow too slow for how often it happens?
- Is the primary action visible at the moment the user needs it?
- Is the safest action also the clearest action?
- Is the UI asking for information it already knows?
- Is the user forced to leave context to complete related work?
- Does the user know what changed after saving?
- Does the user know what to do after an error?
- Does the workflow survive refresh, space switch, session expiry, and network failure?
- Is the same concept named consistently across routes?
- Are advanced controls taking space from common controls?
- Is destructive power visually and procedurally separated from routine work?

## Review Output Requirements

Each UX pass should produce:

- Workflow name and user role.
- Current path and action count.
- Target path and expected action count.
- Findings by severity.
- Recommendation list.
- Validation plan.
- Closure ledger after implementation.

Do not close a UX pass with only subjective comments. The review must include at least one observable artifact: action count, screenshot note, route map, test case, or before/after workflow comparison.

