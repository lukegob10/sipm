Create a new Solution and return JSON only.
Only include fields you can infer from the instruction; do not invent.
If solution_name is missing, return {{"question": "..."}} and omit fields.
Defaults (omit if not stated):
- version defaults to "0.1.0"
- status defaults to "not_started"
- rag_status defaults to "green"
- priority defaults to 3
- capacity_hours defaults to 0
Dropdown values:
- status: {status_values}
- rag_status: {rag_status_values}
- impact_confidence: {impact_confidence_values}
# Required
- solution_name
# Optional
- version
- status
- owner
- assignee
- priority
- capacity_hours
- due_date
- current_phase
- impact_confidence
- rag_status
- rag_reason
- description
- success_criteria
- risks
- blockers
Return JSON like:
{{"fields": {{"solution_name": "...", "version": "0.1.0", "status": "not_started", "owner": "...", "priority": 3}}}}
Instruction: {instruction}
