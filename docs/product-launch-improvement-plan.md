# SIPM Product Launch Improvement Plan

Date: 2026-07-09

## Executive Summary

SIPM has a stronger technical base than a typical prototype. It already has authentication, space isolation, audit logging, live refresh, telemetry, capacity, dashboards, import/export, tests, CI, Docker packaging, and an agent-facing API surface. The main product problem is not basic application wiring. The main product problem is that SIPM is still shaped like a specialized internal portfolio/delivery tool, not a configurable project-management product that many businesses can adopt without learning SIPM-specific concepts.

The recommended direction is to evolve SIPM into a multi-tenant work-management platform with configurable work types, workflows, fields, views, permissions, notifications, integrations, billing, onboarding, and operational guarantees. The existing `space -> program -> project -> solution -> task` hierarchy should be treated as one default template, not the universal product model.

## Current Product Shape

The current application model is:

- `Space`: top-level data boundary and collaboration workspace.
- `Program`: portfolio grouping above projects.
- `Project`: initiative under a program.
- `Solution`: deliverable under a project, with RAG, phase, owner, assignee, due dates, documents, repo URL, blockers, risks, and confidence fields.
- `Task`: execution work item under a solution.
- `Team`, `User`: team capacity and people administration.
- `ChangeLog`, usage events, performance samples: audit and product telemetry.
- Agent API and change-request tables: automation-friendly backend workflow.

This is useful, but it encodes a particular operating model. A broad project-management product needs to support companies that think in projects, epics, tasks, tickets, milestones, campaigns, clients, engagements, initiatives, deliverables, sprints, OKRs, portfolios, or simple shared to-do lists.

## Strengths To Preserve

- Space isolation is already a strong foundation for multi-tenant workspaces.
- Cookie-backed browser auth and service-account bearer tokens are better than storing reusable tokens in the browser.
- Audit logging, request IDs, and live refresh are production-minded.
- The app already supports multiple operational views: table, dashboard, Gantt, Kanban, calendar, capacity, governance, analytics.
- Tests cover many backend and frontend contracts.
- The backend is already structured around routes, schemas, models, services, and SQL contracts.
- The agent-facing backend direction is useful for automation, integrations, and AI-assisted project operations.

## Highest-Risk Product Gaps

### 1. The Domain Model Is Too Specialized

Severity: High / must-fix before broad launch

The `Solution` entity is effectively a specialized deliverable/work-package concept, but it is a required middle layer between project and task. Many businesses will not naturally use that hierarchy. Forcing every user into project -> solution -> task creates adoption friction and makes the product feel opinionated in the wrong way.

Recommended change:

- Introduce a generic `WorkItem` model or a polymorphic work layer.
- Let each workspace define enabled work item types such as `Project`, `Milestone`, `Epic`, `Deliverable`, `Task`, `Bug`, `Request`, or `Campaign`.
- Keep SIPM's current program/project/solution/task setup as a default workspace template.
- Add parent-child relationships that allow different depths, not one fixed chain.
- Add a controlled migration path from `projects`, `solutions`, and `tasks` into the generalized model.

Target model:

```text
Organization
  Workspace
    Portfolio or Folder
      WorkItem(type=project|milestone|epic|deliverable|task|custom)
        WorkItem children
        Assignments
        Comments
        Attachments
        Activity
        Custom fields
        Status history
```

### 2. Workspace And Account Structure Is Not Commercial-SaaS Ready

Severity: High / must-fix before paid launch

`Space` is close to a workspace, but the app lacks a clear commercial account boundary. A product needs organizations, workspace membership, invitations, billing ownership, plan limits, data-retention policy, and admin separation.

Recommended change:

- Add `Organization` above `Space` or rename `Space` to `Workspace` in the product language.
- Add `OrganizationMember`, `WorkspaceMember`, and role templates.
- Add invitation flows instead of assuming admin-created users.
- Add plan, billing status, trial state, seat count, and usage limits.
- Keep `Space` internally during migration if needed, but present users with `Workspace`.

### 3. Identity Is Enterprise-Specific

Severity: High / must-fix before public launch

The current model exposes `soeid` as a core identifier. That works for one enterprise environment but will feel foreign to most customers.

Recommended change:

- Replace product-facing `soeid` language with `username`, `handle`, or `external_id`.
- Make email the primary human identity for public SaaS.
- Support password auth for early launch, then add SSO/OIDC/SAML for teams.
- Preserve `soeid` as optional `external_id` or enterprise directory identifier.

### 4. Permissions Are Too Coarse

Severity: High / must-fix before multi-business launch

The current role model has global admin, space admin, and member. A production PM tool needs permissions that distinguish owner, admin, manager, editor, commenter, viewer, guest, automation, and billing admin.

Recommended change:

- Add role templates and permission flags.
- Separate organization administration from workspace administration.
- Add object-level access only where it is truly needed, such as private projects or client guest access.
- Add permission tests for every new role boundary.

### 5. Collaboration Primitives Are Missing

Severity: High / must-fix for product usefulness

Project-management users expect comments, mentions, notifications, watchers, activity feeds, file previews, assignment notifications, due-date reminders, and change subscriptions. The current audit log is useful for governance but not a collaboration experience.

Recommended change:

- Add comments on work items.
- Add mentions and watchers.
- Add notification preferences.
- Add in-app notification center first, email/slack/webhook later.
- Add user-friendly activity feed separate from the system audit log.
- Add attachment metadata and object-storage-backed files instead of storing all content as DB blobs.

### 6. Workflows And Fields Are Not Configurable Enough

Severity: High / must-fix for many business types

The app has fixed status enums, RAG status, phases, blockers, risks, FTE, repo URLs, and confidence fields. Those are useful for some teams, but a product needs workspace-configurable workflows and custom fields.

Recommended change:

- Add configurable statuses per work item type.
- Add workflow transitions and optional transition rules.
- Add custom fields by workspace and work item type: text, number, date, select, multi-select, person, URL, checkbox.
- Add field visibility and required-field configuration per type.
- Keep RAG, risk, capacity, and repo URL as optional fields in a default template rather than universal fields.

### 7. Scaling Model Is Still Collection-Oriented

Severity: Medium / should-fix before larger customer pilots

The frontend loads broad entity arrays for many views. That is workable for small teams, but a product needs pagination, server-side filtering, search, and bounded rendering before customers have thousands of items.

Recommended change:

- Add paginated list APIs for work items, users, activities, comments, and audit.
- Add server-side filtering and sorting.
- Add full-text search.
- Add virtualization for large table and board views.
- Define performance budgets per route.

### 8. Product Onboarding Is Underdeveloped

Severity: Medium / should-fix before public beta

The app has good internal docs, but product users need guided setup, templates, sample import paths, role invites, and an empty state that gets them to value quickly.

Recommended change:

- Add first-run workspace creation.
- Offer templates: Simple Tasks, Software Team, Client Delivery, Portfolio PMO, Marketing Calendar, Operations Queue.
- Add CSV and JSON import wizards with preview and undo.
- Add guided setup checklist for workspace owner.
- Add demo workspace generation for evaluation.

### 9. Launch Operations Are Not Complete

Severity: High / must-fix before paid launch

The app has readiness checks and CI, but a commercial launch needs stronger deployment, rollback, incident, observability, security, privacy, and compliance posture.

Recommended change:

- Add managed production environment definitions.
- Add migration runner and rollback strategy.
- Add structured app metrics, error tracking, audit exports, backup and restore drills.
- Add tenant deletion/export process.
- Add data-retention controls.
- Add vulnerability scanning and dependency-update process for npm and Python.
- Add security review for auth, cookies, CSRF, rate limits, uploads, and permissions.

## Recommended Product Entity Model

### Commercial Account Layer

Add:

- `Organization`: billing/account boundary.
- `OrganizationMember`: account-level membership and role.
- `Workspace`: product-facing collaboration space. This can map to current `Space`.
- `WorkspaceMember`: workspace-level access.
- `Invitation`: email-based invite flow with expiration and role.
- `Subscription` or `Plan`: trial, free, team, business, enterprise.
- `UsageLimit`: seats, workspaces, storage, automations, API volume.

### Work Management Layer

Add or evolve toward:

- `WorkItemType`: workspace-configurable type definition.
- `Workflow`: status set and transition rules for a type.
- `WorkItem`: generic persisted work object.
- `WorkItemRelation`: parent/child, blocked-by, relates-to, duplicate-of.
- `Assignment`: many-to-many assignees, reviewers, owners, teams.
- `Milestone`: either a work item type or a first-class schedule object.
- `Sprint` or `Iteration`: optional agile execution container.
- `Goal` or `Objective`: optional strategic alignment object.
- `Portfolio`: optional grouping above projects.

### Collaboration Layer

Add:

- `Comment`
- `Mention`
- `Watcher`
- `Notification`
- `ActivityEvent`
- `Attachment`
- `AttachmentVersion`
- `SavedView`
- `DashboardWidgetConfig`

### Configuration Layer

Add:

- `CustomFieldDefinition`
- `CustomFieldValue`
- `Template`
- `AutomationRule`
- `WebhookEndpoint`
- `ApiTokenScope`
- `IntegrationConnection`

## Recommended Navigation Model

The current routes can be reshaped into a more product-oriented IA:

- Home: personal work, recent activity, assigned items, mentions, due soon.
- Work: table, board, calendar, timeline, backlog.
- Projects: project directory and project detail pages.
- Roadmap: capacity, sequencing, milestones.
- Dashboards: saved dashboards and reporting.
- Automations: rules, agent change requests, webhooks.
- Admin: workspace settings, members, roles, billing, integrations, audit.

The current `master`, `dashboard`, `pm-dashboard`, and `program-dashboard` views should be rationalized. Each should answer a distinct question, or they should be merged into configurable dashboards and saved views.

## Frontend Architecture Direction

The vanilla ES module frontend can continue for near-term launch if the team keeps the current modular discipline. For a commercial product, the decision point is whether SIPM will remain a compact tool or grow into a large app with complex interactive state.

Recommended near-term:

- Keep vanilla modules while product fit is still changing.
- Add design-system tokens and reusable primitives for table, board, modal, drawer, form, toast, tabs, filter bar, empty state, and confirmation.
- Add route-level visual regression screenshots for key workflows.
- Add accessibility gates for keyboard flow, labels, focus traps, contrast, and reduced motion.

Recommended medium-term:

- Consider React, Vue, Svelte, or another component framework only when route complexity and state sharing justify the migration cost.
- If migrating, do it by route, not as a full rewrite.
- Preserve existing API contracts during frontend migration.

## Backend Architecture Direction

Recommended backend direction:

- Keep FastAPI and SQLAlchemy.
- Move more route business logic into services as entities generalize.
- Add a migration system instead of relying only on canonical SQL docs.
- Add pagination, filtering, sorting, and projection utilities.
- Add consistent error-code envelopes across public APIs.
- Add idempotency keys for imports, automations, and integration writes.
- Add API versioning before external customers depend on the contract.
- Expand the Agent API into an automation and integration API, not a separate business logic path.

## Data Storage Direction

Recommended changes:

- Use object storage for attachments; keep only metadata and virus-scan status in the database.
- Add storage quotas per plan/workspace.
- Add retention policy tables and background jobs.
- Add soft-delete restore windows and hard-delete jobs.
- Add export packages for tenant portability.
- Add background workers for email, notifications, imports, exports, rollups, and automation rules.

## Security And Compliance Direction

Before paid launch:

- Add CSRF assessment and explicit policy for cookie-authenticated writes.
- Add rate limits for login, password reset, API tokens, imports, exports, and upload endpoints.
- Add upload validation, malware scanning hook, and file-type policy.
- Add SSO/OIDC for business accounts.
- Add optional SAML for enterprise.
- Add organization-level audit export.
- Add admin event logs for invites, role changes, billing changes, token creation, and integration changes.
- Add privacy policy support: user deletion, workspace export, tenant deletion, retention.
- Add security headers validation in CI.

## Reporting And Analytics Direction

The current analytics system is mostly internal product/usage telemetry. A PM product also needs customer-facing reporting.

Recommended product reporting:

- Saved dashboards.
- Work item count, throughput, cycle time, aging, overdue, blocked, workload, burnup, burndown.
- Portfolio health and roadmap reporting.
- Custom-field-based charts.
- Exportable reports.
- Scheduled email reports.
- Permission-aware dashboards.

Keep internal product telemetry separate from customer reporting.

## Integration Direction

Launch-ready integrations should be deliberately small:

- Email notifications.
- Calendar subscription/export.
- Slack or Microsoft Teams notifications.
- GitHub/Jira/Linear import or sync only after core data model stabilizes.
- Webhooks for work item events.
- Public REST API with scoped tokens.
- Agent API for controlled bulk work and AI-assisted changes.

Avoid deep bidirectional sync until the core work item model and permissions are stable.

## Suggested Roadmap

### Phase 0: Product Positioning And Rename

Goal: decide what SIPM is selling.

Deliverables:

- Product positioning: "configurable project and work management for teams."
- Product vocabulary: organization, workspace, project, task, view.
- Decision on public name and whether `SIPM` remains internal code name.
- Target customer profiles and top 5 workflows.

Exit criteria:

- The entity model and UI copy stop being driven by internal SIPM vocabulary.

### Phase 1: Tenant, Identity, And Onboarding Foundation

Goal: make the app usable by a new business without manual admin setup.

Deliverables:

- Organization/workspace model.
- Email-first identity.
- Workspace invites.
- Workspace owner/admin/member/viewer roles.
- First-run setup.
- Workspace templates.

Exit criteria:

- A new team can sign up, create a workspace, invite members, and start from a template without operator intervention.

### Phase 2: Generalized Work Item Model

Goal: remove the fixed `solution` middle-layer constraint.

Deliverables:

- Work item type definitions.
- Generic work item table or compatibility layer.
- Parent-child relationships.
- Migration from current program/project/solution/task records.
- Backward-compatible API adapters during transition.
- UI that supports simple project/task usage and richer portfolio usage.

Exit criteria:

- A workspace can use simple projects and tasks without creating "solutions."

### Phase 3: Collaboration And Notifications

Goal: make SIPM useful for daily team work, not only reporting.

Deliverables:

- Comments.
- Mentions.
- Watchers.
- In-app notifications.
- Activity feed.
- Email notifications for key events.
- Attachment metadata with object storage.

Exit criteria:

- Users can discuss, follow, and be notified about work without leaving the app.

### Phase 4: Configurable Views And Fields

Goal: let different businesses adapt SIPM without custom code.

Deliverables:

- Custom fields.
- Configurable workflows/statuses.
- Saved views.
- Table, board, calendar, and timeline views over the same work items.
- View sharing and permissions.

Exit criteria:

- A workspace owner can configure a workflow and fields for their team without database or code changes.

### Phase 5: Scale And Reliability

Goal: support real customer data volumes.

Deliverables:

- Paginated APIs.
- Server-side filtering/sorting/search.
- Large-list rendering strategy.
- Background jobs.
- Import/export jobs.
- Error tracking, metrics, dashboards, alerting.
- Backup/restore rehearsal.

Exit criteria:

- The app can handle thousands of work items per workspace with predictable route performance.

### Phase 6: Commercial Launch Readiness

Goal: make the product sellable and supportable.

Deliverables:

- Billing/subscription integration.
- Plan limits.
- Admin billing area.
- Terms/privacy/security docs.
- Support tooling.
- Tenant export/delete.
- Production incident playbook.
- Security review and remediation.

Exit criteria:

- The product can support paying customers with clear operational ownership.

## Migration Strategy

Do not rewrite everything at once.

Recommended path:

1. Add commercial account/workspace concepts while preserving current `Space` behavior.
2. Introduce new generic work tables or compatibility views behind new APIs.
3. Build a migration service that can map:
   - Program -> Portfolio or Folder
   - Project -> WorkItem type `project`
   - Solution -> WorkItem type `deliverable`
   - Task -> WorkItem type `task`
4. Keep old routes working through adapters during the transition.
5. Move one route at a time to the generalized APIs.
6. Retire old entity-specific routes after UI and agent API consumers have migrated.

## Launch Acceptance Criteria

SIPM should not be called launch-ready for broad business use until:

- New users can self-serve account creation or invitation acceptance.
- Product-facing identity is email/user based, not SOEID based.
- A workspace can operate with projects and tasks only.
- Comments, notifications, activity, and attachments exist.
- Roles and permissions are clear enough for guests, viewers, members, admins, and owners.
- Lists and boards support pagination or bounded rendering.
- File uploads are scanned or explicitly restricted.
- Billing, plan limits, and tenant lifecycle are defined.
- Production observability and incident response exist.
- Customer data export and deletion are supported.
- The core workflows have browser-level smoke and visual validation.

## Immediate Next Decisions

1. Decide whether SIPM will remain an enterprise/internal deployment product or become public SaaS. This affects auth, billing, tenancy, and compliance immediately.
2. Decide whether "solution" is a first-class product concept or a default template work type.
3. Decide whether the first launch is team-level project management, PMO portfolio management, or team capacity management. Trying to launch all three equally will blur the product.
4. Decide whether Oracle/TAConnection remains the production database target or whether the product should support a more standard SaaS stack such as Postgres.
5. Decide the frontend strategy: continue modular vanilla JS through beta, or plan a route-by-route component-framework migration after the generalized work model lands.

## Recommended First Implementation Slice

The smallest high-leverage slice is:

1. Product language cleanup: present `Space` as `Workspace`, hide SOEID language behind email/display name where possible.
2. Add workspace templates and first-run setup.
3. Add comments and activity feed on tasks and solutions.
4. Add a simple `WorkItemType` concept that initially maps existing `project`, `solution`, and `task` records.
5. Add saved views for task/work item lists.

This slice improves adoption without immediately replacing the whole persistence model.
