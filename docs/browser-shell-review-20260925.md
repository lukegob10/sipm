# Browser shell review — 2026-09-25

This is a **full-surface review of the delegated browser shell**, with bounded
correctness and performance fixes. The intended result is a shell that reaches
sign-in reliably, keeps requests and late responses attached to the correct
session and space, preserves unsaved editor input during refresh, and supports
keyboard use on compact screens. This report does not close the whole-repository
review or claim production latency improvements.

Baseline: `82c69be2e71faef18c1a99b5e820aac8e6a78cb4`.
Branch: `codex/browser-shell-review`.
Worktree: `C:/Users/Luke Goblirsch/.codex/worktrees/d81d/sipm`.

Two explicitly requested subagents participated, both using `gpt-6-luna` with
`max` reasoning: `login_startup` reviewed session/bootstrap/context behavior;
`shell_navigation` reviewed navigation, routing, menus, dialogs, and switchers.
The parent reviewed their changes, integrated the refresh fixes, and ran the
combined checks. The `clean-code-review` skill's safety, comprehensive, frontend,
JavaScript, HTML, Python, testing, and performance passes informed this work.

## Findings and closure ledger

| Severity / priority | Evidence and impact | Smallest fix / status |
| --- | --- | --- |
| High / must-fix | Editable names were interpolated into option HTML without escaping. Rendering probes created forged options from closing-option labels and extra datalist markup from quoted capacity names. | Use existing `escapeHtml` for values and labels in all option builders in `app.js`. Nine regressions execute the actual app builders and verify literal values/text, no injected attributes, and assignee propagation. **Fixed now.** |
| High / must-fix | A throwing `localStorage` getter aborted activity-controller construction and left startup visible indefinitely. Chromium reproduction reached no sign-in form and raised `SecurityError`. | Resolve storage inside the existing guarded write in `shell/activity-session.js`. Patched Chromium reaches sign-in without a page error. **Fixed now.** |
| High / must-fix | Store refresh reopened Project and Solution forms and refilled Task fields regardless of unsaved changes. A real websocket update erased all three drafts; rebuilding selects also reset a changed Solution project. | Reuse the existing draft guard for Task, preserve dirty forms and selections, and refresh clean forms through `shell/data-store.js` and `app.js`. **Fixed now.** |
| High / must-fix | Space-context work and session refresh could finish after a logout, replacement login, or space switch. A retried request could acquire the current space header instead of its original space. | Guard context application and switch completion by operation/session identity. Recheck session lifetime before replay and retain the original effective request headers in `shell/session.js`. Legitimate server-selected fallback spaces still work. **Fixed now.** |
| High / must-fix | The compact sidebar was visually offscreen while its controls remained keyboard reachable. | Apply `inert` and `aria-hidden` while closed; restore focus and recompute state at viewport changes in `shell/navigation.js`. **Fixed now.** |
| Medium / should-fix | Concurrent telemetry flushes could resend an in-flight batch or discard events queued during that request. A backlog larger than the server's combined limit of 100 was sent as one rejected batch. | Reserve at most 100 records before awaiting transport, restore only a failed reserved batch, and retain newly queued records in `shell/telemetry.js`. **Fixed now.** |
| Medium / should-fix | Deferred focus could reach a closed confirmation or switcher. Replacing a confirmation lost its opener; create/account menu transitions could leave hidden focus or steal focus from a newly opened dialog. | Guard deferred focus, preserve the confirmation opener, and close menus according to actual focus movement. Changes are in `shell/modal-shell.js`, `space-switcher.js`, `topbar-create.js`, and `navigation.js`. **Fixed now.** |
| Medium / should-fix | Team Capacity awaited its route module before starting an independent data read. | Start both operations together in `shell/router.js`. The deterministic 50 ms import / 80 ms data fixture completes in 80 ms instead of 130 ms. **Fixed now; this is a scheduling proxy, not production timing.** |
| Medium / should-fix | Task-delete callers marked the next refresh as ignorable before confirmation, so cancellation could suppress a later unrelated task update. | `app.js` now marks suppression inside `deleteTasksById` after confirmation. **Helper fixed now; full closure requires the UI team's paired removal of four premature caller markers.** |
| Low / should-fix | A URL sharing only the context-path prefix could be stripped as though it were inside the app. | Require an exact context path or a slash boundary in `shell/router.js`. **Fixed now.** |

The storage behavior is consistent with the documented possibility that access to
`window.localStorage` throws when persistence is blocked by browser policy:
[MDN localStorage exceptions](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage#exceptions).
The change preserves activity heartbeats and idle expiry; it does not weaken
authentication or require persistent browser storage.

## Coverage

| Domain | Reviewed / changed / limit |
| --- | --- |
| Startup and authentication | Reviewed app bootstrap, local login feedback, session refresh, activity lifetime, and failure paths. Changed storage access and late-result guards. Existing browser tests verify local login and session reopening retain their request-count contracts. No auth endpoint, password policy, or cookie changes. |
| State and data flow | Reviewed app context application, data-store refresh, form restoration, switch completion, and request retries. Changed dirty-state preservation and freshness guards. `live-sync.js` belongs to the coordinator's separate sync review and was not edited. |
| Navigation and interaction | Reviewed router, route registry, entrypoints, context paths, navigation, dialogs, create menu, account menu, and space switcher. Changed the defects above; registry and entrypoint contracts remain unchanged. |
| HTML, styling, and accessibility | Reviewed shell DOM wiring, index structure, base/framework styling, responsive navigation, focus/visibility behavior, and form use. Browser smoke covered compact and tablet shells. No style-only edits or DOM ID changes. |
| Performance | Reviewed startup graph and request sequencing, Team Capacity scheduling, telemetry batching, and refresh/render work. Static startup graph remains 37 modules under its 37-module guard; imported source stays within the 425,000-byte guard. No production p95 claim. |
| Security and reliability | Reviewed browser session/space attachment, rejected/stale responses, storage failure, telemetry concurrency, focus lifecycle, and option HTML construction. Escaped the shell's option values and labels after the coordinator identified the assignee sink; equivalent capacity, phase, team, and AI entity sinks were also covered. Server authorization, schemas, route APIs, and credentials were not changed. |
| Tests and workflow | Read contributing rules and relevant package/test entrypoints; checked route-module mapping, lint, focused UI and frontend contracts, and selected browser smoke. Full combined suites and coverage are the coordinator's integration responsibility. |
| Stale assets and structure | Ran the skill's repository inventory and stale-script helper. The initial inventory reported 116 JavaScript, 180 Python, 16 CSS, 1 HTML, 24 SQL files, and 8 scripts. Broad executable-file matches on Windows were treated as candidates, then checked against runtime imports and workflow use. No confirmed stale deletion was justified in this scope. New refresh helpers remain in an already loaded module. |

All changed runtime helpers have active call sites in the shell. Added test files
are test-only. There are no database, deployment, dependency, or migration changes
in this patch set. The existing SQL, backend, and infrastructure domains are
present in the repository but outside this delegated review.

## Validation and performance evidence

Checks below used the isolated worktree, the original checkout's dependency
installation, and a disposable SQLite/in-memory browser server on port 8772.
No production service, push, or deployment was used.

- **162 UI tests passed across 16 files:** session, context, data-store,
  editor-refresh, activity-session, telemetry, router, route-registry,
  route-entrypoints, shell-navigation, modal-shell, space-switcher, topbar-create,
  startup-assets, theme, and route-state.
- The subsequent option-escaping fix added **9 passing rendering regressions**
  in `app-selects.test.js`, each of which failed before the fix. Its verification
  also reran all 7 startup-assets cases and focused ESLint successfully. There
  are 171 distinct passing focused UI cases across these validation runs.
- **20 frontend contract tests passed:** live-sync/session, task-delete
  confirmation, topbar create, modal layout, and context-path routing.
- Route-module test mapping, focused ESLint, and staged whitespace checks passed.
- **11 existing Playwright cases passed:** recovery return to sign-in, failed
  startup recovery, local login usable without follow-up context requests,
  local login/project creation, three valid-session reopening cases, dashboard
  routes, Calendar navigation while earlier reads are pending, compact shell,
  and tablet shell. Windows emitted two socket-reset messages from the disposable
  server during the run; no test failed.
- Characterization regressions reproduced storage/telemetry failures, obsolete
  context application, and dirty-editor loss before the corresponding fixes.
  Draft restoration failed four of its six cases with the original algorithm;
  all six pass with the patch, including clean-form refresh and closed-form state.

The additional browser reproductions used actual application code and server
updates, with baseline source served in place only for the relevant module:

| Scenario | Baseline | Patched |
| --- | --- | --- |
| Storage getter throws, Chromium 390×844 | Startup visible, sign-in hidden, `SecurityError` | Sign-in visible, startup hidden, no page error |
| Dirty Project + remote websocket update | Unsaved name erased | Unsaved name preserved |
| Dirty Solution + remote websocket update | Unsaved name and changed project selection erased | Both preserved |
| Dirty Task + remote websocket update | Unsaved name erased | Name, assignee, and open editor preserved |
| Team Capacity: import 50 ms, data 80 ms, fake timer | Serial completion at 130 ms | Concurrent completion at 80 ms |
| Telemetry backlog of 107 records | Oversized 107-record batch | Batches of 100 and 7 |
| Actual app option builders, JSDOM | Closing-option labels create forged choices; quoted values alter attributes/datalist structure | Labels and values remain literal; no forged options or attributes |

The editor reproductions ran Chromium at 1440×1000 and reported no page errors in
either mode. They use synthetic local data. The scheduling fixture and batching
counts support the mechanisms changed here; they do not establish production
Oracle/Redis or network latency. Existing login controls already provide immediate
pending feedback and suppress duplicate submission, so this patch does not claim
to accelerate password hashing or the authentication endpoint.

## Remaining work and integration

- **Flagged for follow-up:** pair the deletion-helper commit with the UI team's
  caller cleanup and its cancellation behavior regression. Do not claim the
  cancellation defect closed using the helper commit alone.
- **Not verified here:** production Oracle/Redis behavior, latency distributions,
  the full combined backend/UI coverage suites, and exhaustive keyboard/screen
  reader behavior. Unit tests check inert/ARIA/focus state; the browser smoke
  validates compact route and session-action reachability.
- **Out of scope:** server, route modules, entity modules, utilities, route CSS,
  live-sync implementation, and tracked E2E modifications. Other review tasks own
  these areas. Existing user changes in the original checkout were untouched.
- The next pass should be the coordinator's combined integration run, including
  the deletion cancellation path, refresh races across all integrated modules,
  full UI lint/tests/coverage, frontend contracts, and smoke. An additional broad
  shell cleanup is not required to integrate these bounded fixes.

Implementation commits, in order:

1. `d57aa34d6556cf3d9be2cf65c38d4c244a026bf4` — storage-safe activity startup.
2. `d7fddc78a66318411bd3ee9c5d558e407724cd18` — reserved bounded telemetry batches.
3. `741c62a5de9bb14c16986dd6fe87664dfe1ac80b` — shell focus, path boundaries, and concurrent capacity load.
4. `e280367f291673e0e6577fc16ecdc814bab3752b` — session/context and editor refresh preservation.
5. `1e53f2277dd9c5e89e69e2a6c2f14c132f2b9fa8` — post-confirmation task refresh marker.
6. `29c4b276480961dbf5b41a189a84cbfdcf27d5a4` — escaped shell option values and labels.

The first two were already imported by the coordinator before the subsequent
commits were created. Commits can be reverted independently except that the deletion
helper and its caller cleanup should be reverted together. No schema migration
or operator action is required.
