# SIPM Project Assessment

Date: 2026-03-26

Scope: current-state codebase complexity, engineering professionalism, operational maturity, and replacement-cost estimate before AI coding agents versus today.

## Executive Summary

SIPM is a serious line-of-business web application. It is not a shallow CRUD demo, not a one-screen prompt build, and not a zero-dollar app.

Based on the current repository state, my overall assessment is:

- Product depth: high for an internal operations platform
- Engineering professionalism: strong and materially more disciplined than an average internal app
- Current grade: roughly `A-` as a professional internal application
- Most realistic replacement-cost band:
  - pre-AI coding agents: `~$300k-$600k`
  - today with disciplined AI-assisted delivery: `~$200k-$425k`

The current codebase has real architectural intent, real permission and tenancy complexity, real validation discipline, and real operational thought. It still stops short of full top-tier enterprise maturity, but it is plainly in professional-software territory.

## Assessment Method

This assessment is based on the current tree as it exists now. I did not use the recent refactor history as the basis for the judgment.

I reviewed the present directory structure and representative implementation surfaces across:

- backend runtime, auth, dependency, route, service, and schema layers in `src/main/backend/`
- frontend shell, route, entity, and style layers in `src/main/ui/`
- Python, Vitest, and Playwright coverage in `src/main/test/` and `src/main/ui/test/`
- CI, repo-governance, and operability artifacts in `.github/`, `scripts/`, `CONTRIBUTING.md`, `.editorconfig`, `.env.example`, and `docs/codebase-review/`
- the current executive baseline at `docs/project-assessment-2026-03-25.md`

Representative files reviewed directly during this pass included:

- `src/main/backend/main.py`
- `src/main/backend/app/deps.py`
- `src/main/backend/app/routes/__init__.py`
- `src/main/backend/app/routes/planning/work_allocation.py`
- `src/main/backend/app/routes/projects/{common,read,write,import_export}.py`
- `src/main/backend/app/services/planning_work_allocation.py`
- `src/main/backend/app/services/planning_report_pdf.py`
- `src/main/backend/app/services/realtime.py`
- `src/main/backend/app/services/smart_cache.py`
- `src/main/ui/index.html`
- `src/main/ui/js/app.js`
- `src/main/ui/js/shell/router.js`
- `src/main/ui/js/shell/live-sync.js`
- `src/main/ui/js/routes/planning/{api,render,interactions}.js`
- `src/main/ui/js/routes/pm-dashboard/{render,sections}.js`
- `src/main/ui/js/routes/spaces/{render,interactions}.js`
- `docs/codebase-review/{05-enterprise-roadmap,06-quality-gates,07-repo-operability}.md`

## Validation Run

Validation executed during this pass:

| Check | Result |
| --- | --- |
| `python3 scripts/codebase_review.py quality-gates` | `pass=75, fail=1` |
| `python3 scripts/check_route_module_test_mapping.py` | pass |
| `cd src/main && python3 -c "import backend.main; print('ok')"` | `ok` |
| `pytest -q -s src/main/test` | `444 passed, 1 skipped in 185.98s` |
| `npm run lint:ui` | pass |
| `npm run test:ui` | `5 passed` |
| Browser smoke coverage | Playwright suite passed `2 passed` when reusing a running smoke app; the stock `npm run test:ui:smoke` launcher is currently cross-shell brittle on this host because `playwright.config.js` hardcodes `python3` for its web server command |

Interpretation:

- The application behavior and regression surface are strong.
- The remaining quality-gate failure is structural, not widespread instability.
- There is a small tooling-portability issue in the smoke harness, which is a professionalism gap, but not evidence that the app itself is broken.

## Complexity Snapshot

Current active-repo metrics excluding `.git`, `.venv`, `node_modules`, `__pycache__`, `.pytest_cache`, `htmlcov`, `playwright-report`, and `test-results`:

| Metric | Value |
| --- | --- |
| Active files reviewed | `211` |
| Total active LOC | `48,707` |
| Backend files | `60` |
| Frontend files | `73` |
| Test files | `54` |
| Docs files | `13` |
| Scripts files | `4` |
| Backend LOC | `11,253` |
| Frontend LOC (`js/css/html`) | `22,865` |
| Test LOC | `10,981` |
| Backend route modules | `28` |
| Frontend route modules | `42` |
| Python test files | `52` |
| Vitest specs | `2` |
| Playwright specs | `2` |

Largest current active files:

- `src/main/ui/js/app.js` -> `3,870` lines
- `src/main/ui/styles/base.css` -> `1,693` lines
- `src/main/ui/index.html` -> `965` lines
- `src/main/test/test_frontend_ux_improvement_contract.py` -> `902` lines
- `src/main/ui/styles/routes/dashboard.css` -> `867` lines
- `src/main/backend/app/routes/planning/work_allocation.py` -> `803` lines
- `src/main/ui/styles/routes/kanban-calendar.css` -> `788` lines
- `src/main/ui/js/routes/planning/api.js` -> `627` lines
- `src/main/ui/js/routes/planning/render.js` -> `588` lines
- `src/main/ui/js/routes/pm-dashboard/render.js` -> `579` lines

Current quality-gate posture:

- `75` checks pass
- `1` check fails
- the only remaining file-size violation is `src/main/backend/app/routes/planning/work_allocation.py`

This is the profile of a medium-to-large internal application with real product surface area, not a lightweight single-flow app.

## Why This Is A Serious App

SIPM has several characteristics that shallow web apps usually do not have:

- Multi-space behavior with active-space resolution, role thresholds, global-admin exceptions, and guarded access paths.
- A real backend service layer rather than only frontend mock state.
- A framework-light but structured SPA shell with route modules, lazy loading, state controllers, and route ownership boundaries.
- Realtime coordination, cache invalidation, websocket reconnect logic, and request correlation.
- Health and readiness endpoints with runtime validation and DB checks.
- Oracle-oriented schema contract plus test-mode SQLite overrides.
- Audit logging and explicit authorization-denial logging.
- Rich business surface area: deliverables, projects, solutions, subcomponents, planning board, PM dashboard, calendar, kanban, teams, spaces, user access, import/export, and PDF reporting.
- CI that exercises backend tests, frontend linting, frontend unit coverage, and browser smoke coverage.
- Repo-governance and operator artifacts that document budgets, merge rules, runtime modes, and incident triage.

Shallow apps usually have some of these. Serious internal platforms tend to have most of them. SIPM is in the second category.

## Professionalism Assessment

### Strong Signals

| Area | Assessment | Evidence |
| --- | --- | --- |
| Domain modeling | Strong | distinct entities and workflows across projects, solutions, subcomponents, allocations, teams, users, spaces, and audits |
| Authorization discipline | Strong | central dependency guards, space resolution, global-admin and space-role checks, authz denial audit logging |
| Frontend structure | Strong | route modules, entity modules, shell controllers, lazy route loading, ownership budgets |
| Validation discipline | Strong | `444` passing Python tests plus lint, Vitest, and browser smoke coverage |
| Repo governance | Strong | `.editorconfig`, `CONTRIBUTING.md`, `CODEOWNERS`, quality-gates, roadmap, operability guide |
| Operability thinking | Good | readiness, request IDs, request logs, Redis coordination rules, runtime mode matrix |
| Product scope | Strong | broad functional surface beyond CRUD list/detail/edit |

### Current Weaknesses And Debt

| Area | Assessment | Why it matters |
| --- | --- | --- |
| Planning backend concentration | Meaningful debt | `work_allocation.py` is still the only quality-gate violation and centralizes too much route behavior |
| Frontend shell residual size | Manageable debt | `app.js` is now within budget, but at `3,870` lines it is still a major coordination surface |
| SPA shell concentration | Moderate | `index.html` and `base.css` remain large, which can raise long-term UI change friction |
| Production-platform visibility | Partial | the repo documents runtime expectations well, but still does not surface IaC, deployment automation, tracing, metrics, SLOs, or release controls |
| Tooling portability | Minor gap | Playwright smoke command is cross-shell brittle because the configured web-server launcher assumes `python3` resolution |

### Scorecard

My subjective scorecard:

| Dimension | Score | Notes |
| --- | --- | --- |
| Product depth | `8.8/10` | broad and business-real surface area |
| Architecture | `8.2/10` | current ownership is much healthier, with one notable backend hotspot left |
| Validation | `9.0/10` | stronger than most internal apps at this size |
| Operability | `7.6/10` | real application-level maturity, not yet full platform maturity |
| UX and UI discipline | `7.5/10` | functionally rich and coherent, less evidence of a deeply systematized design platform |
| Maintainability | `8.0/10` | substantially improved, but still exposed to the planning monolith and some shell concentration |
| Overall professionalism | `8.3/10` | solid `A-` internal software |

## What The Codebase Says About The Team And Build Quality

The current repository reads like software built and then actively professionalized, not software generated in one pass.

The strongest evidence for that judgment is not just line count. It is the presence of:

- explicit ownership boundaries
- route- and style-level budget enforcement
- characterization tests around structural refactors
- meaningful permission and tenancy logic
- app-level observability and readiness behavior
- review-memory and execution artifacts in `docs/codebase-review/`

That combination is hard to fake. It usually appears when someone is treating the app as an actual maintained product rather than a disposable experiment.

## Complexity Drivers

The cost and difficulty in SIPM are driven by the kinds of problems it solves, not by superficial code size alone.

1. Multi-space authorization. Active-space context, role thresholds, global-admin bypasses, and guarded mutation paths are inherently higher-risk than ordinary CRUD.
2. Cross-cutting mutation consistency. Cache invalidation, audit logs, descendant visibility, and realtime refresh need to remain aligned after writes.
3. Planning-domain depth. Teams, people, tasks, allocations, capacity, month scoping, and report generation create real business-logic density.
4. Frontend state coordination. A framework-light SPA with many routes and shared shell state demands more engineering discipline than a heavily scaffolded frontend stack.
5. Import/export and reporting. CSV flows and PDF generation are common in serious business software and uncommon in hobby-grade apps.
6. Runtime-mode and data-store flexibility. The code supports SQLite test harnesses while still documenting Oracle and Redis expectations for non-test environments.

## What Keeps It From Top-Tier Enterprise Grade

SIPM is strong, but I would not describe it as top-tier enterprise software yet.

Main reasons:

- One important backend route remains above the structural budget and still concentrates planning behavior.
- The repo shows app-level operational maturity, not full platform maturity.
- There is still limited repo-visible evidence of deployment automation, environment provisioning, tracing, metrics backends, formal SLO ownership, or release governance.
- The frontend is much healthier than before, but it still depends on a large custom shell rather than a more standardized component-platform setup.
- The smoke harness portability issue is small, but it is exactly the kind of thing polished enterprise teams usually remove quickly.

These are scaling and platform-maturity gaps, not toy-app problems.

## Cost Estimate

### Framing

This estimate is for rebuilding an app of similar grade and scope, not for reproducing screenshots.

What is being priced:

- backend API and tenancy-aware authorization
- frontend SPA shell and route modules
- schema and data-model work
- planning board and related business logic
- dashboards, calendar, kanban, and governance surfaces
- realtime, cache, import/export, and PDF/reporting behavior
- tests, CI, and normal PM/QA/design/rework overhead

What is not priced:

- long-term maintenance
- production support staffing
- cloud and infrastructure spend
- legal, compliance, or formal security-audit costs

### Effort Estimate

My best-fit replacement effort for the current grade is roughly:

- `10-14` engineering person-months
- plus `3-5` person-months of QA, PM, design, hardening, and rework overhead

That places SIPM comfortably above hobby or cheap-agency territory.

### Pre-AI Coding Agents

Most realistic band before current AI coding agents:

- lean senior-led build: `~$180k-$320k`
- small professional shop: `~$300k-$600k`
- heavier enterprise vendor path: `~$600k-$1.1M`

My best single-range estimate for a comparable rebuild is:

`~$300k-$600k pre-AI`

### Today With Modern AI Assistance

Most realistic band today, assuming disciplined use of modern AI assistance by competent engineers:

- lean senior-led build: `~$125k-$240k`
- small professional shop: `~$200k-$425k`
- heavier enterprise vendor path: `~$425k-$850k`

My best single-range estimate today is:

`~$200k-$425k with modern AI-assisted delivery`

### Why The Discount Is Real But Not Extreme

I would not model SIPM as a `50%+` guaranteed cost collapse just because modern coding agents exist.

My estimate uses a conservative `20-35%` cost reduction versus the pre-AI baseline.

Why conservative:

- this repo has many implicit requirements and permission edges
- the value is in correct behavior and stable workflows, not just code generation speed
- mature-repo coordination, debugging, refactoring, and validation still consume a large share of effort
- this codebase is closer to a realistic maintained application than to a clean-room benchmark task

## External Market And Research Inputs

I used these sources to ground the cost section:

- U.S. Bureau of Labor Statistics, Occupational Outlook Handbook:
  - https://www.bls.gov/ooh/computer-and-information-technology/software-developers.htm
  - BLS reports the median annual wage for software developers at `$133,080` in May 2024 and software QA analysts/testers at `$102,610`.
- arXiv, `The Impact of AI on Developer Productivity: Evidence from GitHub Copilot`:
  - https://arxiv.org/abs/2302.06590
  - In a controlled, well-scoped task, developers with Copilot completed the assignment `55.8%` faster.
- arXiv, `The Impact of Generative AI on Collaborative Open-Source Software Development: Evidence from GitHub Copilot`:
  - https://arxiv.org/abs/2410.02091
  - The authors report a `5.9%` increase in project-level code contributions, alongside an `8%` increase in coordination time.
- METR, `Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity`:
  - https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/
  - In that realistic large-repo setting, experienced developers took `19%` longer when AI tools were allowed.

Important interpretation:

- The older Copilot experiment supports real upside on well-scoped implementation tasks.
- The newer GitHub OSS study suggests only modest net gains once collaborative coordination is included.
- The METR result is the best cautionary evidence for mature, implicit-constraint repositories.
- SIPM is much closer to the latter two settings than to a benchmark-style coding task.

The cost bands above are therefore an inference from current labor rates plus mixed productivity evidence, not a direct quote from any one study.

## Bottom Line

SIPM has clear replacement value.

My bottom-line judgment:

- This is materially better than the shallow apps it is being compared against.
- It belongs in the `serious internal platform / advanced MVP+` bucket.
- It is now solidly professional software, not just ambitious hobby software.
- It is plausibly a `mid six-figure` app pre-AI and still a `meaningful six-figure` app today if rebuilt properly.

If I had to summarize it in one line:

SIPM currently reads like a professionally built internal operations platform that still has one major backend decomposition step and a few platform-maturity gaps left before it can credibly claim enterprise-grade completeness.
