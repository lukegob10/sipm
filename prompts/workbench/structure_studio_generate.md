You are generating a draft project structure from source documents.

Hard constraints:
- Ground all content in Charter/Plan context.
- Prefer under-generation to speculation.
- Do not invent scope, deliverables, or timelines.
- If information is missing, surface assumptions and warnings explicitly.
- Decompose analytically: infer enabling work needed to deliver outcomes (e.g., dependency chains and supporting capabilities).
- Keep decomposition bounded and meaningful; do not explode into excessive subcomponents.
- Output JSON only.

Project context JSON:
{project_context_json}

Charter source JSON:
{charter_source_json}

Plan source JSON:
{plan_source_json}

Input sufficiency JSON:
{sufficiency_json}

Requested decomposition level:
{decomposition_level_json}

Decomposition guidance JSON:
{decomposition_guidance_json}

Existing solution names (avoid duplicates):
{existing_solution_names_json}

Existing subcomponent names (avoid duplicates):
{existing_subcomponent_names_json}

Return JSON with this shape:
{
  "solutions": [
    {
      "draft_id": "uuid-optional",
      "kind": "solution",
      "name": "...",
      "description": "...",
      "assumptions": ["..."],
      "evidence": [
        {"doc_type": "charter|plan", "revision_id": "...", "line_start": 1, "line_end": 2, "excerpt": "..."}
      ],
      "confidence": "low|medium|high"
    }
  ],
  "subcomponents": [
    {
      "draft_id": "uuid-optional",
      "kind": "subcomponent",
      "name": "...",
      "description": "...",
      "parent_solution_draft_id": "...",
      "parent_solution_name": "optional helper when id unknown",
      "assumptions": ["..."],
      "evidence": [
        {"doc_type": "charter|plan", "revision_id": "...", "line_start": 1, "line_end": 2, "excerpt": "..."}
      ],
      "confidence": "low|medium|high"
    }
  ],
  "assumptions": ["..."],
  "warnings": ["..."],
  "minimal_draft": false
}

Decomposition policy:
- Use the requested decomposition level.
- Keep structure adaptive to complexity and outline depth (not a fixed number per solution).
- Stay within decomposition guidance bounds.
- Use `subcomponents` as the task-level unit (do not introduce another task entity name).
