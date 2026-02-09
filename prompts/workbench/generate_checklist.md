Month key: {month_key}

You generate a Monthly SOW Governance Attestation for executive review.

Goal:
- Produce an exec-grade Markdown document (renderable, clean headings, tables).
- Also produce a structured JSON record of control attestations for audit/diffing.

Hard constraints:
- Do NOT invent facts.
- Use ONLY the provided inputs (project context, deltas, control set).
- If information is insufficient to attest a control, mark it as "UNKNOWN" and add a question.
- Avoid task-level detail; stay at governance/process level.

Inputs (authoritative):
Project context JSON (source of truth):
{project_context_json}

Change deltas JSON (changes since last period, may be empty):
{deltas_json}

Governance control set JSON (source of truth for what must be attested):
{controls_json}

Definitions:
- attestation values: "TRUE" | "FALSE" | "NA" | "UNKNOWN"
- "NA" only if the control explicitly does not apply in this phase / project type (use control metadata).
- "UNKNOWN" if the control is required/applicable but evidence is missing.

Required outputs:
Return JSON ONLY with the following keys:

{
  "month": "{month_key}",
  "project": {
    "name": "<from context or UNKNOWN>",
    "sow_id": "<from context or UNKNOWN>",
    "owner": "<from context or UNKNOWN>",
    "phase": "<from context or UNKNOWN>"
  },
  "exec_summary": "<short paragraph: overall compliance posture, major changes, key risks>",
  "delta_summary": "<short paragraph: material changes since last period; or 'no material changes'>",
  "controls": [
    {
      "id": "<control id from controls_json>",
      "category": "<control category>",
      "description": "<control description>",
      "required": <true|false>,
      "applicable": <true|false>,
      "attestation": "TRUE|FALSE|NA|UNKNOWN",
      "evidence": [
        "<very short bullet-like fragments pointing to context/deltas fields; no invention>"
      ],
      "notes": "<only if FALSE/UNKNOWN; otherwise empty string>"
    }
  ],
  "exceptions": [
    "<only material exceptions; empty if none>"
  ],
  "risks": [
    "<only material risks; empty if none>"
  ],
  "questions": [
    "<only missing info required to resolve UNKNOWN attestations or required fields>"
  ],
  "warnings": [
    "<inconsistencies: e.g., deltas suggest scope change but no change control evidence>"
  ],
  "markdown": "<A complete executive-ready Markdown document that includes sections and a control attestation table>"
}

Markdown rendering requirements (inside the `markdown` string):
- Use this structure:

# Monthly SOW Governance Attestation
Project / SOW / Month / Phase / Owner block

## Executive Summary
## Phase Status
## Governance Attestation
- Include a table with columns:
  Control ID | Category | Attestation | Notes
- Group controls by Category; keep it readable.
- Put detailed notes only for FALSE/UNKNOWN.
## Risk & Issue Governance
## Change & Delta Review
## Overall Attestation Statement
(signature lines)
## Open Questions
## Warnings & Exceptions

Style:
- Executive-friendly language.
- No long lists of low-level tasks.
- Keep the attestation table compact and scannable.

Validation logic:
- If phase is UNKNOWN, add a warning and include a question requesting the phase.
- If deltas_json is empty or indicates no changes, delta_summary must explicitly say "No material changes were recorded this period."
- If any REQUIRED + applicable control is UNKNOWN, overall posture should reflect incompleteness (not "fully compliant").
