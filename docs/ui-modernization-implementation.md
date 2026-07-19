# UI Modernization Framework — Implementation Record

**Branch:** `codex/ui-modernization-framework`
**Worktree:** `F:\vault\projects\the-eco-system\sipm-ui-modernization`
**Source reviews:** [UI consistency review](./ui-frontend-consistency-review.md) and [UI modernization review](./ui-frontend-modernization-review.md)
**Implementation mode:** contract alignment

## End state

The frontend now uses the current Deliverables view as a shared product framework rather than as a one-off page treatment. All 12 routed view containers have the same product route frame and one semantic route heading. Navigation labels, browser titles, active navigation state, route aliases, data requirements, and prefetch relationships are owned by one route registry.

The desktop interface retains its dense control-room character. Tablet and phone layouts use a deliberate app bar, navigation drawer, account menu, touch targets, and route-specific adaptive presentation without relying on hidden global horizontal scrollbars.

## Framework architecture

### Route contract

`src/main/ui/js/shell/route-registry.js` is the source of truth for:

- route IDs and aliases;
- Work, Insight, and Admin sections;
- public navigation labels and page titles;
- route DOM and navigation targets;
- data requirements and prefetch targets.

The router consumes this metadata, updates `aria-current="page"`, exposes inactive views with `aria-hidden`, updates the compact app-bar title, and synchronizes the browser title.

### Shell contract

`src/main/ui/js/shell/navigation.js` owns the responsive navigation drawer and account menu. The shell now includes:

- a keyboard-focusable skip link;
- primary navigation landmark;
- stable tablet/phone app bar;
- labeled navigation disclosure and backdrop;
- reachable account, theme, completed-work, and sign-out actions;
- Escape, outside-click, route-selection, and resize cleanup behavior.

The old horizontal mobile navigation strip and its hidden scrollbar were removed from the route stylesheet. Shell breakpoint behavior now lives in `src/main/ui/styles/framework.css`.

### Visual contract

The framework stylesheet owns:

- the Deliverables-style blueprint route surface;
- a short 8/12/14 px surface scale;
- route header, toolbar, state, and responsive geometry;
- 42 px compact-shell interaction targets;
- a desktop Dashboard viewport with a 55/45 primary-to-supporting split and natural compact-page scrolling;
- visible, non-overflowing PM and governance navigation layouts;
- reduced-motion behavior;
- mobile Calendar agenda composition.

Route styles continue to own their domain-specific tables, boards, charts, forms, and workbench behavior.

### State contract

`src/main/ui/js/ui/route-state.js` provides escaped, semantic loading/empty/error/restricted/success state markup. Calendar, Roadmap, Kanban, and Usage Analytics now use this route-state language for their highest-level no-data or unavailable states.

## Review closure mapping

| Review item | Resolution |
|---|---|
| C-01 / M-01 responsive shell | Replaced horizontal strips with a drawer and account menu; all global actions remain reachable at 390 and 768 px |
| C-02 scrolling contracts | Calendar uses agenda mode below 700 px; Dashboard fills the desktop viewport with bounded card scrolling and returns to document flow at 980 px and below; no tested route has document overflow |
| C-03 route frame | All 12 view containers use `product-route-panel` and one `route-title` |
| C-04 naming and IA | Central registry; Gantt is consistently Roadmap; Tasks is consistently Tasks; Kanban and Calendar breadcrumbs use Insight |
| C-05 active/action dialects | Router sets semantic active state; PM and governance navigation use visible responsive grids; existing primary/secondary/destructive roles are retained |
| C-06 surface and density | Shared surface scale; Analytics and Team Capacity align to compact route geometry; administration loses oversized field gaps |
| C-07 / M-08 route states | Shared state renderer adopted by the planning and analytics routes; password recovery gains Back to sign in |
| C-08 / M-10 regression coverage | Added route registry, shell navigation, route state, Calendar agenda, semantic frame, responsive route matrix, and expanded contrast coverage |
| M-03 nesting | Dashboard has no competing page scroll on desktop and constrains overflow to its data cards; Spaces and PM navigation no longer require hidden horizontal overflow |
| M-06 density | Desktop density preserved; compact-shell touch targets raised without enlarging dense data tables |
| M-07 semantics | Skip link, landmarks, route-level H1 headings, `aria-current`, `aria-hidden`, menu semantics, and reduced-motion contract added |
| M-09 technical foundation | Implemented with small vanilla ES modules and shared CSS; no framework migration or public API change |

## Route outcomes

- **Deliverables:** visual benchmark preserved; shell and semantics modernized around it.
- **Tasks:** shared frame and naming; empty editor no longer reopens without a selected task.
- **PM Command Center:** six focus choices use a visible 3-column desktop / 2-column compact grid.
- **Dashboard:** fills the desktop viewport; the main project section receives 55% and the three supporting cards receive 45% of the available card area. Tablet and mobile retain natural summary-to-detail page flow.
- **Program Dashboard:** shared frame and route metadata aligned.
- **Kanban:** shared, instructive no-match state.
- **Calendar:** desktop month grid plus phone agenda; filters and month navigation reflow without collision.
- **Roadmap:** consistent naming and shared first-run/no-result states.
- **Team Capacity:** compact field/action geometry and responsive stacking.
- **Spaces / Access:** shared frame; local governance and platform tools use visible responsive grids instead of hidden scrollers.
- **Usage Analytics:** shared route frame, surface geometry, and restricted/unavailable states.
- **Authentication / reset:** focused auth design retained; recovery now has an explicit return path.

## Validation contract

Automated coverage includes:

- ESLint over UI modules and browser tests;
- 131 Vitest unit tests across 21 files;
- UI coverage report generation;
- route-module/test mapping check;
- Playwright route, authentication, theme contrast, responsive shell, and route-frame checks;
- 390, 768, 1,024, and 1,440 px viewport contracts;
- no unintended document horizontal overflow;
- reachability of every member route and session action;
- all 12 static route frames and headings;
- responsive Calendar agenda and hidden desktop grid;
- desktop Dashboard viewport fill, 55% primary allocation, and three-column supporting region;
- dark and light contrast samples including Calendar and Roadmap.

Manual rendered QA used representative Program, Project, and Solution data in a disposable SQLite smoke workspace. Deliverables, Tasks, PM Command Center, Dashboard, Calendar, Team Capacity, and Spaces were visually inspected in dark and light themes, with all route geometry measured at the four target widths.

## Preserved behavior and boundaries

- Backend APIs, schemas, authentication policy, authorization policy, telemetry, data models, and deployment configuration were not changed.
- Existing route paths remain valid, including the Access-to-Spaces alias.
- Dense desktop tables retain local horizontal overflow where their data model requires it.
- The upgrade does not introduce a framework, icon dependency, palette replacement, glass effects, or global density reduction.

## Closure ledger

- **Fixed now:** all consistency findings C-01 through C-08 and modernization framework items M-01 through M-10 at the shared-contract level.
- **Flagged for product-led follow-up:** optional compact/comfortable density preferences and whether Roadmap/Kanban need additional domain-specific phone modes beyond local scrolling and current adaptive states.
- **Not verified:** assistive-technology screen-reader walkthrough, every destructive modal variant, slow-network transitions, and non-Chromium browser rendering.
- **Out of scope:** backend behavior, data-model changes, product-policy changes, framework migration, deployment, and production rollout.

The shared frontend contract is ready for product review in the local smoke environment. Any next pass should be a focused follow-up audit based on reviewer feedback rather than another general modernization sweep.
