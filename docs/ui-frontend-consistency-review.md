# UI Frontend Consistency Review

**Review mode:** full-surface frontend review
**Date:** 2026-07-19
**Benchmark:** the current Deliverables view
**Implementation changes:** none; this document is the deliverable

## Executive assessment

SIPM already has a recognizable product language: a compact control-room shell, dark and light themes, blue-gray surfaces, small high-density controls, hierarchical data tables, and restrained status color. The Deliverables view is the clearest expression of that language and should remain the benchmark.

The frontend does not yet behave as one consistent page system. It behaves as three related systems:

1. **Operational workbench:** Deliverables, Tasks, Program Dashboard, and most of PM Command Center.
2. **Planning surfaces:** Kanban, Calendar, Gantt, and Dashboard, each with its own layout and scrolling rules.
3. **Administration:** Spaces, Team Capacity, and Usage Analytics, which use larger radii, more nested cards, and looser spacing.

The gap is not a need for a redesign. It is a need to standardize route anatomy, naming, responsive navigation, scrolling, surface depth, control hierarchy, and state presentation around the patterns that already work on Deliverables.

## Scope and evidence

The review covered:

- All 12 router entries: `master`, `gantt`, `tasks-workbench`, `dashboard`, `program-dashboard`, `pm-dashboard`, `kanban`, `calendar`, `team-capacity`, `spaces`, `access`, and `analytics` ([router.js](../src/main/ui/js/shell/router.js#L19)).
- The authentication, registration, password-reset, lobby, modal, and shared-shell surfaces.
- Populated and empty states using a temporary local workspace with a program, project, solution, task, member, and global-admin access.
- Dark and light themes.
- Desktop, 768 px tablet, and 390 px phone viewports.
- Shared CSS tokens, route stylesheets, markup, rendering modules, unit tests, and end-to-end tests.

`access` was assessed as an alias rather than an independent visible page because the router deliberately maps it to the Spaces DOM and navigation entry ([router.js](../src/main/ui/js/shell/router.js#L201)). Populated agent-approval diffs, destructive confirmation variants, slow-network transitions, and cross-browser rendering were not visually exercised.

## What the Deliverables benchmark gets right

Deliverables establishes a strong foundation worth preserving:

- One route frame with breadcrumb, title, tools, search, and data canvas ([index.html](../src/main/ui/index.html#L225)).
- A subtle blueprint grid that adds identity without competing with the data.
- A clear Program → Project → Solution hierarchy with restrained semantic accents.
- Compact table geometry backed by shared tokens: 26 px header, 30 px row, 28 px compact control, and 8 px route surfaces ([base.css](../src/main/ui/styles/base.css#L151)).
- Local horizontal overflow for a legitimately wide data table, rather than allowing the document itself to overflow.
- Closely matched dark and light themes driven by variables instead of duplicated markup.

The desired end state is not “make every page a table.” It is “make every page feel built from the same shell, hierarchy, density, control, and state rules.”

## Findings

### C-01 — High · must-fix — The responsive shell hides navigation and session actions

**Evidence**

- At 390 px, the navigation rail measured 1,106 px of scroll content in a 390 px viewport. The topbar measured 728 px inside a 368 px client width.
- At 768 px, the converted horizontal navigation consumed roughly the first quarter of the screen vertically before route content began.
- Admin destinations, “Show Completed,” sign out, and theme controls were off-screen with no visible overflow cue.
- The responsive rule turns both the sidebar and topbar into scrollbar-less horizontal scrollers ([workbench-admin.css](../src/main/ui/styles/routes/workbench-admin.css#L1065)). The shell switches to one column but does not establish an explicit compact row contract ([base.css](../src/main/ui/styles/base.css#L345)).

**Risk**

Core navigation and account controls are discoverable on desktop but effectively hidden on smaller screens. Each route therefore presents a different apparent feature set depending on which items happen to be at the start of the scroll position.

**Smallest reasonable fix**

- Add an explicit `grid-template-rows: auto auto 1fr` or equivalent shell contract at the breakpoint.
- Keep the current route group visible and move other route groups behind one labeled “More” or navigation drawer control.
- Keep Create and active-space context in the topbar; move completion visibility, theme, user, and sign-out into one account/overflow menu.
- Preserve native horizontal scrolling only for data regions, and add a visible affordance anywhere horizontal navigation remains.

### C-02 — High · should-fix — Routes use incompatible scrolling contracts

**Evidence**

- Deliverables, Tasks, and Program Dashboard use a bounded route with local horizontal table scrolling.
- Dashboard uses a fixed-height route plus independent scrollable table shells ([dashboard.css](../src/main/ui/styles/routes/dashboard.css#L13), [dashboard.css](../src/main/ui/styles/routes/dashboard.css#L516)).
- Calendar uses a scrollable route region containing seven columns with a minimum of 120 px each ([kanban-calendar.css](../src/main/ui/styles/routes/kanban-calendar.css#L136)). At 390 px, the calendar canvas measured 898 px wide and the document widened to 459 px, producing both local and document-level scrolling.
- On desktop, Calendar and Dashboard expose nested vertical scrollbars while the browser page also scrolls.

**Risk**

Users must relearn whether the page, panel, table, or calendar is the scroll owner on every view. Nested scrollbars also make keyboard, trackpad, and touch navigation less predictable.

**Smallest reasonable fix**

Adopt one route contract:

- The document owns vertical scrolling by default.
- A bounded data region may own horizontal scrolling.
- A bounded data region may own vertical scrolling only when it has a sticky header and a clear visual boundary.
- No route may cause document-level horizontal overflow at 390, 768, or 1,024 px.

### C-03 — Medium · should-fix — The shared route frame is optional rather than canonical

**Evidence**

Deliverables, Gantt, Dashboard, Program Dashboard, PM Command Center, Kanban, and Calendar use `panel product-route-panel`. Tasks, Usage Analytics, Team Capacity, and Spaces use only `panel` ([index.html](../src/main/ui/index.html#L225), [index.html](../src/main/ui/index.html#L295), [index.html](../src/main/ui/index.html#L565), [index.html](../src/main/ui/index.html#L1020)). The missing modifier changes the grid, background, border treatment, radius, and perceived density.

**Risk**

The route frame communicates product identity, so omitting it makes otherwise related views look like separate applications. It also encourages each route stylesheet to rebuild spacing and surface rules.

**Smallest reasonable fix**

Create one canonical `route-frame` primitive based on `product-route-panel`. Allow explicit `route-frame--workbench`, `--planning`, and `--admin` density modifiers, but keep the same outer background, title placement, border, and breakpoint behavior.

### C-04 — Medium · should-fix — Navigation, breadcrumb, page title, and path labels drift

**Evidence**

- Sidebar “Tasks” opens the page titled “Tasks Workbench” ([index.html](../src/main/ui/index.html#L113), [index.html](../src/main/ui/index.html#L295)).
- Sidebar “Gantt” opens the page titled “Project Roadmap” ([index.html](../src/main/ui/index.html#L123), [index.html](../src/main/ui/index.html#L271)).
- Kanban and Calendar sit in the sidebar’s Insight group but both breadcrumbs say Work ([index.html](../src/main/ui/index.html#L116), [index.html](../src/main/ui/index.html#L967), [index.html](../src/main/ui/index.html#L989)).
- `access` is a routable module and prefetch target, but it renders through Spaces and has no independent navigation item ([router.js](../src/main/ui/js/shell/router.js#L49), [router.js](../src/main/ui/js/shell/router.js#L201)).

**Risk**

Inconsistent naming weakens wayfinding, makes help text harder to write, and creates avoidable ambiguity in analytics and tests.

**Smallest reasonable fix**

Define route metadata once:

```js
{
  id: "gantt",
  navLabel: "Roadmap",
  pageTitle: "Project Roadmap",
  section: "Insight",
  path: "/gantt",
}
```

Generate sidebar labels, breadcrumbs, document titles, route analytics labels, and tests from that source. Choose one public label per route; a longer explanatory subtitle can carry the nuance.

### C-05 — Medium · should-fix — Active states and action hierarchy use too many dialects

**Evidence**

- Deliverables uses compact secondary toolbar buttons and a menu.
- Tasks uses a seven-button preset row plus a separate saved-view toolbar.
- PM Command Center implements six focus choices as labels backed by hidden radio inputs ([index.html](../src/main/ui/index.html#L525)).
- Spaces has global navigation, governance-section navigation, and a second four-item platform tool tab set on the same page ([spaces/render.js](../src/main/ui/js/routes/spaces/render.js#L1269), [spaces/render.js](../src/main/ui/js/routes/spaces/render.js#L1361)).
- Router navigation updates only the `.active` class; it does not update `aria-current` on the primary route control ([router.js](../src/main/ui/js/shell/router.js#L264)).

**Risk**

Buttons, filters, tabs, navigation, and links look similar while behaving differently. Important actions compete with filters, and selected state is not consistently communicated semantically.

**Smallest reasonable fix**

Standardize five control roles: primary action, secondary action, quiet action, destructive action, and selection control. Use one segmented-control pattern for mutually exclusive filters, one tab pattern for content switching, and one menu pattern for secondary route actions. Add `aria-current="page"` to the active primary route item.

### C-06 — Medium · should-fix — Surface depth and density diverge most in administration

**Evidence**

- The route token specifies an 8 px data-surface radius ([base.css](../src/main/ui/styles/base.css#L169)).
- Usage Analytics cards set 14 px directly ([analytics.css](../src/main/ui/styles/routes/analytics.css#L25)).
- Space Governance independently uses 11, 12, 14, 16, 18, and 20 px radii, often through several nested bordered containers ([space-governance.css](../src/main/ui/styles/routes/space-governance.css#L585), [space-governance.css](../src/main/ui/styles/routes/space-governance.css#L665)).
- Team Capacity uses a 1 cm column gap, 220–360 px fields, and 150–240 px buttons rather than the route spacing and control scales ([team-capacity.css](../src/main/ui/styles/routes/team-capacity.css#L59)).

**Risk**

Admin views feel newer but also heavier and less efficient than the work views. The light theme amplifies the mismatch because nearly every nested boundary becomes visible.

**Smallest reasonable fix**

Use a short shared scale: 8 px for data regions, 12 px for cards and navigation groups, 14 px for dialogs, and 999 px only for pills. Use the existing 4/8/12/16 spacing rhythm and remove borders from child containers when the parent already establishes grouping.

### C-07 — Medium · should-fix — Empty and first-run states are inconsistent

**Evidence**

- Deliverables provides a useful Quick Start with next actions.
- Gantt shows one dashed sentence.
- Calendar renders an empty month grid with no explanation or alternate next step.
- Dashboard renders empty table shells with visible internal scrollbars.
- Kanban renders a large mostly empty board without distinguishing “no data,” “no matches,” or “unscheduled.”

**Risk**

The same absence of data can look like onboarding, a successful zero state, a filtering result, or a rendering failure depending on the route.

**Smallest reasonable fix**

Create shared state variants: first run, no records, no filter matches, unscheduled records, loading, and recoverable error. Each variant should provide a title, one sentence, and at most one primary plus one quiet action.

### C-08 — Medium · should-fix — Existing tests do not guard the visible consistency contract

**Evidence**

- The contrast suite samples eight routes but omits Calendar, Gantt, and Usage Analytics ([theme-contrast.spec.js](../src/main/ui/test/e2e/theme-contrast.spec.js#L192)).
- Navigation smoke coverage opens only Dashboard and Program Dashboard ([navigation-smoke.spec.js](../src/main/ui/test/e2e/navigation-smoke.spec.js#L28)).
- The current smoke suite has no 768 px or 390 px geometry assertions.

The current checks all passed: ESLint, 124 Vitest tests, three Playwright smoke tests, and the existing dark/light contrast checks. Those successes establish functional health, but not visual consistency.

**Risk**

Responsive overflow, clipped actions, title drift, and nested scrolling can regress while every current check remains green.

**Smallest reasonable fix**

Add a route-matrix smoke test with durable invariants rather than brittle full-page snapshots:

- active route and title are visible;
- document width does not exceed viewport width at 390 and 768 px;
- account/navigation actions remain reachable;
- one route header exists;
- designated data regions, not the document, own horizontal overflow;
- dark and light token contrast samples cover every route family.

## View-by-view consistency matrix

| Surface | Fit to Deliverables language | Main consistency gap | Recommended alignment |
|---|---|---|---|
| Deliverables | Benchmark | None material | Preserve as the reference implementation |
| Tasks | Strong | Different route frame; excessive competing filter rows; title drift | Adopt canonical route frame and segmented/filter hierarchy |
| PM Command Center | Strong | Six-item focus rail overflows on desktop; small ad hoc footer links | Use shared tabs/overflow pattern and quiet-link row |
| Dashboard | Partial | Bespoke gradient card heads and several nested scroll regions | Keep analytical cards, align route header, surface depth, and scroll ownership |
| Program Dashboard | Strong | Export actions are visually weaker than equivalent actions elsewhere | Preserve table hierarchy; normalize actions and toolbar |
| Kanban | Partial | Panel-inside-panel depth and weak empty-state distinction | Flatten one surface layer and use shared state presentation |
| Calendar | Weak | Header controls collide at phone width; nested and document overflow | Switch to responsive agenda/list mode and canonical route header |
| Gantt | Partial | “Gantt” versus “Project Roadmap”; sparse empty state | Resolve naming and use shared state component |
| Spaces / Access | Partial | Triple navigation hierarchy, large radius range, loose density | Keep its clearer admin grouping but reduce layers and share shell tokens |
| Team Capacity | Weak | Oversized fields/actions, 1 cm gap, three separate form/table blocks | Use a compact member toolbar plus one roster data surface |
| Usage Analytics | Partial | Standalone 14 px card system and no product route frame | Reuse shared KPI and table cards; retain useful two-column analytics layout |
| Authentication | Good, intentionally separate | No shared route context needed | Preserve focused card; align button, field, and message primitives |
| Password reset | Partial | No visible return-to-sign-in action | Add a quiet “Back to sign in” action and shared auth feedback layout |

## Canonical route anatomy

Every routed view should follow this structural contract:

1. **Route frame** — one outer product surface.
2. **Route header** — breadcrumb, one public title, optional subtitle, and one compact action zone.
3. **Route toolbar** — filters, view selection, import/export, and secondary actions.
4. **Route summary** — optional KPIs using one shared card primitive.
5. **Route content** — table, board, calendar/agenda, chart, form, or admin workbench.
6. **Route state** — one shared loading/empty/error pattern inside the content boundary.

Recommended shared geometry:

| Element | Compact desktop | Small viewport |
|---|---:|---:|
| Route panel padding | 10–12 px | 10 px |
| Data surface radius | 8 px | 8 px |
| Card/navigation radius | 12 px | 10–12 px |
| Standard control height | 32–34 px | 40–44 px touch target |
| Compact data control | 28 px | 40 px touch target |
| Table header / row | 26 / 30 px | Retain table density inside local horizontal scroll |

## Recommended sequence

1. **Shell and route metadata:** centralize labels/sections/titles; fix responsive navigation and topbar reachability.
2. **Frame and scrolling:** apply the canonical route frame and scroll contract to every route.
3. **Divergent routes:** migrate Calendar, Dashboard, Team Capacity, then Spaces/Analytics.
4. **State and semantics:** unify loading/empty/error states, active semantics, and route feedback.
5. **Regression coverage:** add the route matrix at desktop, tablet, and phone widths.

## Closure ledger

- **Fixed now:** two review documents; no UI behavior was changed.
- **Flagged for follow-up:** all C-01 through C-08 findings.
- **Not verified:** populated agent-approval review, slow/error transitions, every modal variant, cross-browser rendering, and assistive-technology walkthroughs.
- **Out of scope:** backend behavior, product-policy changes, data-model changes, and implementation of the recommended UI work.

Another pass is warranted after the first implementation slice. Rerun in **contract alignment** mode on the shared shell, route metadata, and 390/768 px overflow invariants before migrating individual views.
