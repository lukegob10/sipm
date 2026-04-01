# SIPM Project Assessment

Date: 2026-03-25

Scope: codebase complexity, engineering professionalism, and replacement-cost estimate before AI coding agents versus today.

## Executive Summary

SIPM is not a shallow demo app. It is a real line-of-business web application with meaningful domain depth, a non-trivial permission model, backend and frontend modularity, regression coverage, CI, and operational concerns beyond simple CRUD.

My overall assessment is:

- Product depth: high for an internal operations app
- Engineering professionalism: strong, but not top-tier enterprise polish
- Current grade: roughly `B+ / low A-` as an internal professional app
- Most realistic replacement-cost band:
  - pre-AI coding agents: `~$250k-$500k`
  - today with strong AI-assisted delivery: `~$160k-$350k`

If someone described this as a zero-dollar or weekend-caliber app, that would not match the evidence in the repository.

## Evidence Base

I based this report on the live repository, not just the README.

Key local evidence reviewed:

- backend runtime and routing in `src/main/backend/main.py` and `src/main/backend/app/routes/`
- frontend shell and route modules in `src/main/ui/index.html`, `src/main/ui/js/app.js`, `src/main/ui/js/routes/`, and `src/main/ui/js/shell/`
- tests in `src/main/test/` and `src/main/ui/test/`
- CI in `.github/workflows/backend-tests.yml`
- SQL contract and migrations in `docs/sql/`
- prior repo review artifacts in `docs/codebase-review/`

Validation run during this pass:

| Check | Result |
| --- | --- |
| `python3 scripts/check_requirements_lock.py` | pass |
| `python3 scripts/check_route_module_test_mapping.py` | pass |
| `python3 -c "import backend.main; print('ok')"` from `src/main` | `ok` |
| `pytest -q -s src/main/test` | `423 passed, 1 skipped in 164.70s` |
| `npm run lint:ui` | pass |
| `npm run test:ui` | `5 passed` |
| `npm run test:ui:smoke` | `2 passed` after refreshing stale smoke expectations |

## Complexity Snapshot

Repository metrics excluding `.git`, `.venv`, `node_modules`, `htmlcov`, `.pytest_cache`, and temp artifacts:

| Metric | Value |
| --- | --- |
| Active source/docs/config files reviewed | `185` |
| Backend files | `56` |
| Frontend files | `51` |
| Test files | `52` |
| Backend Python LOC | `11,137` |
| Frontend LOC (`js/css/html`) | `23,338` |
| Test LOC | `10,434` |
| Backend route modules | `20` |
| Frontend route modules | `27` |
| Python test files | `50` |
| Vitest specs | `2` |
| Playwright specs | `2` |

Largest current hotspots:

- `src/main/ui/js/app.js` -> `7,270` lines
- `src/main/ui/styles/routes/workbench-planning-admin.css` -> `3,061` lines
- `src/main/backend/app/routes/planning/work_allocation.py` -> `803` lines
- `src/main/ui/js/routes/pm-dashboard/render.js` -> `785` lines
- `src/main/ui/js/routes/planning/api.js` -> `627` lines

Interpretation:

- This is a medium-to-large internal web app, not a landing-page app and not a tiny SaaS MVP.
- The size is large enough that structure, test discipline, and permission handling matter.
- The remaining hotspots show real complexity and some technical debt, not artificial over-engineering.

## Why This Is A Serious App

The app has several characteristics that shallow web apps usually do not have:

- Multi-space access model with role-aware authorization, active-space resolution, and global-admin versus space-admin behavior.
- Separate backend and frontend application layers rather than a single-file prototype.
- Realtime and cache coordination via websocket refresh plus `memory|redis` coordination modes.
- SQLAlchemy models, Oracle-oriented schema contract, and tracked SQL migrations.
- Audit logging, request IDs, readiness checks, and runtime configuration hardening.
- Rich domain surface: deliverables, projects, solutions, subcomponents, phases, planning board, dashboards, calendar, kanban, teams, spaces, users, and PDF reporting.
- CSV import/export flows and derived data behavior, which are common in real business software and uncommon in toy apps.
- CI with Python tests, frontend lint, frontend unit tests, and browser smoke coverage.
- Repo-level review memory in `docs/codebase-review/`, which is a sign of active engineering management rather than one-off hacking.

This is the profile of a serious internal operations platform or a strong vertical-product MVP+, not a throwaway side project.

## Professionalism Assessment

### Strong Signals

| Area | Assessment | Evidence |
| --- | --- | --- |
| Domain modeling | Strong | Clear entities and workflows across projects, solutions, subcomponents, planning, spaces, teams, users, and audits |
| Security and auth discipline | Strong | central auth/deps/security modules, cookie/runtime validation, role gates, admin protections |
| Test discipline | Strong | `423` passing Python tests plus UI lint/unit/browser checks |
| Operational thinking | Good | request IDs, readiness probe, structured logs, runtime config validation |
| Change management | Good | codebase review ledger, fix queue, dependency map, CI gates |
| Product scope | Strong | multiple views and workflows beyond CRUD list/detail/edit |

### Weaknesses And Debt

| Area | Assessment | Why it matters |
| --- | --- | --- |
| Frontend maintainability | Mixed | `app.js` is still `7,270` lines; several route/style hotspots remain large |
| Styling surface | Mixed | a `3,061` line route stylesheet suggests UI complexity is still concentrated |
| Branding/naming hygiene | Minor drift | backend package and FastAPI title still contain `Jira-lite` naming leftovers |
| Infra visibility | Limited in repo | no repo-visible deployment stack, observability platform, IaC, or production rollout automation |
| Enterprise hardening | Partial | good app-level discipline, but not a fully surfaced enterprise platform with full infra, metrics, tracing, and formal release controls |

### Scorecard

My subjective scorecard:

| Dimension | Score | Notes |
| --- | --- | --- |
| Product depth | `8.5/10` | well beyond shallow app territory |
| Architecture | `7.5/10` | good separation, but some major hotspots remain |
| Validation | `8.5/10` | notably stronger than typical indie or demo codebases |
| Ops readiness | `6.5/10` | meaningful progress, but still not full enterprise maturity |
| UX/polish | `7.0/10` | substantial functional UI, less evidence of premium design-system refinement |
| Maintainability | `6.8/10` | workable and improving, but still paying down monolith hotspots |
| Overall professionalism | `7.8/10` | clearly professional-grade internal software |

## Complexity Drivers

The cost and difficulty in this repo are driven less by raw line count and more by the kinds of problems it solves:

1. Permissioned multi-space behavior. Space-aware data access, role thresholds, global-admin exceptions, and guarded user management create more complexity than ordinary CRUD.
2. Cross-cutting consistency. Audit logs, cache invalidation, realtime refresh, and descendant data visibility have to stay aligned after writes.
3. Business workflow breadth. Deliverables, planning, dashboards, PM views, teams, spaces, users, calendar, kanban, import/export, and PDF generation add breadth fast.
4. Frontend state complexity. A framework-light SPA with shared shell state and many routes demands discipline because there is less framework structure doing the work for you.
5. Database and contract sensitivity. Oracle schema alignment and migration hygiene are more expensive than a pure local-SQLite hobby stack.

## What Keeps It From Top-Tier Enterprise Grade

This app is strong, but I would not call it elite enterprise software yet.

Main reasons:

- Some core files are still too large, which raises future change risk.
- The repo shows application-level quality, but not a full production platform story.
- The UI appears functionally mature, but there is less evidence of a deeply systematized design system or polished external-product finish.
- Naming drift (`Jira-lite`) and recently stale browser smoke assumptions indicate normal active-product entropy, not pristine maturity.

That said, these are the kinds of issues serious apps have while scaling. They are not toy-app problems.

## Cost Estimate

### Framing

This estimate is for rebuilding an app of similar grade and scope, not just reproducing screens.

What is being priced:

- backend API and permission model
- frontend SPA and route/view structure
- data model and schema work
- tests and CI
- CSV/PDF/reporting/realtime behavior
- normal PM, QA, and integration overhead

What is not priced:

- long-term maintenance
- production support team
- infra spend
- compliance, legal review, or formal security audits

### Effort Estimate

My best-fit replacement effort is roughly:

- `8-12` engineering person-months for equivalent functional depth
- plus `2-4` person-months of PM/QA/design/rework overhead

That places the app in the low-to-mid six-figure build band, not the hobby band.

### Pre-AI Coding Agents

Most realistic band before current AI coding agents:

- Lean senior-led build: `~$140k-$250k`
- Small professional shop: `~$250k-$500k`
- Heavier enterprise vendor path: `~$500k-$900k`

My best single-range estimate for this repo’s grade is:

`~$250k-$500k pre-AI`

Reasoning:

- The repo is too broad and too permission-sensitive to be a cheap no-process build.
- The validation surface alone is worth real money.
- Multi-role workflow software with import/export, reporting, dashboards, and realtime behavior typically prices above shallow CRUD.

### Today With AI Coding Agents

Most realistic band today, assuming a strong engineer or disciplined team is using modern AI assistance well:

- Lean senior-led build: `~$90k-$180k`
- Small professional shop: `~$160k-$350k`
- Heavier enterprise vendor path: `~$350k-$700k`

My best single-range estimate today is:

`~$160k-$350k with modern AI-assisted delivery`

### Why The Discount Is Real But Not Extreme

I would not model this as a `50%+` guaranteed cost collapse for a codebase like SIPM.

My estimate uses a conservative `20-35%` cost reduction versus the pre-AI baseline.

Why conservative:

- SIPM looks more like a mature, multi-file, implicit-requirements app than a small greenfield coding task.
- In that setting, repo knowledge, edge cases, debugging, validation, and product judgment still dominate.
- AI helps most with scaffolding, repetitive code, tests, and refactor acceleration, but less with deciding the right behavior.

## External Market And Research Inputs

I used these sources to ground the cost section:

- U.S. Bureau of Labor Statistics, Occupational Outlook Handbook, software developers pay:
  - https://www.bls.gov/ooh/computer-and-information-technology/software-developers.htm
  - BLS reports software developers at `$133,080` median annual wage in May 2024 and software QA analysts/testers at `$102,610`.
- arXiv, `The Impact of AI on Developer Productivity: Evidence from GitHub Copilot`:
  - https://arxiv.org/abs/2302.06590
  - Controlled experiment result: developers with Copilot completed the task `55.8%` faster in that well-scoped setting.
- METR, `Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity`:
  - https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/
  - In that realistic large-repo setting, experienced developers took `19%` longer when AI tools were allowed.

Important interpretation:

- The Copilot result supports real upside on scoped tasks.
- The METR result is more representative of mature-repo work with implicit constraints.
- SIPM is closer to the second category than the first, which is why I used a moderate discount instead of an aggressive one.

## Bottom Line

SIPM has real replacement value.

The repo shows:

- serious domain scope
- serious engineering effort
- meaningful QA discipline
- visible architecture and operational thought

My bottom-line judgment:

- This is materially better than the shallow web apps you are comparing it to.
- It belongs in the `serious internal platform / advanced MVP` bucket.
- It is plausibly a `low-to-mid six-figure` app pre-AI and still a `meaningful six-figure` app today if rebuilt properly.

## Notes From This Assessment Pass

During this pass I also refreshed two stale Playwright smoke specs so browser validation matches current UI and permission behavior:

- `src/main/ui/test/e2e/auth-and-deliverables.spec.js`
- `src/main/ui/test/e2e/navigation-smoke.spec.js`

Those changes did not widen application behavior; they only aligned smoke coverage with the current product contract.
