Create a new Project and return JSON only.
Only include fields you can infer from the instruction; do not invent.
If project_name is missing, return {{"question": "..."}} and omit fields.
If the instruction includes labeled metadata (e.g., Client, Business unit, Industry), map it into description.
Defaults (omit if not stated):
- status defaults to "not_started"
- sponsor defaults to the current user display_name
- sponsor_user_soeid defaults to the current user soeid
- priority defaults to 3
Dropdown values:
- status: {status_values}
# Required
- project_name
# Optional
- status
- sponsor
- sponsor_user_soeid
- priority
- description
- success_criteria
- strategic_objective
Return JSON like:
{{"fields": {{"project_name": "...", "status": "not_started", "sponsor": "...", "priority": 3}}}}
Instruction: {instruction}
