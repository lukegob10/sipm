export function sortTasksByName(tasks, sort = "name-asc") {
  const direction = sort === "name-desc" ? -1 : 1;
  return [...(tasks || [])].sort((a, b) => (
    String(a?.task_name || "").localeCompare(String(b?.task_name || ""), undefined, {
      sensitivity: "base",
      numeric: true,
    }) * direction
  ));
}
