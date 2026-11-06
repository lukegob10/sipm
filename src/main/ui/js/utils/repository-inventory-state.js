export function invalidateRepositoryInventory(state) {
  const inventory = state.repositoryInventory;
  if (!inventory) return false;
  const hadData = inventory.records !== null || inventory.loading || !!inventory.error;
  if (!hadData) return false;
  inventory.loadRequestId = (Number(inventory.loadRequestId) || 0) + 1;
  inventory.records = null;
  inventory.loading = false;
  inventory.error = "";
  return true;
}
