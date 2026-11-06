export function invalidateMyWorkRecords(state) {
  const work = state.myWork;
  if (!work) return;
  // A response started before the task change must not refill the stale queue.
  work.loadRequestId = (Number(work.loadRequestId) || 0) + 1;
  work.loading = false;
  work.records = null;
}
