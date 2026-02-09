You are refining a draft structure (solutions + subcomponents).

Hard constraints:
- Apply targeted edits only.
- Do not regenerate everything unless explicitly requested.
- Preserve user-edited/locked fields unless the instruction explicitly says to override.
- Keep outputs grounded in source context and draft text.
- Keep decomposition bounded; avoid exploding the number of subcomponents.
- Output JSON only.

Instruction:
{instruction}

Current draft JSON:
{draft_json}

Target IDs JSON:
{target_ids_json}

Target item snapshots JSON:
{target_items_json}

Allow full regeneration:
{allow_full_regeneration_json}

Locked fields by item JSON:
{locked_fields_json}

Requested decomposition level:
{decomposition_level_json}

Decomposition guidance JSON:
{decomposition_guidance_json}

Return JSON with this shape:
{
  "operations": [
    {
      "op": "update_item_fields|split_solution|merge_solutions|add_subcomponent|discard_item",
      "item_id": "optional-draft-id",
      "target_id": "optional-draft-id",
      "kind": "solution|subcomponent",
      "fields": {"name": "...", "description": "..."},
      "items": [
        {
          "draft_id": "uuid-optional",
          "kind": "solution|subcomponent",
          "name": "...",
          "description": "...",
          "parent_solution_draft_id": "optional"
        }
      ],
      "reason": "short reason"
    }
  ],
  "warnings": ["..."],
  "assumptions": ["..."]
}

Refinement policy:
- Use `subcomponents` as the task-level decomposition unit.
- Keep decomposition adaptive to project complexity; do not use fixed per-solution counts.
- Respect decomposition guidance bounds while applying the instruction.
- If target IDs are provided, anchor edits to those items and keep unrelated items unchanged.
