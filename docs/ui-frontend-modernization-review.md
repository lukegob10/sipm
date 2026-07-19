# UI Frontend Modernization Review

**Review mode:** modernization and product-direction review
**Date:** 2026-07-19
**Reference direction:** evolve the current Deliverables view
**Implementation changes:** none; this document is the deliverable

## Executive direction

Modernize SIPM by refining its existing control-room identity, not by replacing it. The Deliverables view already has the right core qualities: compact information density, a quiet blue-gray palette, subtle blueprint texture, strong hierarchy, restrained status color, and a data-first layout. Those qualities should become the system-wide baseline.

The highest-value modernization work is structural:

1. Make navigation and primary actions reachable at every viewport.
2. Give every route the same header, toolbar, surface, and state grammar.
3. Let complex views adapt their presentation instead of shrinking desktop layouts.
4. Reduce nested cards, borders, shadows, and navigation layers.
5. Add semantic and responsive guarantees to the shared component layer and tests.

This direction produces a more current interface without making the product less dense, less distinctive, or more decorative.

## Design principles

### Preserve

- The Deliverables page's compact, data-first composition ([index.html](../src/main/ui/index.html#L225)).
- The subdued dark and light themes and existing blue-gray foundation ([base.css](../src/main/ui/styles/base.css#L1)).
- The blueprint-grid texture as a quiet product signature.
- Hierarchical tables for program, project, solution, and work relationships.
- Semantic color for state, risk, and health rather than decoration.
- Vanilla JavaScript modules and route-specific CSS; modernization does not require a framework rewrite.

### Improve

- Responsive navigation and adaptive view modes.
- Clear action priority and progressive disclosure.
- Consistent route anatomy, typography, spacing, radii, and surface depth.
- Empty, loading, error, success, and first-run feedback.
- Keyboard, focus, reduced-motion, landmark, and active-route semantics.
- Visual regression coverage at realistic desktop, tablet, and phone widths.

### Avoid

- Glassmorphism, large gradients, excessive animation, or decorative dashboards.
- A wholesale palette or brand replacement.
- Enlarging every control and reducing desktop information density.
- Adding a large icon library only to make the interface look newer.
- Rebuilding the frontend in another framework before fixing the product contract.

## Modernization findings

### M-01 — High · must-fix — Replace the small-screen shell with an intentional navigation model

**Observed**

Below 900 px, the desktop sidebar becomes a horizontally scrolling navigation strip and hides its scrollbar ([workbench-admin.css](../src/main/ui/styles/routes/workbench-admin.css#L1065)). At 390 px, that strip measured 1,106 px wide inside a 390 px viewport. The topbar measured 728 px of content inside 368 px and also hid its scrollbar. Session and administrative actions were therefore present in the DOM but not visibly reachable, while the navigation consumed a large band above the route.

**Modern direction**

- At 768–1,023 px, use a compact app bar with a clear workspace switcher and a labeled navigation disclosure.
- At 767 px and below, use a stable app bar plus drawer or “More” sheet.
- Keep the current route visible in the app bar.
- Move account, theme, sign-out, and administrative actions into a reachable account menu.
- Never depend on an invisible horizontal scrollbar for global navigation.
- Preserve desktop sidebar behavior at 1,024 px and above.

**Acceptance criteria**

- Every route and session action is reachable by pointer and keyboard at 390, 768, 1,024, and 1,440 px.
- Global navigation never causes document-level horizontal overflow.
- The current route and expanded/collapsed state are exposed semantically.

### M-02 — High · must-fix — Give Calendar a mobile-native presentation

**Observed**

The month grid enforces seven columns with a 120 px minimum per day ([kanban-calendar.css](../src/main/ui/styles/routes/kanban-calendar.css#L150)). At 390 px, the calendar content measured 898 px wide and the document measured 459 px, producing both local and document scrolling. Header filters collided with route context, and the empty month provided little guidance.

**Modern direction**

- Retain the month grid for desktop.
- Switch to agenda/list presentation below roughly 700 px.
- Offer a compact day or three-day mode on medium widths if user workflows need it.
- Place date navigation and view selection in the route toolbar.
- Use a single local scroll owner and keep the page itself free of horizontal overflow.
- Give empty dates a quiet, consistent state rather than a blank canvas.

The same adaptive principle should guide Gantt and Kanban: preserve their native spatial models on large screens, but provide useful compact alternatives rather than miniature desktop canvases.

### M-03 — Medium · should-fix — Reduce navigation and surface nesting

**Observed**

- Spaces combines global navigation, an internal governance navigation, and a four-item platform-access tab row ([render.js](../src/main/ui/js/routes/spaces/render.js#L1269)).
- PM Command Center uses six peer focus controls in a narrow rail.
- Dashboard places scrollable table shells inside cards inside a fixed-height route ([dashboard.css](../src/main/ui/styles/routes/dashboard.css#L13)).
- Kanban presents a route panel, inner panel, columns, and cards before there is any data.

**Modern direction**

- Limit a normal route to global navigation plus one local navigation level.
- Move infrequent configuration into a disclosure, side panel, or dedicated subroute.
- Let the route surface be the canvas; add cards only when they establish a meaningful group.
- Keep a maximum of two visible elevation levels in ordinary content.
- For six or more peer tabs, use a responsive tab list with a visible overflow affordance or a compact selector.

This is the most important visual simplification after responsive navigation. Removing redundant boxes will make the existing hierarchy feel more modern than adding effects would.

### M-04 — Medium · should-fix — Establish a short, deliberate surface scale

**Observed**

Shared route surfaces use an 8 px radius, Usage Analytics uses 14 px cards, and Spaces introduces radii from roughly 11 to 20 px. In the light theme, the combination of nested borders, shadows, and background changes is more visible than it is in the dark theme. Team Capacity also uses a 1 cm field gap and large fixed action widths, making it feel like a separate application ([workbench-admin.css](../src/main/ui/styles/routes/workbench-admin.css#L59)).

**Modern direction**

Use a compact surface vocabulary:

| Role | Suggested geometry | Treatment |
|---|---:|---|
| Data canvas / table | 8 px | Border or background distinction, normally no shadow |
| Card / local navigation | 12 px | One quiet surface change |
| Dialog / popover | 14 px | Elevation reserved for content above the page |

Avoid stacking border, shadow, and tonal change unless the layer truly floats. In the light theme, use at most one subtle page-level shadow and let spacing carry more of the grouping burden.

### M-05 — Medium · should-fix — Standardize action hierarchy and progressive disclosure

**Observed**

Deliverables, Tasks, Program Dashboard, PM Command Center, and Spaces use different visual treatments for equivalent route actions. Import/export can be prominent, quiet, or separated. Tasks exposes presets and filters in multiple rows. PM uses radio-backed labels for focus navigation. Some administrative actions use fixed-width buttons that dominate the content.

**Modern direction**

Define four action roles:

1. **Primary:** one preferred route action, if the route has one.
2. **Secondary:** common supporting action.
3. **Quiet:** navigation, view change, or reversible utility.
4. **Destructive:** explicit and isolated from routine actions.

Group import/export under one labeled data menu where both are present. Put low-frequency exports and configuration in an overflow menu. Keep icons paired with text until the meaning is unambiguous, and supply accessible names for icon-only controls.

### M-06 — Medium · should-fix — Modernize density without losing the compact desktop advantage

**Observed**

The shared tokens use 13 px body text and 11 px labels, metadata, table headers, and chips ([base.css](../src/main/ui/styles/base.css#L151)). That density works in the Deliverables data table, but 11 px copy is used too broadly in tabs, navigation, supporting text, and low-priority actions. Small-screen controls retain desktop dimensions even though the navigation rearranges.

**Modern direction**

- Keep 12–13 px type in dense tables where scanning matters.
- Raise non-tabular labels and supporting text to a 12 px minimum.
- Use 13–14 px for section headings and 20–23 px for route titles.
- Retain 28–34 px desktop controls in dense toolbars.
- Provide 40–44 px touch targets at phone widths without necessarily enlarging visible glyphs.
- Consider compact/comfortable density modes only after real user demand; do not make the default less efficient preemptively.

### M-07 — Medium · should-fix — Make semantics and accessibility part of the visual system

**Observed**

Theme contrast tests pass for the routes they cover, and visible focus behavior is generally serviceable. However, router updates toggle only a CSS class and do not set `aria-current` ([router.js](../src/main/ui/js/shell/router.js#L264)). Routed page titles use second-level headings, global navigation overflow has no visible cue, and reduced-motion behavior is not expressed as a consistent global contract.

**Modern direction**

- Add a skip link and explicit navigation/main landmarks.
- Expose the active route with `aria-current="page"`.
- Establish one page-heading strategy after authentication.
- Use correct tab, menu, disclosure, and selection semantics instead of styling generic labels as controls.
- Keep focus rings visible in both themes and across every interactive state.
- Add a global `prefers-reduced-motion` rule and avoid motion-dependent feedback.
- Make scrollability apparent whenever content intentionally overflows.

### M-08 — Medium · should-fix — Treat product states as first-class components

**Observed**

Empty routes vary from a dashed Gantt message to a blank Calendar, empty tables, open Kanban columns, and introductory copy. The user cannot always distinguish “no data yet,” “no filter matches,” “not loaded,” and “not authorized.” Password reset also lacks a visible path back to sign-in.

**Modern direction**

Create shared variants for:

- first run, with one clear next action;
- no matching results, with filter-reset guidance;
- loading, reserved for genuinely asynchronous content;
- recoverable error, with retry and retained context;
- permission-limited content, with a plain-language explanation;
- success and background activity, using a consistent toast/inline-feedback policy.

Keep these states inside the content boundary so headers and navigation do not jump. Add a quiet “Back to sign in” action to password recovery.

### M-09 — Medium · should-fix — Build the system from shared primitives, not a framework migration

**Observed**

The current frontend already has useful shared tokens and modular route styles, but route metadata, frame adoption, tabs, cards, and empty states are implemented inconsistently. Responsive shell rules live in a route stylesheet rather than with the shell. The divergence is architectural organization, not an inherent limitation of vanilla JavaScript.

**Modern direction**

- Centralize route metadata: path, section, navigation label, breadcrumb, public title, permissions, and view element.
- Add small shared render helpers for route header, toolbar, tabs, KPI cards, data state, and action groups.
- Move shell and breakpoint rules into shell-owned CSS.
- Keep route files responsible for domain layout, not global navigation behavior.
- Migrate one view at a time behind stable DOM and behavior contracts.

Do not introduce a component framework unless a separate engineering case demonstrates that runtime state complexity—not visual inconsistency—is the limiting factor.

### M-10 — Medium · should-fix — Add a visual contract to the test suite

**Observed**

The existing suite is healthy: 124 UI unit tests, three smoke tests, and current theme-contrast checks passed during this review. The end-to-end coverage does not currently assert route geometry at 390 or 768 px. Calendar, Gantt, and Analytics are omitted from the contrast route sample, while navigation smoke exercises only a small subset of routes.

**Modern direction**

Add a route matrix at 1,440, 1,024, 768, and 390 px that verifies:

- route title, breadcrumb, and active navigation agree;
- primary and session actions are visible or reachable through a labeled menu;
- the document has no unintended horizontal overflow;
- exactly one expected content region owns local overflow;
- keyboard focus reaches actions in a stable order;
- loading, first-run, no-match, and error states preserve route geometry;
- dark and light contrast coverage includes every route family.

Use screenshot assertions selectively for the shell, Deliverables benchmark, Calendar adaptive view, Dashboard, and Spaces—not for every dynamic data row.

## Proposed system specification

### Color and character

- Keep the current blue-gray base and one cool blue interaction accent.
- Reserve green, amber, red, and similar hues for semantic status.
- Retain the blueprint grid at low contrast on route canvases.
- Prefer solid, quiet surfaces to gradients or translucent glass.

### Layout by viewport

| Viewport | Shell | Route behavior |
|---|---|---|
| ≥ 1,024 px | Current left sidebar | Compact route frame and desktop-native work surface |
| 768–1,023 px | Compact app bar or deliberately collapsible navigation | Two-column content may collapse; actions remain labeled and reachable |
| ≤ 767 px | App bar plus drawer/More and account menu | Single-column hierarchy; route-specific adaptive mode; 40–44 px touch targets |

### Route anatomy

1. Breadcrumb and one public route title.
2. Compact action zone with one primary action at most.
3. Optional toolbar for search, filters, view mode, and data operations.
4. Optional KPI summary using a shared primitive.
5. One content canvas with an explicit scroll owner.
6. Shared loading, empty, error, and permission states.

## View-by-view modernization targets

| View | Preserve | Modernize next |
|---|---|---|
| Deliverables | Blueprint grid, hierarchy, compact table, action grouping | Make tools reflow cleanly and keep search/actions reachable; consider a frozen hierarchy column for wide data only after usability testing |
| Tasks | Dense workbench and saved-view capability | Collapse presets and advanced filters into a filter rail/drawer; use one route title |
| PM Command Center | Strong control-room composition and responsive content cards | Replace six-item overflow rail with responsive tabs/selector; normalize export and footer actions |
| Dashboard | Useful analytical summaries | Remove nested scroll owners, reduce gradient headers, and prioritize summary-to-detail flow |
| Program Dashboard | Table hierarchy close to Deliverables | Normalize action hierarchy and shared KPI/table primitives |
| Kanban | Spatial board model | Flatten one surface layer, clarify empty columns, and keep board overflow local and visible |
| Calendar | Month grid on desktop | Add agenda/list mode on phones and reorganize toolbar controls |
| Gantt | Roadmap concept | Choose one public name, add useful first-run guidance, and offer compact milestone/list mode |
| Spaces / Access | Clear governance scope and useful platform segmentation | Limit visible navigation to one local level, reduce card depth, and prevent tab truncation |
| Team Capacity | Member, availability, and capacity concepts | Replace oversized form blocks with a compact member toolbar, roster table, and contextual editor |
| Usage Analytics | Clean KPI and breakdown concept | Adopt shared route frame and KPI cards; retain its useful two-column structure |
| Authentication / reset | Focused standalone card | Reuse shared fields/messages and restore a visible return-to-sign-in path |

## Delivery sequence

### Phase 1 — Foundation and reachability (1–2 implementation weeks)

- Centralize route metadata.
- Move responsive shell behavior into shell-owned styles.
- Implement the tablet/phone navigation and account patterns.
- Establish route frame, action hierarchy, typography, radius, and state tokens.
- Add no-document-overflow and action-reachability checks.

### Phase 2 — Shared frame and divergent layouts (2–4 implementation weeks)

- Align Tasks, Analytics, Team Capacity, and Spaces with the route frame.
- Give Calendar its agenda mode and one-scroll contract.
- Simplify Dashboard scroll ownership and surface depth.
- Resolve Gantt/Roadmap naming and route-state presentation.

### Phase 3 — Progressive disclosure and polish (2–4 implementation weeks)

- Flatten Spaces and PM Command Center navigation.
- Normalize import/export, overflow menus, KPI cards, tabs, and feedback.
- Complete landmark, focus, reduced-motion, and touch-target work.
- Add the full route/viewpoint test matrix and selected visual snapshots.

## Definition of done

The modernization is complete when:

- Every route and session action is reachable at the four target widths.
- No route produces unintended document-level horizontal overflow.
- Navigation label, breadcrumb, public title, and active state come from one route definition.
- Each route has one deliberate content scroll owner.
- Shared controls and surfaces use the short type, radius, and action scales.
- First-run, no-match, loading, error, permission, and success states are distinguishable.
- Dark and light themes meet the agreed contrast target across every route family.
- Keyboard, focus, reduced-motion, and active-route semantics pass automated checks and a manual walkthrough.
- The Deliverables view still feels compact and recognizable after the shared system is applied.

## Closure ledger

- **Preserve:** the Deliverables-led visual character, compact data density, themes, hierarchy, and semantic color.
- **Modernize first:** responsive shell reachability and Calendar adaptation.
- **Modernize next:** shared route frame, scroll ownership, action hierarchy, surface scale, state components, and accessibility semantics.
- **Defer unless separately justified:** framework migration, wholesale rebrand, large icon dependency, animated or glass-like visual effects, and global density reduction.
- **Not verified:** populated agent-approval changes, slow/error transitions, every modal variant, cross-browser rendering, and an assistive-technology walkthrough.

After Phase 1, rerun a contract-alignment review at 390, 768, 1,024, and 1,440 px before migrating the more complex route bodies.
