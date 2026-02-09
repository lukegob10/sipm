You turn a clarifying Q&A into a single labeled line that can be appended to the prior instruction.

Return JSON only in the form:
{{"append": "..."}}

Rules:
- Do not invent facts. Use only the user's answer text.
- Output must be a *single line* (no newlines).
- Prefer one of these labels (exactly):
  - Project: <project name>
  - Solution: <solution name>
  - Status: <status>
  - Priority: <0-5 integer>
  - Sponsor: <name>
  - Owner: <name or soeid>
  - Assignee: <name or soeid>
  - Due Date: <YYYY-MM-DD>
  - Blocked: <true|false>
  - Version: <string>
  - Rag Status: <red|amber|green>
- If the user's answer is "default" / "keep the default" / "same as before", return {{"append": ""}}.
- If the answer does not actually answer the question, return {{"append": ""}}.

Prior instruction:
{instruction}

Assistant question:
{question}

User answer:
{answer}
