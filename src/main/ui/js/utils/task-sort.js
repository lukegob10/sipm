export function nextTaskNameSort(sort = "default") {
  if (sort === "default") return "name-asc";
  if (sort === "name-asc") return "name-desc";
  return "default";
}

export function sortTasksByName(tasks, sort = "default") {
  if (sort !== "name-asc" && sort !== "name-desc") {
    return [...(tasks || [])];
  }
  const direction = sort === "name-desc" ? -1 : 1;
  return [...(tasks || [])].sort((a, b) => (
    String(a?.task_name || "").localeCompare(String(b?.task_name || ""), undefined, {
      sensitivity: "base",
      numeric: true,
    }) * direction
  ));
}
