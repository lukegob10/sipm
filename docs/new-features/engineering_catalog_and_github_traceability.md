# GitHub Repo Traceability and Engineering Catalog Plan

## Summary
Make SIPM more useful for a Python/full-stack tools team by treating a `Solution` as the lightweight service/catalog record and a `Subcomponent` as the delivery work under it. Add one primary GitHub repo URL to solutions, allow subcomponents to override it only when needed, audit every change, and surface the data through existing Deliverables and Subcomponents flows instead of creating a separate engineering system.

This keeps the product in the middle ground defined by `docs/specs/product-target.md`: leadership-friendly, low-friction to maintain, and more trustworthy for teams that need delivery traceability, while also making the system directly useful to developers who need to jump from work records to code quickly.

## Product fit
- Primary audience for this enhancement:
  - developers working on Python/full-stack tools who need to know where the code lives and how a task maps to a repo
  - PMO, team leads, delegates, and engineering-adjacent operators maintaining Python/full-stack internal tool delivery
  - directors and leaders who need an engineering-aware summary without adopting a developer tool
- Primary jobs improved:
  - jump from solution or task context to the right codebase quickly
  - understand which repo a task belongs to without asking around or searching outside SIPM
  - delivery workflow traceability
  - lightweight service cataloging
  - cross-view trust between Deliverables, Subcomponents, Planning, and audit history
- Design constraint:
  - do not introduce a new `service`, `repository`, or `integration` entity for v1
  - use existing hierarchy intentionally: `Project -> Solution -> Subcomponent`

## Developer-useful outcomes
- A developer can open a solution or task and immediately know which repo to work in.
- A lead or delegate can maintain repo ownership once at the solution level instead of duplicating it on every task.
- A team can scan which solutions are mapped to code and which still lack repo traceability.
- SIPM becomes more useful during real delivery work, not just leadership review, without turning into a heavy developer platform.

## Architecture decision

### Core storage model
- Add nullable `github_repo_url` to `Solution`.
- Add nullable `github_repo_url` to `Subcomponent` as an override only.
- Do not add a GitHub URL field to `Project` in v1.
- Do not use the dormant generic `ExternalRef` model in v1.
  - The current need is repo-only, one-primary-URL, and limited to solution/subcomponent scope.
  - Explicit fields are simpler for forms, CSV, filtering, audit, and reporting.

### Why this shape
- `Solution` is the best fit for a service or tool record in the current product model.
- `Subcomponent` override handles real engineering exceptions:
  - monorepo path split by team ownership later
  - separate frontend/backend repos under one solution
  - service-to-component repo divergence
- `Project` stays portfolio-level and does not become a technical metadata bucket.

### Derived read model
- Add `effective_github_repo_url` to `SubcomponentRead`.
  - Use the subcomponent override when present.
  - Otherwise inherit the solution repo URL.
- Add `repo_source` to `SubcomponentRead` with one of:
  - `override`
  - `inherited`
  - `none`
- Keep `SolutionRead.github_repo_url` as the explicit stored value only.

## Data model and API changes

### Backend model changes
- `Solution.github_repo_url: nullable string`
- `Subcomponent.github_repo_url: nullable string`
- Keep both fields additive and nullable so existing records require no backfill to stay valid.

### Schema changes
- Add `github_repo_url` to:
  - `SolutionCreate`
  - `SolutionUpdate`
  - `SolutionRead`
  - `SubcomponentCreate`
  - `SubcomponentUpdate`
  - `SubcomponentRead`
- Add derived read-only fields to `SubcomponentRead`:
  - `effective_github_repo_url`
  - `repo_source`

### Validation rules
- Accept GitHub HTTPS repo roots only:
  - `https://github.com/org/repo`
- Normalize at write time:
  - lowercase hostname
  - strip trailing slash
  - strip trailing `.git`
- Reject:
  - non-GitHub URLs
  - issue, pull, tree, blob, actions, compare, wiki, or release subpaths
  - SSH clone strings
  - organization-only URLs
- Blank means:
  - on solution: no repo stored
  - on subcomponent: no override, inherit if solution repo exists

### Service-layer helper
- Add a backend helper dedicated to:
  - normalize GitHub repo URLs
  - validate allowed shape
  - resolve effective subcomponent repo
- Keep this logic outside route handlers so a later sync layer can reuse it.

### Migration shape
- Add one additive migration for `solutions.github_repo_url`.
- Add one additive migration for `subcomponents.github_repo_url`.
- Do not backfill existing rows.
- Existing records should read as:
  - solution repo: `null`
  - subcomponent override: `null`
  - effective subcomponent repo: derived as `null`

## UI and workflow surfaces

### Solution modal
- Add `Primary GitHub Repo` to the existing solution details form.
- Place it as a full-width field near the solution identity block:
  - after `Solution`
  - before the more operational metadata such as owner, dates, and status
- Show inline guidance:
  - `Primary repo for this solution or tool.`

### Subcomponent form
- Add `GitHub Repo Override` to the existing subcomponent form.
- Make it full-width and place it directly under `Task`.
- Show helper text:
  - `Leave blank to inherit the solution repo.`
- When blank, show a muted preview:
  - `Inherited repo: https://github.com/org/repo`
  - if none exists: `No solution repo set`
- Show a compact source label from `repo_source` when editing an existing task.

### Deliverables engineering lens
- Do not add a new navigation item in v1.
- Extend the existing Deliverables route with a new `Engineering` preset.
- Implement it as a master-table render profile, not a separate screen.
- When `Engineering` is active:
  - show solution rows only
  - show a `Repo` column
  - keep Project and Solution names as their current navigable text behavior
  - render repo as an external link opening GitHub in a new tab
  - favor columns:
    - Type
    - Project
    - Solution
    - Repo
    - Owner
    - Status
    - Due
    - FTE-Months
    - RAG
- Add a `Has Repo` filter for the engineering preset.
- Add a `Missing Repo` discovery path through the same preset so teams can close traceability gaps quickly.
- Do not expose repo editing inline in the table; keep editing in the modal forms.
- Render the repo cell as a compact external text link with an outbound affordance, not as a new chip type.
- Keep the existing `Type` chip behavior unchanged.

### Subcomponents Workbench
- Do not add a new GitHub management panel in v1.
- Add repo context only where it improves traceability:
  - in the quick-edit drawer or contextual header
  - as a compact external link using `effective_github_repo_url`
  - with a source hint when the value is inherited
- Keep the workbench focused on task maintenance, not catalog browsing, but make the repo obvious enough that a developer can jump from task to code without leaving the task context blind.

## Permissions and access
- Keep edit permissions aligned to the current CRUD model:
  - create/update/import repo URLs requires `space_admin`
  - read visibility follows current authenticated space-scoped access rules
- Keep audit read access aligned to the current audit route:
  - audit history remains `space_admin` scoped unless the broader audit model changes later
- Do not add a special GitHub permission or role in v1.

## Audit, logging, and traceability

### Audit behavior
- Log all create, update, clear, and delete-equivalent changes to `github_repo_url` through existing `log_changes`.
- Track these fields explicitly:
  - `github_repo_url` on solution
  - `github_repo_url` on subcomponent
- Do not create a special GitHub audit table in v1.

### Visibility of logged changes
- Solution repo changes should appear automatically in the existing solution `Activity` tab because it already reads the audit API.
- Do not add a new subcomponent activity UI in v1.
- Subcomponent repo changes remain accessible through the existing audit endpoints and can be surfaced later if usage proves strong.

### Why this is enough for v1
- It preserves one logging path across the system.
- It keeps the user-facing experience light.
- It satisfies the requirement to track and log repo ownership and changes without adding a new admin workflow.

## Cross-view consistency and refresh behavior
- Treat repo URL updates as connected-view changes, not local form-only metadata.
- On solution repo changes:
  - invalidate the existing `solutions` space cache scope
  - broadcast the existing `solutions` realtime channel
- On subcomponent repo override changes:
  - invalidate the existing `subcomponents` space cache scope
  - broadcast the existing `subcomponents` realtime channel
- The Deliverables engineering preset should derive from the same refreshed solution data as the rest of Deliverables, not from a separate cached store.
- The Subcomponents Workbench repo context should derive from refreshed subcomponent reads plus inherited solution values, so a repo update does not require manual screen reconciliation.

## CSV and bulk maintenance

### CSV export/import updates
- Add `github_repo_url` to solution CSV export/import.
- Add `github_repo_url` to subcomponent CSV export/import as the override field.
- Leave project CSV unchanged.

### Template updates
- Update the downloadable solution CSV template to include `github_repo_url`.
- Add a downloadable subcomponent template when subcomponent CSV actions are exposed in the UI.
- Until then, the backend route remains available and the field contract should still be documented.

### Import behavior
- Run the same normalization and validation rules during CSV import as modal form entry.
- Solution CSV blank `github_repo_url`:
  - clears the stored repo URL
- Subcomponent CSV blank `github_repo_url`:
  - clears the override and falls back to inherited solution repo
- Reject invalid rows with clear import errors instead of silently dropping malformed URLs.

### Why this matters
- PMO and tech leads can bulk-load or bulk-correct repo links without hand-editing many records.
- Developers benefit because the maintained repo links become visible in the same work surfaces they already use.
- This supports real engineering maintenance while staying aligned to low-friction data entry.

### UI rollout for CSV
- Phase 1 and 2 do not need a new CSV control.
- Reuse the existing Deliverables import/export menu when repo support is added to solution CSV.
- Add subcomponent CSV actions to that same menu only in Phase 3, once the repo override model is stable enough to justify bulk maintenance from the main UI.

## Implementation phases

### Phase 1: Foundation
- Add explicit repo URL fields to solution and subcomponent models and schemas.
- Add normalization, validation, inheritance, and audit logging.
- Add solution and subcomponent form support.
- Add API tests and form contract tests.
- Keep this phase additive and migration-safe with no behavior change outside the edited forms and reads.

### Phase 2: Engineering catalog lens
- Add Deliverables `Engineering` preset.
- Add repo column and `Has Repo` filter.
- Add repo context to Subcomponents Workbench.
- Keep all catalog behavior read-oriented.
- Do not add new saved-view or preset complexity outside the Deliverables route.
- Treat this phase as the point where the feature becomes directly developer-useful, not just admin-maintainable.

### Phase 3: Scale-up maintenance
- Add CSV import/export support for repo URLs.
- Ensure solution activity clearly surfaces repo changes.
- Add targeted docs or inline help for inheritance behavior.
- Expose subcomponent CSV actions in the existing Deliverables import/export menu only if the bulk-maintenance case is still justified after Phase 2.

### Phase 4: Future sync-ready extensions
- Consider optional GitHub sync only after manual repo maintenance proves valuable.
- Candidate later additions:
  - default branch awareness
  - README or runbook link derivation
  - release visibility
  - open PR signal
- Do not add these in v1.

## Explicit non-goals
- No GitHub OAuth or token management in v1.
- No webhook processing in v1.
- No PR, branch, workflow, release, or deployment tracking in v1.
- No new top-level `Engineering Catalog` route in v1.
- No project-level repo URL in v1.
- No migration to `ExternalRef` in v1.
- No monorepo path-level tracking in v1.
- No separate engineering auth, token vault, or GitHub connection management UI in v1.

## Test plan

### Backend tests
- solution create/update accepts valid repo URL and returns normalized value
- solution rejects invalid GitHub repo URL
- subcomponent create/update accepts override repo URL and returns normalized value
- subcomponent rejects invalid override repo URL
- subcomponent derived `effective_github_repo_url` inherits from solution when override is blank
- subcomponent derived `repo_source` reports `override`, `inherited`, or `none` correctly
- clearing a subcomponent override reverts to inherited repo
- audit rows are created for solution and subcomponent repo field changes
- CSV imports for solutions and subcomponents validate and normalize repo URLs correctly

### Frontend contract tests
- solution modal includes `Primary GitHub Repo`
- subcomponent form includes `GitHub Repo Override`
- inherited preview appears correctly when override is blank
- Deliverables `Engineering` preset renders repo column and `Has Repo` behavior
- repo links open externally while project and solution names keep their current drill-down behavior
- workbench quick-edit context renders effective repo without expanding the drawer into a new GitHub console
- solution and subcomponent repo changes trigger the same connected-view refresh behavior already used by their existing routes

### Manual acceptance scenarios
- create a solution with a repo URL and confirm it is visible in the solution modal and Deliverables engineering preset
- create a subcomponent with no override and confirm it inherits the solution repo
- add a subcomponent override and confirm only that task changes
- clear the override and confirm inheritance returns
- import solutions with repo URLs by CSV and confirm values normalize consistently
- open the solution `Activity` tab and confirm repo field changes are logged cleanly
- update a solution repo and confirm the Deliverables engineering preset reflects the change without manual filter-reset or cross-screen reconciliation
- update a subcomponent override and confirm the Subcomponents Workbench context refreshes consistently
- from a subcomponent in the Workbench, open the repo link and confirm a developer can reach the correct GitHub repo in one click

## Assumptions and defaults
- GitHub only in v1.
- HTTPS repo URL only in v1.
- `Solution` is the catalog anchor.
- `Subcomponent` override is exception-only and blank means inherit.
- Deliverables remains the catalog surface; no new route is introduced in v1.
- Existing audit infrastructure remains the single source of change history.
- Existing dormant `ExternalRef` remains in the codebase untouched until a real multi-provider or multi-link requirement exists.
- Existing solution and subcomponent realtime/cache patterns are reused rather than creating a new refresh channel for repo metadata.
