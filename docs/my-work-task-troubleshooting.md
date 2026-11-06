# Tasks that remain in My Work

My Work reads assigned tasks from the SIPM server opened in the browser. A different deployment can use a different database. Deleting local data does not change that deployment.

## Checks on the affected deployment

1. In Preferences, turn off **Show completed work**. Completed and abandoned tasks are otherwise intentionally visible in My Work. This preference is stored per user and space in that browser; set it on each computer you use.
2. Hard reload the page (`Ctrl+Shift+R`). If a deleted or reassigned task disappears, the browser was showing a cached My Work result.
3. For an open task still assigned to you, use Tasks to clear or change its assignee when appropriate. Delete the shared task on this deployment if it should be removed for everyone and you have permission. Confirm the action succeeds; a failed request has not removed the task.

Deleting a task's private My Work state only resets its bucket, ordering, reminders, and notes. It does not delete the shared task or hide an assignment.

## Code repair to deploy

The UI now invalidates My Work after successful task deletions, editor saves, batch changes, authoritative task reloads, and forced My Work reloads such as reconnect refreshes. Invalidation also retires older My Work requests so a delayed response cannot restore stale entries. Failed deletions leave the queue unchanged.

The current backend query also excludes deleted tasks and tasks under deleted or mismatched project/solution parents. Deploy the backend and UI from the same release to the affected environment. A local code change does not update another deployment automatically.

The separate task-save repair requires existing Oracle deployments to apply [the task assignee migration](sql/20260930_task_assignee_nullable_v1.sql). That migration addresses save errors; it does not remove tasks.

## If a task still returns after reloading

An operator with access to that environment should inspect the browser Network responses for `/project-manager/api/my-work` and the task mutation. Record the task ID, selected space ID, HTTP status, and `X-Request-ID`; correlate them with the server logs.

- If My Work returns the task with an open status and your assignee SOEID, the deployed database still considers it assigned work. Remove or change the assignment there.
- If the task is complete or abandoned, check the Show completed work preference in the affected browser.
- If a delete succeeds but a subsequent fresh My Work response still includes the task, inspect the deployed release, the task and parent deletion flags, and which database each server instance uses. Check that reads and writes reach the intended environment and that cross-instance refresh coordination is configured.
- If the API response excludes the task but the page still shows it, the UI is stale. Verify that the browser received the repaired UI release.

## Recommended personal hide feature

For assigned tasks you want off your own queue while preserving shared work, add **Hide from My Work** and **Restore**. Save the hidden flag in private state keyed by user, space, and task on the deployed server. Keep the task's assignment, status, notes, reminder, and previous planning bucket intact. Exclude hidden tasks from the normal queue and provide a Hidden tasks view for restoring them.

This would persist across browsers and computers using that deployment. It would remain private to the owning user and would not hide work in other deployments. This feature is a proposed follow-up; the cache repair does not add it.
