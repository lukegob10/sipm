export function nextTaskNameSort(sort = "default") {
  if (sort === "default") return "name-asc";
  if (sort === "name-asc") return "name-desc";
  return "default";
}

export function taskNameSortPresentation(sort = "default") {
  const presentations = {
    "name-asc": { ariaSort: "ascending", indicator: "A–Z", nextLabel: "Sort tasks Z to A" },
    "name-desc": { ariaSort: "descending", indicator: "Z–A", nextLabel: "Restore normal task order" },
    default: { ariaSort: "none", indicator: "↕", nextLabel: "Sort tasks A to Z" },
  };
  return presentations[sort] || presentations.default;
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
