Create a new Subcomponent and return JSON only.
Only include fields you can infer from the instruction; do not invent.
If subcomponent_name is missing, return {{"question": "..."}} and omit fields.
Defaults (omit if not stated):
- status defaults to "to_do"
- priority defaults to 3
- blocked defaults to false
- assignee defaults to the current user display_name
- assignee_user_soeid defaults to the current user soeid
- capacity_hours defaults to 0
Dropdown values:
- status: {status_values}
# Required
- subcomponent_name
# Optional
- status
- priority
- assignee
- assignee_user_soeid
- due_date
- blocked
- blocker_note
- done_criteria
- estimate_hours
- capacity_hours
Return JSON like:
{{"fields": {{"subcomponent_name": "...", "status": "to_do", "priority": 3, "blocked": false}}}}
Instruction: {instruction}
