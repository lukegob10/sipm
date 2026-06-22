# SIPM Front-End UX Phased Implementation Plan

Purpose: provide a focused, view-by-view implementation plan for bringing SIPM closer to the UI/UX quality bar without attempting a broad one-shot redesign.

This plan treats the quality bar as the product standard:

- Linear-like operational density for product UI.
- Stripe Docs-like clarity for information-heavy views.
- Airtable-like structure for tables, directories, and admin surfaces.
- Crisp, dense, clean, intuitive, purpose-built, high-signal, and uncluttered screens.

The work should move in small passes. Each pass must leave the product more consistent, more measurable, and easier to validate than it was before.

## Current Assessment

SIPM is directionally aligned with the target bar, but not uniformly aligned across every view.

Strong existing foundations:

- Compact typography tokens and route-level styling exist.
- Work, Insight, and Admin navigation groups are clear.
- Deliverables, Tasks Workbench, Dashboard, Gantt, Program Dashboard, and Planning already use dense operational patterns.
- Many interactions use inline feedback instead of alerts.
- Route-local modules and frontend contract tests already encode some UX decisions.
- The existing stepwise UX process already supports workflow-based review, action counts, and validation.

Primary gaps:

- The quality bar is not yet enforced as a shared acceptance contract across every route.
- Admin and governance surfaces still carry more card, hero, and generic dashboard language than the bar prefers.
- Some surfaces rely on horizontal overflow rather than a deliberately designed small-screen workflow.
- Loading and performance expectations are present but not measured consistently.
- Visual language is close but still softened by heavy shadows, high radii, gradients, and card-heavy grouping in places.
- The app has several distinct review surfaces, but their purpose boundaries need to be sharper.

## Operating Rules

Each phase should be scoped to a small set of routes or one shared system concern.

Do not run a phase as a broad visual polish task. Every phase must include:

- User goal.
- Current path and action count for representative tasks.
- Visual audit against the quality bar.
- Interaction audit against the quality bar.
- Responsive audit for desktop and mobile.
- Performance and loading-state audit where the view depends on data.
- Focused implementation changes.
- Focused tests or screenshot checks.
- Closure notes with remaining UX debt.

Do not merge a phase unless the view has:

- Clear primary action hierarchy.
- Stable layout under realistic data.
- No decorative emptiness.
- No unexplained loading, empty, error, or permission state.
- Text that fits in controls, table cells, pills, modals, and mobile widths.
- Consistent use of status, RAG, project, solution, task, and space display tokens.
- A documented reason for any retained complexity.

## Shared Acceptance Criteria

These criteria apply to every route touched by a phase.

### Density And Layout

- Route headers should be compact and useful.
- Filters, presets, actions, and state summaries should be close to the work they affect.
- Cards should be used for repeated entities, modals, or framed tools, not as generic page decoration.
- Nested cards should be removed unless the nesting communicates real hierarchy.
- Route panels should avoid large empty zones and oversized padding.
- Tables and grids should define stable column behavior for real data.

### Visual System

- Border radii should default to the shared route radius, currently 8px, unless a component has a reason to differ.
- Shadows should be restrained and functional.
- Gradients should be reduced where a flat tokenized surface communicates hierarchy just as well.
- Accent color should communicate state, selection, or action priority.
- Status and RAG colors should remain consistent across all routes.
- Avoid beige, parchment, muted newspaper, and generic washed-out neutral styling.

### Interaction

- Primary actions should be visible when needed and secondary actions should not compete.
- Common non-destructive actions should avoid unnecessary modal or route churn.
- Destructive and cross-space actions should be explicit, scoped, and confirmed.
- Feedback should land near the action that produced it.
- Keyboard and focus behavior should be verified for modals, menus, drawers, and tables.

### Responsiveness

- Desktop layouts should optimize scanning and repeated use.
- Mobile layouts may preserve dense data via horizontal scroll only when the workflow remains coherent.
- Core recovery workflows must work on mobile: sign in, reset, switch space, open deliverables, open details, dismiss session warnings.
- Sticky controls should not trap content or obscure primary actions.

### Performance

- Loading states should reserve enough structure to avoid jarring layout shifts.
- Expensive data surfaces should define pagination, filtering, virtualization, or bounded rendering expectations.
- Route transitions should have visible progress or stable stale-content behavior.
- Large tables should avoid unnecessary full re-renders where incremental updates are practical.

## Phase 0: Baseline And Quality-Bar Contract

Goal: make the quality bar concrete before changing route behavior.

Scope:

- Shared UX quality bar.
- Shared style tokens.
- Route inventory.
- Existing frontend contract tests.

Tasks:

- Convert the quality bar into SIPM-specific acceptance checks.
- Build a route inventory covering Work, Insight, Admin, auth, modals, and global shell.
- Identify which existing tests already enforce the bar.
- Identify missing contract tests for visual density, loading states, mobile behavior, and purpose boundaries.
- Capture baseline screenshots for desktop and mobile for every major route.

Deliverables:

- Route-by-route baseline matrix.
- Screenshot set or screenshot notes.
- List of quality-bar acceptance criteria that should become tests.
- Prioritized implementation backlog.

Exit criteria:

- Every route has an owner phase.
- Every phase has measurable success criteria.
- No implementation starts from subjective visual preference alone.

## Phase 1: Shell, Navigation, First Landing, And Orientation

Goal: make the first authenticated screen explain location, active space, user state, connection state, and next useful action without visual noise.

Primary surfaces:

- App shell.
- Sidebar.
- Topbar.
- Space switcher.
- Current user display.
- Connection status.
- Completed visibility toggle.
- Default Deliverables route entry.

Current likely strengths:

- Work, Insight, and Admin groups are already explicit.
- Create menu is globally available.
- Space switcher is visible in the topbar.
- Completed visibility is globally controlled.

Audit questions:

- Does the topbar compete with the route content?
- Is the active space understandable before any write?
- Is the Create menu clearly primary without overpowering review tasks?
- Are admin routes visually separated enough from common work?
- Does the completed-work toggle communicate scope across views?
- Does route navigation still work cleanly on mobile?

Implementation targets:

- Tighten topbar density and visual hierarchy.
- Normalize menu, pill, and switcher styling to the shared route language.
- Ensure global state controls are grouped by user intent: create, context, view preference, account.
- Remove any leftover glyph encoding issues if they render in-browser.
- Define mobile behavior for sidebar and topbar before individual route tuning.

Validation:

- Desktop screenshot: signed in, active space selected, Deliverables open.
- Mobile screenshot: signed in shell, navigation usable, topbar controls reachable.
- Contract tests for visible active space, create menu accessibility, and completed toggle scope.

## Phase 2: Authentication, Session, And Recovery

Goal: make access and failure states clear, calm, and non-technical.

Primary surfaces:

- Login.
- Register.
- Temporary password reset.
- Idle timeout modal.
- Session-expired behavior.
- Server unreachable or network failure.

Audit questions:

- Does failed login preserve the user path without feeling like app failure?
- Does copy avoid user enumeration?
- Does expired session clear stale data and explain the next action?
- Are duplicate submits prevented?
- Does temporary password reset make the next step obvious?
- Do auth screens match the density and visual quality of the app shell?

Implementation targets:

- Tighten auth card layout and copy.
- Ensure all auth notices use consistent role/status semantics.
- Add clear busy states for submit actions.
- Validate mobile height and keyboard behavior.
- Align auth visuals with the same crisp neutral/accent system as the app.

Validation:

- Manual paths: success, wrong password, expired temporary password, duplicate submit, network failure.
- Mobile screenshot: login and reset.
- Focus tests around idle modal and reset flow.

## Phase 3: Deliverables Overview

Goal: make the broad project and solution inventory scannable, fast, and useful before editing.

Primary surfaces:

- Deliverables route.
- Filters.
- Quickstart or empty-state card.
- Import/export menu.
- Project and solution row actions.
- Project and solution modals launched from the table.

Audit questions:

- Does the table show the right broad-scope columns?
- Are project and solution types visually obvious without taking too much space?
- Are filters discoverable but not noisy?
- Are presets needed here, or should this stay a broad inventory surface?
- Can users open details in one obvious action?
- Does import/export scope stay clear?

Implementation targets:

- Reduce any leftover card-heavy or empty intro states.
- Make filters dense and table-aligned.
- Normalize row action icons, tooltips, and hit targets.
- Ensure detail links are text-first and not visually noisy.
- Define behavior for large inventories: pagination, bounded rendering, or virtualized table plan.

Representative action targets:

- Open visible project or solution: 1 action.
- Open Create menu: 1 action.
- Start create project: 2 actions before form entry.
- Start create solution: 2-3 actions before form entry.
- Download/upload scoped CSV: clear scope within 2-3 actions.

Validation:

- Desktop and mobile screenshots with realistic row volume.
- Contract tests for table columns, row action accessibility, and import/export menu scope.
- Performance note for large row counts.

## Phase 4: Create And Edit Project, Solution, And Task

Goal: make entity creation and editing predictable, local, and safe.

Primary surfaces:

- Topbar Create menu.
- Project modal.
- Solution modal.
- Task picker.
- Task form.
- Solution tabs: Details, Phases, Tasks, Documents, Activity.
- Delete confirmation modal.

Audit questions:

- Are create and edit modes unmistakable?
- Does the UI ask for data it already knows?
- Does creating a task from inside a solution avoid unnecessary picking?
- Are required fields visible before submit?
- Are destructive actions visually separated from saves?
- Does Reset mean reset unsaved edits or clear the form, and is that clear?
- Does Activity help the user understand what changed?

Implementation targets:

- Normalize modal headers, sticky footers, tabs, and status messages.
- Group required fields before optional fields.
- Make context-aware task creation the fastest path.
- Improve delete confirmation copy with exact entity names and scope.
- Ensure all modal content scrolls without hiding final actions.

Representative action targets:

- Create project from default route: 2 actions before field entry.
- Create solution from default route: 2-3 actions before field entry.
- Create task with known solution context: 1-2 actions before field entry.
- Edit status from detail modal: 1 open action plus field change and save.

Validation:

- Modal screenshot set for create/edit project, solution, task.
- Keyboard focus test for opening, tabbing, submitting, closing.
- Contract tests for context-aware labels and destructive confirmation content.

## Phase 5: Tasks Workbench

Goal: make daily task execution faster than the broad Deliverables table.

Primary surfaces:

- Tasks route.
- KPI strip.
- Presets.
- Saved views.
- Filter row.
- Task table.
- Bulk action toolbar.
- Task editor modal.

Current likely strengths:

- Presets and saved views exist.
- Filters are table-aligned.
- Bulk action feedback is inline.
- Project and solution context links reuse existing modals.

Audit questions:

- Are presets and filters complementary, or duplicative?
- Is the selected saved view state understandable?
- Is bulk selection scope always visible?
- Does the editor support fast review and edit without route churn?
- Are keyboard shortcuts discoverable only where useful?
- Do KPI cards add operational value or visual clutter?

Implementation targets:

- Tighten the KPI strip into a compact summary row if cards feel heavy.
- Make preset state and saved view state visibly distinct.
- Ensure selected row count and bulk scope cannot be missed.
- Keep table density high while allowing names to wrap predictably.
- Define large-row performance expectations.

Representative action targets:

- Apply common preset: 1 action.
- Search and open visible task: text entry plus 1 action.
- Edit task from table: 1 open action, field changes, 1 save.
- Apply saved view: 1-2 actions.
- Bulk update after selection: 2-4 actions.

Validation:

- Desktop screenshot with dense data and selected rows.
- Mobile screenshot of filter/table behavior.
- Unit tests for filter normalization, saved views, bulk feedback, and editor focus.

## Phase 6: Planning And Work Allocation

Goal: make allocation, month planning, and capacity impact understandable and recoverable.

Primary surfaces:

- Planning route.
- Work Allocation Board.
- Month or planning-window controls.
- People and teams.
- Backlog.
- Drag/drop zones.
- Allocation detail panel or modal.

Audit questions:

- Does the user know which planning window or month they are editing?
- Are drag/drop targets obvious before the user drags?
- Are capacity limits visible before over-allocation?
- Is undo or recovery available for mistakes?
- Does changing planning period preserve orientation?
- Are unassigned, overloaded, completed, and hidden states clear?

Implementation targets:

- Make current planning period a first-class visible state.
- Tighten toolbar cards and reduce explanatory bulk.
- Separate common planning actions from instructional help.
- Ensure capacity signals are consistent across Planning, Dashboard, and Team Capacity.
- Validate drag/drop and keyboard alternatives.

Representative action targets:

- Switch planning period: 1-2 actions.
- Assign selected work to visible person/team: 1-2 actions.
- Reassign existing allocation: 1 drag/drop or equivalent keyboard path.
- Open allocation details: 1 action.

Validation:

- Screenshot with empty board, normal board, overloaded board.
- Interaction test for move versus duplicate allocation behavior.
- Mobile screenshot proving the workflow is coherent or explicitly desktop-first.

## Phase 7: Review And Insight Surfaces

Goal: make each review surface answer a distinct question without duplicating the others.

Primary surfaces:

- PM Command Center.
- Dashboard.
- Program Dashboard.
- Gantt.
- Kanban.
- Calendar.

View purposes:

- PM Command Center: portfolio health, attention, and immediate management decisions.
- Dashboard: configurable solution and capacity summaries.
- Program Dashboard: hierarchy and program-level delivery structure.
- Gantt: timeline overlap and sequence.
- Kanban: status flow and movement.
- Calendar: date-based due work and milestones.

Audit questions:

- What question does this view answer better than every other view?
- Does the route title match the user goal?
- Is the default scope obvious?
- Can users drill from insight to action in one obvious step?
- Are date windows, filters, and selected programs visible without crowding?
- Do visual states match the same definitions used elsewhere?

Implementation targets:

- Write one explicit purpose statement per view and enforce it through layout.
- Remove redundant metrics or sections that blur route purpose.
- Normalize table header, row, pill, and drilldown styling across all insight routes.
- Reduce generic dashboard card styling where tables or compact summary rows are more useful.
- Ensure each insight route has a direct path back to the editable object.

Validation:

- One screenshot per insight view with realistic data.
- Route-purpose matrix showing no unowned duplicate purpose.
- Contract tests for drilldown links and shared display tokens.
- Manual task tests: identify at-risk item, open details, change status if appropriate.

## Phase 8: Team Capacity

Goal: make capacity setup and ongoing capacity review safe, scannable, and auditable.

Primary surfaces:

- Team Capacity route.
- Capacity user form.
- Roster table.
- Filters.
- Upload/download roster.

Audit questions:

- Is this admin setup, ongoing planning review, or both?
- Are capacity units clear everywhere?
- Is deactivation distinct from deletion?
- Are upload/download actions in the correct scope?
- Can a manager find and update a person without table hunting?

Implementation targets:

- Clarify the route purpose through layout, not explanatory copy.
- Separate edit form, filters, and roster actions by intent.
- Make capacity unit display consistent with Planning and Dashboard.
- Use inline feedback near save, deactivate, upload, and download actions.
- Review row density and search behavior with realistic roster sizes.

Representative action targets:

- Find member: search/filter plus 1 row selection.
- Update capacity: edit value plus 1 save.
- Deactivate member: 1 action plus scoped confirmation if risk requires it.
- Upload/download roster: clear scope within 2-3 actions.

Validation:

- Desktop and mobile screenshots.
- Contract tests for inline feedback and deactivation language.
- Manual import/export partial failure path.

## Phase 9: Spaces, Access, And Governance

Goal: make workspace boundaries, membership, global admin controls, and automation controls unmistakably scoped and safe.

Primary surfaces:

- Space switcher.
- Spaces route.
- Space directory modal.
- Space create modal.
- Add member modal.
- Platform access area.
- Service account tokens.
- Agent approvals.
- Password reset issuance.

Current likely risk:

This area contains more hero/card language than the bar prefers. It also carries high-risk admin actions where ambiguity is expensive.

Audit questions:

- Can a user clearly distinguish switching active space from administering spaces?
- Are global admin controls visually separate from space admin controls?
- Are archived spaces clearly read-only?
- Are token and password reset warnings strong enough?
- Does every write name the affected space or platform scope?
- Are service account and agent approval controls too visually similar to routine actions?

Implementation targets:

- Replace hero-like admin blocks with compact operational sections.
- Make scope labels persistent and close to write actions.
- Use stronger confirmation copy for password reset, API token, revocation, and global access changes.
- Normalize directory cards or convert to a denser list/table where scanning matters more.
- Ensure admin empty states tell the next action without marketing-style copy.

Representative action targets:

- Switch active space: open switcher, select space.
- Create space: 2 actions before field entry.
- Add member to active space: open form, enter SOEID, select role, submit.
- Issue password reset: select target, confirm scope, generate.
- Generate token: name token, confirm scope, generate, copy result.

Validation:

- Screenshots for active space, selected directory space, platform access, service account token result.
- Contract tests for scope labels and dangerous action confirmations.
- Manual permission-loss and archived-space checks.

## Phase 10: Import, Export, Bulk Edit, And Recovery

Goal: make high-impact batch workflows explicit, scoped, and recoverable.

Primary surfaces:

- CSV menu.
- CSV upload modal.
- Download actions.
- Template actions.
- Import result messages.
- Bulk edit controls in Tasks Workbench.
- Any future deliverables bulk controls.

Audit questions:

- Does the user know exactly which entity type is being imported or exported?
- Is the template easy to find?
- Are partial failures summarized clearly?
- Are failed rows actionable?
- Are hidden or stale selections prevented?
- Does bulk apply summarize scope before mutation?

Implementation targets:

- Normalize import/export labels and modal titles.
- Add structured partial failure summaries where needed.
- Keep bulk actions near selected counts.
- Ensure destructive or broad bulk actions require confirmation.
- Make upload result messages specific enough to act on.

Representative action targets:

- Download template: 2-3 actions.
- Upload CSV: choose file, upload, read result.
- Review partial failure: result shows failed count and next fix.
- Bulk update selected tasks: selection plus 2-4 actions.

Validation:

- Manual partial-failure import path.
- Contract tests for scoped modal title and result message structure.
- Screenshot of bulk toolbar with selected rows.

## Phase 11: Mobile And Responsive Coherence

Goal: make the mobile experience intentionally constrained rather than accidentally compressed.

Primary surfaces:

- Auth and reset.
- Shell navigation.
- Topbar.
- Space switcher.
- Deliverables.
- Tasks Workbench.
- Planning.
- Modals.

Audit questions:

- Which workflows must be usable on mobile?
- Which workflows are acceptable as review-only on mobile?
- Do tables overflow predictably?
- Are sticky modal footers reachable?
- Do filters stack in the order users need?
- Does text still fit in buttons, pills, cells, and headers?

Implementation targets:

- Define mobile support levels per route: full workflow, review only, or desktop-first.
- For full workflow routes, create mobile-specific layout rules beyond horizontal scrolling.
- For review-only routes, preserve readable scanning and drilldown.
- Verify modals with small viewport heights.
- Ensure no topbar/sidebar overlap.

Validation:

- Mobile screenshot set for required workflows.
- Playwright viewport checks for no obvious overlap.
- Manual path: sign in, switch space, open deliverables, open details, save a small edit.

## Phase 12: Performance, Loading, And Large Data

Goal: make perceived speed and large-data behavior explicit parts of the UX.

Primary surfaces:

- Deliverables table.
- Tasks Workbench table.
- Program Dashboard grid.
- Gantt.
- Planning board.
- Space directory and members.
- Team Capacity roster.

Audit questions:

- What row count is each surface expected to handle?
- Does loading preserve layout or collapse the route?
- Does filtering feel instant under realistic data?
- Are route transitions stable?
- Are there unnecessary full renders after small edits?
- Is there a need for pagination, virtualization, or server-side filtering?

Implementation targets:

- Define expected data volume per route.
- Add measurable performance targets where practical.
- Replace vague loading text with route-appropriate loading states.
- Add pagination or virtualization plans for surfaces that exceed browser-comfortable rendering.
- Keep optimistic updates only where rollback is clear.

Candidate targets:

- Route switch visible feedback under 150ms for already-loaded routes.
- Filter feedback under 100ms for moderate in-memory datasets.
- Large tables should have a bounded rendering strategy before scaling beyond a few thousand rows.
- Loading states should avoid major layout shift.

Validation:

- Manual large-data smoke scenario.
- Render timing notes or lightweight performance instrumentation.
- Tests for stale-state recovery after failed refresh.

## Suggested Execution Order

1. Phase 0: Baseline And Quality-Bar Contract.
2. Phase 1: Shell, Navigation, First Landing, And Orientation.
3. Phase 3: Deliverables Overview.
4. Phase 4: Create And Edit Project, Solution, And Task.
5. Phase 5: Tasks Workbench.
6. Phase 7: Review And Insight Surfaces.
7. Phase 6: Planning And Work Allocation.
8. Phase 8: Team Capacity.
9. Phase 9: Spaces, Access, And Governance.
10. Phase 10: Import, Export, Bulk Edit, And Recovery.
11. Phase 2: Authentication, Session, And Recovery.
12. Phase 11: Mobile And Responsive Coherence.
13. Phase 12: Performance, Loading, And Large Data.

Rationale:

- Start with shared acceptance criteria so every later pass uses the same bar.
- Fix shell and orientation early because every view inherits that context.
- Improve the highest-frequency work surfaces before admin and review edge cases.
- Defer broad mobile and performance passes until route intent is sharper, while still checking mobile and performance within each route phase.

## Per-Phase Work Template

Use this template for every phase.

```markdown
## Phase <N>: <Name>

### Goal

As a <role>, users need to <goal>, so that <outcome>.

### Scope

- Routes:
- Components:
- Shared modules:
- Out of scope:

### Baseline

- Desktop screenshot:
- Mobile screenshot:
- Current path:
- Current action count:
- Current friction:
- Current test coverage:

### Quality-Bar Gaps

- Density:
- Hierarchy:
- Interaction:
- Visual system:
- Responsiveness:
- Performance:
- Resilience:

### Implementation Plan

- Change:
- User impact:
- Risk:
- Test:

### Validation

- Manual path:
- Desktop viewport:
- Mobile viewport:
- Unit tests:
- Contract tests:
- E2E or smoke tests:

### Closure

- Changed:
- Action count before:
- Action count after:
- Remaining UX debt:
- Next phase:
```

## View Coverage Matrix

| View or Surface | Primary Phase | Secondary Phase | Main UX Risk |
| --- | --- | --- | --- |
| Auth login/register/reset | Phase 2 | Phase 11 | Failure and recovery clarity |
| Idle/session recovery | Phase 2 | Phase 12 | Stale state and unclear next action |
| App shell/sidebar/topbar | Phase 1 | Phase 11 | Global controls competing with route work |
| Space switcher | Phase 1 | Phase 9 | Active space ambiguity |
| Deliverables | Phase 3 | Phase 10 | Broad table clutter and unclear import/export scope |
| Project modal | Phase 4 | Phase 3 | Create/edit ambiguity and destructive action placement |
| Solution modal | Phase 4 | Phase 10 | Tab density, required fields, and context preservation |
| Task form/picker | Phase 4 | Phase 5 | Asking for known context and slow creation |
| Tasks Workbench | Phase 5 | Phase 12 | Filter/preset complexity and bulk scope |
| Planning | Phase 6 | Phase 12 | Allocation impact, drag/drop clarity, large board behavior |
| PM Command Center | Phase 7 | Phase 12 | Purpose overlap with Dashboard |
| Dashboard | Phase 7 | Phase 12 | Generic dashboard cards and configurable complexity |
| Program Dashboard | Phase 7 | Phase 12 | Wide grid behavior and purpose clarity |
| Gantt | Phase 7 | Phase 12 | Timeline scanning and date window clarity |
| Kanban | Phase 7 | Phase 12 | Status movement and drilldown clarity |
| Calendar | Phase 7 | Phase 11 | Date scanning and small-screen behavior |
| Team Capacity | Phase 8 | Phase 10 | Admin versus planning purpose ambiguity |
| Spaces/Governance | Phase 9 | Phase 11 | Scope ambiguity and high-risk admin actions |
| Import/export | Phase 10 | Phase 12 | Partial failure recovery and entity scope |
| Mobile behavior | Phase 11 | All phases | Accidental compression rather than designed workflows |
| Large data/performance | Phase 12 | All phases | Slow dense surfaces and layout shift |

## Implementation Discipline

Keep each implementation PR focused on one phase or one coherent slice of a phase.

Preferred PR shape:

- One route or one workflow family.
- One visual-system concern when it affects multiple views.
- Focused tests updated with the change.
- Before/after action count included in the PR description.
- Desktop and mobile screenshot notes included when layout changes.

Avoid:

- Changing all route styles in one broad polish pass.
- Mixing backend model changes with visual cleanup unless the workflow requires it.
- Adding new visual abstractions before proving they remove duplication or inconsistency.
- Treating screenshot approval as sufficient validation for workflows.

## Definition Of Done For The Full Program

The phased UX program is complete when:

- Every view in the coverage matrix has passed its primary phase.
- Shared quality-bar criteria are represented in documentation and, where practical, tests.
- Work, Insight, and Admin surfaces feel intentionally distinct but visually consistent.
- Common workflows meet their action-count targets or have documented justification.
- Dense data surfaces have explicit large-data behavior.
- Mobile support levels are documented and validated.
- Remaining UX debt is advisory rather than blocking core task completion.
