# Frontend route review — 2026-09-25

Mode: **full-surface review within the assigned frontend route scope**.
Baseline: `82c69be2e71faef18c1a99b5e820aac8e6a78cb4`.
Checkout: `C:/Users/Luke Goblirsch/.codex/worktrees/69ca/sipm`.
Branch: `codex/frontend-route-review`.

The target is responsive, correct route interactions with preserved API paths,
payloads, route IDs, DOM contracts, and authentication strength. This review
improves the assigned surface; it does not establish production readiness or
production login latency. The coordinator owns final combined validation.

## Review coverage and ownership

The repository inventory and stale-script helper were run. The stale-script
heuristic classified many active ES modules and discovered tests as candidates;
runtime imports, route registration, and test discovery refute those candidates.
No stale code was deleted on heuristic evidence alone.

The review read `CONTRIBUTING.md`, the root/runtime READMEs, applicable ancestor
guidance (the ancestor `AGENTS.md` is empty), existing UI/performance review
documents, route contracts, and relevant tests. The clean-code-review safety,
comprehensive, frontend, JavaScript, HTML, Python, testing, performance, rubric,
and end-state references were applied.

Three explicitly requested subagents all used **gpt-6-luna, max reasoning**:

| Reviewer | Assigned surface |
| --- | --- |
| workflows | Tasks/workbench, My Work, task entity, matching styles/tests |
| planning_reporting | Kanban, Calendar, Roadmap, Dashboard, PM Command Center, Program Dashboard, analytics, matching styles/tests |
| administration_entities | Deliverables/master, repositories, spaces/access/admin, team capacity, program/project/solution entities, matching styles/tests |
| Parent | Shared utilities, cross-area coordination, diff review, performance evidence, focused browser/integration checks |

The original checkout's user-modified backend My Work files and adoption-review
document were left untouched. No backend, app shell, global styles, index HTML,
e2e tests, route-module map, external services, or deployment configuration were
edited by this task. Authentication and password hashing were not changed.

## Confirmed findings and closure

All confirmed findings below are **P2 / Medium / should-fix**. The observed
failures were corrected and covered by focused regression checks. There are no
remaining confirmed defects within these changes; that statement does not imply
that every possible interaction has been tested.

| Finding and reproduction | Correction | Closure |
| --- | --- | --- |
| Repeated entity submits issued concurrent writes; a late save could overwrite a newer editor or repopulate collections after a user/space change. | Program, project, solution, and task forms admit one save at a time. Editor revisions and form snapshots preserve newer drafts, attach a returned create ID to the same draft, and avoid rendering a different solution's task list. Shared context guards reject old user/space responses, including same-ID object replacements. Program reset invalidates its pending editor. | Fixed now; held-response regressions cover duplicate writes, draft edits/reset, editor switches, and context changes. |
| Integration review found that a pending delete of A could close or show errors in a newly opened entity B editor; a failed task delete could also clear A's draft. | Program/project/solution deletion captures the editor revision before confirmation and guards later close/notices. A late confirmation for a replaced editor is canceled. Task deletion resets only after the requested task was deleted and the original editor/solution/context remain current; legitimate state/list updates still happen. Stale failures cannot clear the new context's refresh marker. | Fixed in follow-up `967938d`; deferred success/failure, same/different solution, late confirmation, and context rejection regressions. |
| Workbench background renders replaced dirty fields, and a delayed save of A could reselect A after the user had opened and edited B. Delete notices could also land in B after selection changed. | Track the current task's baseline per form, preserve edited fields during same-task refresh, and update untouched fields. Intentional task changes reset the baseline. Saves apply current-context state/list updates without reselecting an older task, and acknowledge only the unchanged original editor. Notice ownership is checked again after rendering, including automatic selection of the next task after deletion. | Fixed in the final workbench follow-up; deferred unit cases and actual Chromium reproduction before/after. |
| Approval cache and pending reads survived context changes; a pending request in space A could block loading space B or replace B's results. | Cache and requests belong to the exact user/space context. B starts immediately; stale A outcomes are ignored. Same-context reads share a request, forced refreshes still queue, and selected rows/counts clear on context change. | Fixed now; cache, pending-response, logout, and same-ID replacement regressions. |
| Analytics retained a previous report after a space/session change. | Request and cache keys include state/user/space object identities and IDs. Restricted/disabled renders clear report data. Old responses cannot replace the current report; explicit all-space and specific-space scopes remain intact. | Fixed now; current-space, explicit-scope, out-of-order, logout, and same-ID replacement regressions. |
| Hostile assignee values inserted extra workbench option markup. | Reuse the existing display escaping helper for option values and labels. | Fixed now; the regression reproduced extra options before the change and verifies literal text/values afterward. Arbitrary script execution was not demonstrated. |
| Canceling task deletion left a refresh-suppression marker set by the caller before confirmation. | Remove the four premature markers in task form, workbench drawer, keyboard, and bulk callers; the shell helper owns the post-confirmation marker. | Fixed with a paired integration dependency, described below. |
| My Work and Repositories search rerenders reset selection while typing in the middle of text. | Capture and restore focus, caret, and selection direction around the rerender. | Fixed now; collapsed/backward selection regressions and actual Chromium typing checks. |
| Kanban phase movement and desktop Calendar day details required a mouse. | Add labelled native phase selectors and date buttons through the existing update/modal handlers. Preserve drag behavior and pending guards; restore keyboard focus only when it has not moved elsewhere. | Fixed now; unit interaction checks and Chromium keyboard checks. |
| Sorting many task names spent excessive time constructing collation behavior for each comparison. | Create one `Intl.Collator` per sort, retaining locale, numeric order, stable case/accent equivalence, defaults, and nonmutation. | Fixed now; output parity and browser CPU measurements below. |

The deletion caller commit **must be paired** with shell helper commit
`1e53f2277dd9c5e89e69e2a6c2f14c132f2b9fa8`. The coordinator confirmed that helper
was integrated in the original checkout. It deliberately is not part of this
route-only worktree.

The review also found `app.js:restoreSelections` reopening/refilling selected
editors after collection refresh, which could overwrite an unsaved draft. This
was handed to the shell owner; the coordinator reported its separate fix and
browser validation. That fix is not claimed as part of these route commits.

Overlapping My Work reorder requests were inspected but left unchanged because
order corruption was not demonstrated. No issue was fabricated from concurrency
alone. No stale files were deleted without evidence.

## Commit ledger

Apply in this order from the baseline; the coordinator already integrated the
first sorting commit. All hashes are stable and no commit was amended afterward.

| Commit | Change |
| --- | --- |
| `3f7e885583505a4938e1ed49e5db770cf500a352` | Reuse task-name collator |
| `c2da151b709bd03d31b007181780228c0694b5f6` | Remove premature delete markers; pair with shell helper above |
| `24a319cf12779b6bbd2dc6a162a57247b7b1c318` | Entity write, draft, and context guards |
| `fc092a85a4a6beaf9f1b4eeda91ea7c5700ee40a` | Workbench assignee option escaping |
| `659738dfaf1d233a1f1e54c4df19603a9f7e2d79` | Search caret and selection preservation |
| `1319c9e8d3581b935657b2de28fa00d47eaaf40d` | Approval queue context ownership |
| `c881a14eb12fc408b2a4963a1aabfa994ed729d9` | Analytics context invalidation |
| `2b9632693c552a70dea25e843f8ddb1a648f750c` | Kanban and Calendar keyboard controls |
| `4784772ac4ffec4401f772f72fcafce6b32e9370` | Initial review report |
| `967938d6f0e3d47aba6eae1323720538d778b4cb` | Preserve newer entity editors after pending deletion |
| `ad2bdf150ff4526692658ae4686b6f8eefa0022e` | Workbench draft preservation and asynchronous action ownership |

## Task sorting performance evidence

Headless Chromium **145.0.7632.6**, Node **v24.14.1**, Windows. Baseline source was
loaded directly from `82c69be`; candidate source was commit `3f7e885`. Each input
contained `size` task objects named `Task ${(index * 7919) % size}`. Two warmups
were followed by ten measured iterations with alternating baseline/candidate
order. Ascending and descending output arrays were verified identical.

| Tasks | Baseline median | Improved median | Baseline p95 | Improved p95 |
| --- | ---: | ---: | ---: | ---: |
| 100 | 3.7 ms | 0.2 ms | 4.0 ms | 0.3 ms |
| 1,000 | 66.0 ms | 3.2 ms | 76.3 ms | 3.4 ms |
| 10,000 | 939.7 ms | 51.2 ms | 1,034.6 ms | 118.6 ms |

These are synthetic browser CPU measurements, excluding network, backend, and
DOM rendering. Other review processes were active on the host. They do not
measure production login performance or a complete user interaction. The
implementation follows the platform guidance to reuse a collator when comparing
many strings ([MDN localeCompare documentation](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/localeCompare)).

The initial Node-only experiment also preserved results and showed a material
improvement, but the browser measurements above are the reported proxy.

The Kanban selector initially renders only its current option and populates the
available phases on focus or pointerdown. For 100 cards and 10 phases, this avoids
900 initial option nodes compared with eagerly rendering every option. This is
a markup-size proxy, not a latency claim. Pointerdown/focus population, selection,
pending state, and keyboard focus restoration were verified.

## Validation record

- Utility baseline: 4 Vitest files / 11 tests passed.
- Sorting and workbench filtering after the sort fix: 2 files / 34 tests passed;
  focused ESLint passed.
- Final parent focused UI union: **14 files / 119 tests passed**. These were
  `entities`, `repositories`, `space-agent-approvals`, `tasks-workbench`,
  `tasks-workbench-entity-races`, `tasks-workbench-delete`,
  `my-work-primary-experience`, `task-sort`, `tasks-workbench-filters`,
  `analytics-context`, `kanban`, `kanban-interactions`, `calendar`, and `gantt`.
  They ran with `npm exec -- vitest run` against the corresponding
  `src/main/ui/test/unit/*.test.js` files.
- Worker-reported scoped Python contract checks passed: workflows **25**,
  administration/entities **34**, and planning/reporting **94**. These are each
  worker's check counts, not a deduplicated suite total. No backend files changed.
- Integration entity-delete follow-up: **2 files / 40 tests passed** on the
  coordinator-updated Vitest **4.1.11**, with scoped ESLint and diff checks. These
  cases were derived from the confirmed code path and tested after the fix;
  they were not run as failing regressions against the earlier commit.
- Final workbench follow-up: **4 files / 50 tests passed** on Vitest **4.1.11**
  (`tasks-workbench`, `tasks-workbench-delete`, `tasks-workbench-entity-races`,
  `tasks-workbench-filters`), with scoped ESLint, route mapping, and staged diff
  checks. The worker reproduced the original draft overwrite, selection,
  stale-context, and delete-notice failures with the new regressions before
  applying the fix. The parent reran these four files and the held-response
  Chromium checks against the final code. These follow-up counts overlap the
  initial focused union and are not additional unique-test totals.
- Full UI lint passed: `npm run lint:ui`.
- Route module/test mapping passed:
  `python scripts/check_route_module_test_mapping.py`.
- `git diff --check` and each staged commit's whitespace check passed. Existing
  mixed line endings were preserved on unchanged lines to limit unrelated churn.
- Existing Playwright checks passed: **7 tests** across
  `navigation-smoke.spec.js` and `responsive-framework.spec.js`, with one worker
  and the local server on port **8774**. Coverage includes delayed route data,
  the compact ten-route matrix, tablet/desktop layouts, and ultrawide dashboards.
- Extended disposable SQLite fixture: populated **My Work, Repositories, Kanban,
  and Calendar at 390, 768, and 1440 px**. All **12** route/viewport checks had no
  document overflow or browser errors. Both search inputs preserved actual
  middle-of-text typing and caret position. Kanban keyboard selection performed
  a successful phase PATCH and restored focus; Calendar Enter opened day details.
  Representative screenshots were visually inspected.
- Harness corrections were limited to test setup: enable developer mode for
  Repositories and seed canonical phases for Kanban. The stock smoke fixture
  disables startup seeding and contains no phase rows. The corrected fixture
  passed; these were not product regressions.
- Workbench follow-up browser evidence: the earlier code **failed** after a held
  save of task A completed while task B's draft was open; the selected task ID
  changed back to A. With the fix, B remains selected, its draft and status are
  preserved, and A's saved value is persisted. A second held save proves that
  newer edits typed into B during its own save remain visible while the submitted
  version is persisted. Both checks passed in Chromium with no page errors.
- The local browser server was stopped after validation. All three workers and
  all parent Node/npm/browser test processes were finished before handing the
  shared tooling back to the coordinator for dependency updates and combined
  gates. Full backend/UI/coverage/browser integration remains the coordinator's
  responsibility, per the task split.

## Remaining limits

Production Oracle/Redis behavior, deployed latency distributions, real-device
interaction timing, and assistive-technology behavior are not verified here.
The local browser fixture is a SQLite proxy, not production evidence. Existing
public contracts and authentication strength are preserved. No schema migration
is required; each logical fix can be reverted independently, except that the
coordinated deletion-marker caller/helper changes must be reverted together.

No push, deployment, production data mutation, or external-service change was
performed. The final closure is: confirmed route findings fixed; shell findings
handed off with an explicit integration dependency; production and assistive
technology behavior not verified; broader backend, shell, and deployment review
outside this task's ownership.
