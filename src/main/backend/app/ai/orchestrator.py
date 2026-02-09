from __future__ import annotations

import json
import os
import concurrent.futures
import re
import time
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Any, Dict, List, Optional, TypedDict

try:
    from langchain_core.messages import AIMessage, BaseMessage, ChatMessage, HumanMessage, SystemMessage, ToolMessage
except ModuleNotFoundError:  # pragma: no cover - test fallback when langchain_core isn't installed
    class BaseMessage:  # minimal shim for tests
        type = "base"

        def __init__(self, content: str = "", **kwargs) -> None:
            self.content = content
            self.additional_kwargs = kwargs.get("additional_kwargs", {})
            self.response_metadata = kwargs.get("response_metadata", {})

    class HumanMessage(BaseMessage):
        type = "human"

    class AIMessage(BaseMessage):
        type = "ai"

    class SystemMessage(BaseMessage):
        type = "system"

    class ToolMessage(BaseMessage):
        type = "tool"

        def __init__(self, content: str = "", tool_call_id: str = "", **kwargs) -> None:
            super().__init__(content=content, **kwargs)
            self.tool_call_id = tool_call_id

    class ChatMessage(BaseMessage):
        type = "chat"

        def __init__(self, role: str = "user", content: str = "", **kwargs) -> None:
            super().__init__(content=content, **kwargs)
            self.role = role
try:
    from langgraph.graph import END, StateGraph
    from langgraph.graph.message import add_messages
except ModuleNotFoundError:  # pragma: no cover - test fallback when langgraph isn't installed
    END = "__END__"

    def add_messages(value: Any) -> Any:
        return value

    class _DummyExecutor:
        def __init__(self, nodes: Dict[str, Any], entry: Optional[str], cond_edges: Dict[str, Any]) -> None:
            self._nodes = nodes
            self._entry = entry
            self._cond_edges = cond_edges

        def invoke(self, state: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            limit = 10
            if isinstance(config, dict):
                limit = int(config.get("recursion_limit") or limit)
            current = self._entry
            steps = 0
            while current and steps < limit:
                steps += 1
                node = self._nodes.get(current)
                if not node:
                    break
                updates = node(state)
                if isinstance(updates, dict):
                    state.update(updates)
                if current in self._cond_edges:
                    router, mapping = self._cond_edges[current]
                    next_key = router(state)
                    current = mapping.get(next_key)
                    if current == END:
                        break
                else:
                    break
            return state

    class StateGraph:
        def __init__(self, _state_type: Any) -> None:
            self._nodes: Dict[str, Any] = {}
            self._entry: Optional[str] = None
            self._cond_edges: Dict[str, Any] = {}

        def add_node(self, name: str, fn: Any) -> None:
            self._nodes[name] = fn

        def add_edge(self, _src: str, _dest: str) -> None:
            return None

        def add_conditional_edges(self, src: str, router: Any, mapping: Dict[str, Any]) -> None:
            self._cond_edges[src] = (router, mapping)

        def set_entry_point(self, name: str) -> None:
            self._entry = name

        def compile(self) -> _DummyExecutor:
            return _DummyExecutor(self._nodes, self._entry, self._cond_edges)

from .llm import call_chat_completion, GenAIConfigError
from .contracts import contract_hints
from .prompt_loader import render_prompt
from .orchestrator_context import (
    compact_for_prompt as _compact_for_prompt,
    compact_history as _compact_history,
    context_packet as _context_packet,
    fallback_empty_response as _fallback_empty_response,
    latest_assistant_message as _latest_assistant_message,
    latest_user_message as _latest_user_message,
    message_content as _message_content,
    message_role as _message_role,
)
from .orchestrator_parsing import normalize_action as _normalize_action
from .orchestrator_parsing import parse_json as _parse_json
from .tools import (
    read_context,
    read_context_complete,
    read_project_detail,
    read_solution_detail,
    read_subcomponent_detail,
    read_artifacts_detail,
    read_sow_document,
    list_projects,
    list_solutions_for_project,
    read_external_doc,
    explain_app_usage,
    get_tool_catalog,
    log_tool_call,
    log_query_metric,
    search_entities,
    read_entity_index,
    read_entity_deltas,
    list_project_cards,
    list_solution_cards,
    list_task_cards,
    get_project_card,
    get_solution_card,
    get_task_card,
    get_scope_digest,
    get_entity_fields,
    get_entity_deltas,
    validate_draft,
    apply_draft,
    verify_write,
)
from ..routes.genai import _user_prompt, _system_prompt, _project_prompt, _solution_prompt, _subcomponent_prompt

logger = logging.getLogger(__name__)

class AgentState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], add_messages]
    context: Dict[str, Any]
    current_date: Optional[str]
    current_user: Optional[Dict[str, Any]]
    entity_type: Optional[str]
    entity_id: Optional[str]
    project_id: Optional[str]
    space_id: Optional[str]
    response: Optional[str]
    request_type: Optional[str]
    output: Optional[str]
    requires_approval: bool
    # True when the agent asked the user for required/clarifying info and is waiting for an answer.
    awaiting_user: bool
    pending_tool: Optional[Dict[str, Any]]
    queued_tool: Optional[Dict[str, Any]]
    halt: bool
    last_error: Optional[str]
    last_tool_signature: Optional[str]
    last_tool_repeats: int
    tool_calls: int
    context_calls: int
    tool_history: List[str]
    max_steps: int
    trace_enabled: bool
    trace: List[Dict[str, Any]]
    steps: int
    last_validation: Optional[Dict[str, Any]]
    deadline_s: Optional[float]
    metric_bytes_sent: int
    metric_tokens_sent: int
    metric_bytes_returned: int
    metric_tokens_returned: int
    metric_cache_hits: int
    metric_drilldowns: int


REPAIR_SYSTEM_PROMPT = (
    "You are a strict JSON fixer. Return valid JSON only, no markdown or commentary.\n"
    "The JSON must match this schema:\n"
    "{\"action\": \"tool|final|ask\", \"tool\": \"name\", \"args\": {..}, \"reply\": \"...\", "
    "\"request_type\": \"...\", \"output\": \"...\", \"requires_approval\": true|false}\n"
)


def _agent_system_prompt() -> str:
    tools = get_tool_catalog()
    # Include arg hints so the LLM can call tools correctly without relying on guesswork.
    compact_lines = []
    for t in tools:
        name = t.get("name")
        desc = t.get("description")
        args = t.get("args") or []
        if isinstance(args, list) and args:
            compact_lines.append(f"- {name}({', '.join(args)}): {desc}")
        else:
            compact_lines.append(f"- {name}: {desc}")
    compact = "\n".join(compact_lines)
    return render_prompt("agent/system.md", tool_list=compact)


def _message_from_role(role: Optional[str], content: str) -> BaseMessage:
    normalized = (role or "").strip().lower()
    if normalized in {"user", "human"}:
        return HumanMessage(content=content)
    if normalized in {"assistant", "ai"}:
        return AIMessage(content=content)
    if normalized == "system":
        return SystemMessage(content=content)
    if normalized == "tool":
        return ToolMessage(content=content, tool_call_id="tool")
    return ChatMessage(role=normalized or "user", content=content)


def _append_message(messages: List[BaseMessage], role: str, content: str) -> List[BaseMessage]:
    del messages
    return [_message_from_role(role, content)]


def _repair_json(raw: str, trace: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
    if not raw:
        return None
    try:
        return _safe_call(
            REPAIR_SYSTEM_PROMPT,
            f"Fix this JSON:\n{raw}",
            trace=trace,
            trace_label="repair_json",
        )
    except Exception:
        return None


_CONTEXT_TOOLS = {
    "read_context",
    "explain_app_usage",
    "get_scope_digest",
    "list_projects",
    "list_solutions_for_project",
    "list_project_cards",
    "list_solution_cards",
    "list_task_cards",
    "get_project_card",
    "get_solution_card",
    "get_task_card",
    "get_entity_fields",
    "search_entities",
    "read_entity_index",
    "read_entity_deltas",
    "get_entity_deltas",
}

_WRITE_TOOLS_BLOCKED_IN_CHAT = {"apply_draft", "verify_write"}

_DIRECT_PROJECT_PATTERNS = (
    "create project",
    "create a project",
    "new project",
    "add project",
    "start project",
    "start a project",
    "set up project",
    "setup project",
    "launch project",
    "project name",
    "project named",
    "project called",
)

_DIRECT_SOLUTION_PATTERNS = (
    "create solution",
    "create a solution",
    "new solution",
    "add solution",
    "start solution",
    "start a solution",
    "set up solution",
    "setup solution",
    "launch solution",
    "solution name",
    "solution named",
    "solution called",
)

_DIRECT_SUBCOMPONENT_PATTERNS = (
    "create subcomponent",
    "create a subcomponent",
    "new subcomponent",
    "add subcomponent",
    "subcomponent name",
    "subcomponent named",
    "subcomponent called",
    "create task",
    "create a task",
    "new task",
    "add task",
    "task named",
    "task called",
)

_DIRECT_CREATE_EXCLUDES = (
    "charter",
    "plan",
    "decision log",
    "decision_log",
    "checklist",
    "sow",
    "statement of work",
)


def _infer_direct_draft_tool(message: str) -> Optional[str]:
    text = (message or "").lower()
    if not text:
        return None
    if any(pattern in text for pattern in _DIRECT_CREATE_EXCLUDES):
        return None
    if any(pattern in text for pattern in _DIRECT_SOLUTION_PATTERNS):
        return "draft_create_solution"
    if any(pattern in text for pattern in _DIRECT_SUBCOMPONENT_PATTERNS):
        return "draft_create_subcomponent"
    if any(pattern in text for pattern in _DIRECT_PROJECT_PATTERNS):
        return "draft_create_project"
    return None


def _has_fields_section(text: str) -> bool:
    if not text:
        return False
    if "# fields" in text.lower():
        return True
    payload = _parse_json(text)
    return isinstance(payload, dict) and isinstance(payload.get("fields"), dict) and bool(payload.get("fields"))


def _parse_fields_block(text: str) -> Dict[str, str]:
    if not text:
        return {}
    payload = _parse_json(text)
    if isinstance(payload, dict):
        fields = payload.get("fields")
        if isinstance(fields, dict):
            return fields
    fields: Dict[str, str] = {}
    in_fields = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("# fields"):
            in_fields = True
            continue
        if stripped.startswith("# "):
            in_fields = False
        if not in_fields or not stripped:
            continue
        entry = stripped.lstrip("- ").strip()
        if ":" not in entry:
            continue
        key, value = entry.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')
    return fields


def _normalize_spaces(text: str) -> str:
    return " ".join(str(text).split())


def _normalize_description(text: str) -> str:
    cleaned = _normalize_spaces(text)
    if not cleaned:
        return cleaned
    parts = [p.strip().rstrip(".") for p in cleaned.split(";") if p.strip()]
    if parts:
        cleaned = ". ".join(parts)
    if not cleaned.endswith("."):
        cleaned = f"{cleaned}."
    return cleaned


def _normalize_project_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    if not fields:
        return fields
    normalized = dict(fields)
    if isinstance(normalized.get("project_name"), str):
        normalized["project_name"] = _normalize_spaces(normalized["project_name"])
    if isinstance(normalized.get("description"), str):
        normalized["description"] = _normalize_description(normalized["description"])
    if isinstance(normalized.get("sponsor"), str):
        normalized["sponsor"] = _normalize_spaces(normalized["sponsor"])
    return normalized


def _render_fields_block(kind: str, fields: Dict[str, Any]) -> str:
    if not fields:
        return ""
    if kind == "project":
        order = [
            "project_name",
            "status",
            "sponsor",
            "priority",
            "description",
            "success_criteria",
            "strategic_objective",
        ]
    else:
        order = [
            "solution_name",
            "version",
            "status",
            "owner",
            "assignee",
            "priority",
            "capacity_hours",
            "due_date",
            "current_phase",
            "impact_confidence",
            "rag_status",
            "description",
            "success_criteria",
            "risks",
            "blockers",
        ]
    lines = ["# Fields"]
    used = set()
    for key in order:
        if key not in fields:
            continue
        value = fields.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        used.add(key)
        lines.append(f"- {key}: {json.dumps(value, ensure_ascii=True)}")
    for key in sorted(k for k in fields.keys() if k not in used):
        value = fields.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        lines.append(f"- {key}: {json.dumps(value, ensure_ascii=True)}")
    return "\n".join(lines) + "\n"


def _render_fields_payload(fields: Dict[str, Any]) -> str:
    return json.dumps({"fields": fields}, ensure_ascii=True)


def _extract_question_from_output(text: str) -> Optional[str]:
    if not text:
        return None
    payload = _parse_json(text)
    if isinstance(payload, dict):
        question = payload.get("question")
        if isinstance(question, str) and question.strip():
            return question.strip()
        questions = payload.get("questions")
        if isinstance(questions, list):
            joined = " ".join(str(q).strip() for q in questions if str(q).strip())
            if joined:
                return joined
    stripped = text.strip()
    if stripped.lower().startswith("question:"):
        return stripped.split(":", 1)[1].strip()
    return None


def _handle_question_output(
    output_text: str,
    updates: AgentState,
    trace: List[Dict[str, Any]],
    trace_enabled: bool,
) -> bool:
    question = _extract_question_from_output(output_text)
    if not question:
        return False
    updates["response"] = question
    updates["requires_approval"] = False
    updates["request_type"] = None
    updates["output"] = None
    updates["halt"] = True
    updates["awaiting_user"] = True
    if trace_enabled:
        trace.append(
            {
                "type": "ask",
                "question": question,
                "time": datetime.now(timezone.utc).isoformat(),
            }
        )
        updates["trace"] = trace
    return True

def _trim_candidate(text: str) -> str:
    if not text:
        return ""
    cleaned = text.strip().lstrip(":").strip()
    if not cleaned:
        return ""
    if cleaned[0] in {"'", '"'}:
        quote = cleaned[0]
        end = cleaned.find(quote, 1)
        if end > 1:
            return cleaned[1:end].strip()
    lower = cleaned.lower()
    stop_tokens = [
        " let's ",
        " lets ",
        " make it",
        " set it",
        " assign",
        " with ",
        " for ",
        " then ",
        " and ",
        ":",
        "\n",
        ".",
        ",",
        ";",
    ]
    stop_at = None
    for token in stop_tokens:
        idx = lower.find(token)
        if idx != -1:
            stop_at = idx if stop_at is None else min(stop_at, idx)
    if stop_at is not None:
        cleaned = cleaned[:stop_at]
    cleaned = cleaned.strip().strip("\"'").strip()
    if cleaned.lower().startswith("name "):
        cleaned = cleaned[5:].strip()
    return cleaned


def _extract_labeled_value(text: str, labels: List[str]) -> Optional[str]:
    if not text:
        return None
    lower = text.lower()
    for label in labels:
        start = 0
        while True:
            idx = lower.find(label, start)
            if idx == -1:
                break
            end = idx + len(label)
            if end < len(lower) and lower[end].isalnum():
                start = idx + 1
                continue
            after = text[end:].strip()
            candidate = _trim_candidate(after)
            if candidate:
                return candidate
            start = idx + 1
    return None


def _extract_about_phrase(text: str) -> Optional[str]:
    if not text:
        return None
    lower = text.lower()
    for token in [" about ", " regarding ", " focused on ", " focus on ", " pertaining to "]:
        idx = lower.find(token)
        if idx == -1:
            continue
        after = text[idx + len(token) :].strip()
        candidate = _trim_candidate(after)
        if candidate:
            return candidate
    m = re.search(r"\babout\b", lower)
    if m:
        after = text[m.end() :].strip()
        candidate = _trim_candidate(after)
        if candidate:
            return candidate
    return None


def _extract_labeled_value_with_stops(
    text: str,
    labels: List[str],
    stop_labels: Optional[List[str]] = None,
) -> Optional[str]:
    if not text:
        return None
    lower = text.lower()
    for label in labels:
        start = 0
        while True:
            idx = lower.find(label, start)
            if idx == -1:
                break
            end = idx + len(label)
            if end < len(lower) and lower[end].isalnum():
                start = idx + 1
                continue
            after = text[end:].strip()
            if stop_labels:
                lower_after = after.lower()
                stop_at = None
                for stop in stop_labels:
                    stop_idx = lower_after.find(stop)
                    if stop_idx != -1:
                        stop_at = stop_idx if stop_at is None else min(stop_at, stop_idx)
                if stop_at is not None:
                    after = after[:stop_at].strip()
            candidate = _trim_candidate(after)
            if candidate:
                return candidate
            start = idx + 1
    return None


def _extract_project_metadata(instruction: str) -> Optional[str]:
    text = (instruction or "").strip()
    if not text:
        return None
    stops = [
        "project name",
        "name:",
        "client:",
        "business unit:",
        "industry:",
        "description:",
        "sponsor:",
        "status:",
        "priority:",
    ]
    description = _extract_labeled_value_with_stops(
        text,
        ["description:", "description -", "description is"],
        stop_labels=stops,
    )
    if not description:
        description = _extract_about_phrase(text)
    client = _extract_labeled_value_with_stops(
        text,
        ["client:", "client -", "client is"],
        stop_labels=stops,
    )
    business_unit = _extract_labeled_value_with_stops(
        text,
        ["business unit:", "business unit -", "business unit is"],
        stop_labels=stops,
    )
    industry = _extract_labeled_value_with_stops(
        text,
        ["industry:", "industry -", "industry is"],
        stop_labels=stops,
    )
    parts = []
    if description:
        parts.append(description)
    if client:
        parts.append(f"Client: {client}")
    if business_unit:
        parts.append(f"Business unit: {business_unit}")
    if industry:
        parts.append(f"Industry: {industry}")
    if not parts:
        return None
    return "; ".join(parts)


def _extract_name_from_instruction(kind: str, instruction: str) -> Optional[str]:
    text = (instruction or "").strip()
    if not text:
        return None
    lower = text.lower()
    explicit_labels = []
    if kind == "project":
        explicit_labels = [
            "project named",
            "project called",
            "project name",
            "project name:",
        ]
    elif kind == "solution":
        explicit_labels = [
            "solution named",
            "solution called",
            "solution name",
        ]
    else:
        explicit_labels = [
            "subcomponent named",
            "subcomponent called",
            "subcomponent name",
            "task named",
            "task called",
            "task name",
        ]
    explicit = None
    if kind == "project":
        explicit = _extract_labeled_value_with_stops(
            text,
            explicit_labels,
            stop_labels=[
                " client:",
                " business unit:",
                " industry:",
                " description:",
                " the project is about",
                " project is about",
                " sponsor:",
                " status:",
                " priority:",
            ],
        )
    else:
        explicit = _extract_labeled_value(text, explicit_labels)
    if explicit:
        return explicit
    generic = _extract_labeled_value(
        text,
        [
            "name:",
            "name is",
            "name -",
            "named",
            "called",
            "let's call it",
            "lets call it",
        ],
    )
    if generic:
        return generic
    if kind != "project":
        about = _extract_about_phrase(text)
        if about:
            return about
    if kind == "project":
        needles = [
            "create a project",
            "create project",
            "new project",
            "add project",
        ]
    elif kind == "solution":
        needles = [
            "create a solution",
            "create solution",
            "new solution",
            "add solution",
        ]
    else:
        needles = [
            "create a subcomponent",
            "create subcomponent",
            "new subcomponent",
            "add subcomponent",
            "create a task",
            "create task",
            "new task",
            "add task",
        ]
    for needle in needles:
        idx = lower.find(needle)
        if idx == -1:
            continue
        after = text[idx + len(needle) :].strip()
        candidate = _trim_candidate(after)
        if candidate and not candidate.lower().startswith(
            ("for ", "in ", "within ", "under ", "on ")
        ):
            lowered = candidate.lower()
            if lowered.startswith(("that ", "this ", "a ", "an ")) and "deliverable" in lowered:
                continue
            return candidate
    return None


def _extract_status_from_instruction(kind: str, instruction: str) -> Optional[str]:
    text = (instruction or "").lower()
    if not text:
        return None
    if kind == "subcomponent":
        status_map = {
            "to do": "to_do",
            "todo": "to_do",
            "to_do": "to_do",
            "in progress": "in_progress",
            "in_progress": "in_progress",
            "on hold": "on_hold",
            "on_hold": "on_hold",
            "complete": "complete",
            "completed": "complete",
            "abandoned": "abandoned",
        }
    else:
        status_map = {
            "not started": "not_started",
            "not_started": "not_started",
            "active": "active",
            "on hold": "on_hold",
            "on_hold": "on_hold",
            "complete": "complete",
            "completed": "complete",
            "abandoned": "abandoned",
        }
    for phrase, value in status_map.items():
        if re.search(rf"\\b{re.escape(phrase)}\\b", text):
            return value
    return None


def _extract_assignee_from_instruction(instruction: str) -> Optional[str]:
    text = (instruction or "").strip()
    if not text:
        return None
    lower = text.lower()
    patterns = [
        "assign it to",
        "assign to",
        "assigned to",
        "sponsor is",
        "owner is",
        "owned by",
        "owner:",
        "owner -",
        "i am the owner",
        "i'm the owner",
    ]
    for pattern in patterns:
        idx = lower.find(pattern)
        if idx == -1:
            continue
        after = text[idx + len(pattern) :].strip()
        candidate = _trim_candidate(after)
        if candidate:
            return candidate
    # Handle "owner <name>" without punctuation or "is".
    owner_match = re.search(r"\bowner\s+(?!is\b)([A-Za-z0-9].+)", text, re.IGNORECASE)
    if owner_match:
        candidate = _trim_candidate(owner_match.group(1))
        if candidate:
            return candidate
    assignee_match = re.search(r"\bassignee\s+(?!is\b)([A-Za-z0-9].+)", text, re.IGNORECASE)
    if assignee_match:
        candidate = _trim_candidate(assignee_match.group(1))
        if candidate:
            return candidate
    return None


_WEEKDAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _parse_date_literal(text: str) -> Optional[date]:
    if not text:
        return None
    cleaned = text.strip().strip('"').strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _next_weekday(start: date, weekday: int) -> date:
    days_ahead = (weekday - start.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    return start + timedelta(days=days_ahead)


def _extract_due_date_from_instruction(instruction: str, current_date: Optional[str]) -> Optional[str]:
    if not instruction:
        return None
    for pattern in (
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",
        r"\b\d{1,2}-\d{1,2}-\d{4}\b",
    ):
        match = re.search(pattern, instruction)
        if match:
            parsed = _parse_date_literal(match.group(0))
            if parsed:
                return parsed.isoformat()
    if not current_date:
        return None
    try:
        base = datetime.fromisoformat(current_date).date()
    except ValueError:
        return None
    lower = instruction.lower()
    if "tomorrow" in lower:
        return (base + timedelta(days=1)).isoformat()
    if "today" in lower:
        return base.isoformat()
    if "next week" in lower:
        return (base + timedelta(days=7)).isoformat()
    for name, weekday in _WEEKDAY_MAP.items():
        if f"next {name}" in lower:
            return _next_weekday(base, weekday).isoformat()
        if f"this {name}" in lower:
            days_ahead = (weekday - base.weekday() + 7) % 7
            return (base + timedelta(days=days_ahead)).isoformat()
    return None


def _normalize_date_fields(fields: Dict[str, Any], current_date: Optional[str]) -> Dict[str, Any]:
    if not fields:
        return fields
    updated = dict(fields)
    for key in ("due_date", "planned_start_date"):
        value = updated.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        parsed = _parse_date_literal(value)
        if not parsed:
            parsed = None
            if current_date:
                parsed_str = _extract_due_date_from_instruction(value, current_date)
                if parsed_str:
                    updated[key] = parsed_str
                    continue
        if parsed:
            updated[key] = parsed.isoformat()
    return updated


def _normalize_field_name(field: str) -> str:
    if not field:
        return ""
    cleaned = str(field).strip().lower()
    cleaned = re.sub(r"[\s\-]+", "_", cleaned)
    cleaned = re.sub(r"[^a-z0-9_]", "", cleaned)
    cleaned = cleaned.strip("_")
    alias = {
        "duedate": "due_date",
        "due": "due_date",
        "duedate": "due_date",
        "ragstatus": "rag_status",
        "ragreason": "rag_reason",
        "currentphase": "current_phase",
        "plannedstartdate": "planned_start_date",
        "assigneesoeid": "assignee_user_soeid",
        "ownersoeid": "owner_user_soeid",
        "sponsorsoeid": "sponsor_user_soeid",
    }
    return alias.get(cleaned, cleaned)


def _coerce_scalar_value(value: str) -> Any:
    """Coerce obvious booleans/ints; keep everything else as a string."""
    raw = (value or "").strip()
    if not raw:
        return raw
    lower = raw.lower()
    if lower in {"true", "yes", "1"}:
        return True
    if lower in {"false", "no", "0"}:
        return False
    # Avoid converting version-like strings (0.1.0) into numbers.
    if re.fullmatch(r"-?\d+", raw):
        try:
            return int(raw)
        except Exception:
            return raw
    return raw


def _parse_simple_update_fields(
    entity_type: str,
    instruction: str,
    contracts: Optional[Dict[str, Any]] = None,
    current_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse simple 'set <field> to <value>' instructions into a fields dict.

    This is intentionally conservative: if we can't confidently map to a known field, return {} and let the LLM handle it.
    """
    raw = (instruction or "").strip()
    # Keep this conservative: only attempt to parse a single-line "set X to Y" style instruction.
    # If the instruction contains multiple lines, use the first non-empty line.
    text = ""
    for line in raw.splitlines():
        if line.strip():
            text = line.strip()
            break
    if not text:
        return {}

    allowed_fields: set[str] = set()
    if isinstance(contracts, dict):
        ent = contracts.get(entity_type) if entity_type else None
        if isinstance(ent, dict):
            allowed = ent.get("fields")
            if isinstance(allowed, dict):
                allowed_fields = {str(k) for k in allowed.keys() if k}

    patterns = [
        r"^(?:set|update|change)\s+(?:the\s+)?(?P<field>[a-zA-Z_][a-zA-Z0-9_\s\-]*)\s+(?:to|=)\s+(?P<value>.+?)\s*$",
        r"^(?P<field>[a-zA-Z_][a-zA-Z0-9_\s\-]*)\s+(?:to|=)\s+(?P<value>.+?)\s*$",
    ]
    match = None
    for pat in patterns:
        match = re.search(pat, text, flags=re.IGNORECASE)
        if match:
            break
    if not match:
        return {}

    field_raw = (match.group("field") or "").strip()
    value_raw = (match.group("value") or "").strip()
    if not field_raw or not value_raw:
        return {}

    field = _normalize_field_name(field_raw)
    if allowed_fields and field not in allowed_fields:
        return {}

    # Trim quotes and trailing punctuation (common from LLM-generated instructions).
    value = value_raw.strip().strip('"').strip("'").strip()
    value = value.rstrip(".").strip()

    fields: Dict[str, Any] = {field: _coerce_scalar_value(value)}
    # Normalize dates (supports "next Friday" etc).
    fields = _normalize_date_fields(fields, current_date)
    return fields


def _coerce_create_output(kind: str, instruction: str, current_date: Optional[str] = None) -> Optional[str]:
    name = _extract_name_from_instruction(kind, instruction)
    if not name:
        return None
    status = _extract_status_from_instruction(kind, instruction)
    sponsor = _extract_assignee_from_instruction(instruction) if kind == "project" else None
    field_key = "subcomponent_name" if kind == "subcomponent" else f"{kind}_name"
    fields: Dict[str, Any] = {field_key: name}
    if status:
        fields["status"] = status
    if sponsor:
        fields["sponsor"] = sponsor
    if kind == "solution":
        due_date = _extract_due_date_from_instruction(instruction, current_date)
        if due_date:
            fields["due_date"] = due_date
    if kind == "subcomponent":
        due_date = _extract_due_date_from_instruction(instruction, current_date)
        if due_date:
            fields["due_date"] = due_date
    return json.dumps({"fields": fields}, ensure_ascii=True)

def _filter_extracted_fields(kind: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    if not fields:
        return {}
    if kind == "project":
        allowed = {
            "project_name",
            "status",
            "sponsor",
            "sponsor_user_soeid",
            "priority",
            "description",
            "success_criteria",
            "strategic_objective",
        }
    elif kind == "subcomponent":
        allowed = {
            "subcomponent_name",
            "status",
            "priority",
            "assignee",
            "assignee_user_soeid",
            "due_date",
            "blocked",
            "blocker_note",
            "done_criteria",
            "estimate_hours",
            "capacity_hours",
        }
    else:
        allowed = {
            "solution_name",
            "version",
            "status",
            "owner",
            "owner_user_soeid",
            "assignee",
            "assignee_user_soeid",
            "priority",
            "capacity_hours",
            "due_date",
            "current_phase",
            "impact_confidence",
            "description",
            "success_criteria",
            "risks",
            "blockers",
            "rag_status",
            "rag_reason",
        }
    filtered: Dict[str, Any] = {}
    for key, value in fields.items():
        if key == "instruction" or key not in allowed:
            continue
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        filtered[key] = value
    return filtered


def _format_extracted_fields(fields: Dict[str, Any]) -> str:
    if not fields:
        return ""
    lines = []
    for key in sorted(fields.keys()):
        value = fields[key]
        try:
            rendered = json.dumps(value, ensure_ascii=True)
        except Exception:
            rendered = json.dumps(str(value), ensure_ascii=True)
        lines.append(f"- {key}: {rendered}")
    if not lines:
        return ""
    return "Extracted fields (hints, may need refinement):\n" + "\n".join(lines) + "\n"

def _call_with_timeout(fn, *args, timeout_s: int):
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn, *args)
    try:
        return future.result(timeout=timeout_s)
    finally:
        # Avoid waiting for a timed-out worker; allow request flow to proceed.
        executor.shutdown(wait=False, cancel_futures=True)


def _safe_call(
    system_prompt: str,
    user_prompt: str,
    trace: Optional[List[Dict[str, Any]]] = None,
    trace_label: Optional[str] = None,
) -> str:
    timeout_s = int(os.getenv("AI_MODEL_TIMEOUT_SECONDS", "60"))
    started = datetime.now(timezone.utc)
    response = _call_with_timeout(call_chat_completion, system_prompt, user_prompt, timeout_s=timeout_s)
    if trace is not None:
        trace.append(
            {
                "type": "llm",
                "label": trace_label or "call",
                "started_at": started.isoformat(),
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response_raw": response,
            }
        )
    return response


def _current_user_label(current_user: Optional[Dict[str, Any]]) -> str:
    if not current_user:
        return ""
    name = (current_user.get("display_name") or "").strip()
    soeid = (current_user.get("soeid") or "").strip()
    if name and soeid:
        return f"{name} ({soeid})"
    return name or soeid or ""


def _with_current_user(instruction: Optional[str], current_user: Optional[Dict[str, Any]]) -> str:
    base = (instruction or "").strip()
    if not current_user:
        return base
    name = (current_user.get("display_name") or "").strip()
    soeid = (current_user.get("soeid") or "").strip()
    if not name and not soeid:
        return base
    if base:
        if name and soeid:
            return f"{base}\nCurrent user display_name: {name}\nCurrent user soeid: {soeid}"
        if name:
            return f"{base}\nCurrent user display_name: {name}"
        return f"{base}\nCurrent user soeid: {soeid}"
    if name and soeid:
        return f"Current user display_name: {name}\nCurrent user soeid: {soeid}"
    if name:
        return f"Current user display_name: {name}"
    return f"Current user soeid: {soeid}"


def _run_context_preamble(current_user: Optional[Dict[str, Any]]) -> str:
    """Preamble appended to every LLM call for determinism and traceability."""
    now_dt = datetime.now(timezone.utc)
    lines = [
        f"Today's date and time: {now_dt.isoformat()}",
        f"Today's date: {now_dt.date().isoformat()}",
    ]
    if current_user:
        name = (current_user.get("display_name") or "").strip()
        soeid = (current_user.get("soeid") or "").strip()
        if name:
            lines.append(f"Current user display_name: {name}")
        if soeid:
            lines.append(f"Current user soeid (user identifier): {soeid}")
    return "\n".join(lines) + "\n\n"


def _draft_update(
    context: Dict[str, Any],
    instruction: str,
    trace: Optional[List[Dict[str, Any]]] = None,
    current_user: Optional[str] = None,
) -> str:
    instruction = _with_current_user(instruction, current_user)
    return _safe_call(
        _system_prompt("update"),
        _user_prompt("update", context, instruction),
        trace=trace,
        trace_label="draft_update",
    )


def _draft_charter(
    context: Dict[str, Any],
    instruction: str,
    trace: Optional[List[Dict[str, Any]]] = None,
    current_user: Optional[str] = None,
) -> str:
    preamble = _run_context_preamble(current_user)
    prompt = (
        "Create a Project Charter. Return JSON only with:\n"
        "- content: markdown string\n"
        "- question: string (only if missing required info)\n"
    )
    user_prompt = f"{preamble}{prompt}\nInstruction: {instruction or 'N/A'}"
    return _safe_call(_system_prompt("charter"), user_prompt, trace=trace, trace_label="draft_charter")


def _draft_plan(
    context: Dict[str, Any],
    instruction: str,
    trace: Optional[List[Dict[str, Any]]] = None,
    current_user: Optional[str] = None,
) -> str:
    preamble = _run_context_preamble(current_user)
    prompt = (
        "Create a Project Plan. Return JSON only with:\n"
        "- content: markdown string\n"
        "- question: string (only if missing required info)\n"
    )
    user_prompt = f"{preamble}{prompt}\nInstruction: {instruction or 'N/A'}"
    return _safe_call(_system_prompt("plan"), user_prompt, trace=trace, trace_label="draft_plan")


def _draft_decision_log(
    context: Dict[str, Any],
    instruction: str,
    trace: Optional[List[Dict[str, Any]]] = None,
    current_user: Optional[str] = None,
) -> str:
    preamble = _run_context_preamble(current_user)
    prompt = (
        "Create a Project Decision Log entry. Return JSON only with:\n"
        "- content: markdown string\n"
        "- question: string (only if missing required info)\n"
    )
    user_prompt = f"{preamble}{prompt}\nInstruction: {instruction or 'N/A'}"
    return _safe_call(
        _system_prompt("decision_log"),
        user_prompt,
        trace=trace,
        trace_label="draft_decision_log",
    )


def _draft_subcomponents(
    context: Dict[str, Any],
    instruction: str,
    trace: Optional[List[Dict[str, Any]]] = None,
    current_user: Optional[str] = None,
) -> str:
    instruction = _with_current_user(instruction, current_user)
    return _safe_call(
        _system_prompt("subcomponents"),
        _user_prompt("subcomponents", context, instruction),
        trace=trace,
        trace_label="draft_subcomponents",
    )


def _draft_sow(
    context: Dict[str, Any],
    instruction: str,
    trace: Optional[List[Dict[str, Any]]] = None,
    current_user: Optional[str] = None,
) -> str:
    instruction = _with_current_user(instruction, current_user)
    return _safe_call(
        _system_prompt("sow"),
        _user_prompt("sow", context, instruction),
        trace=trace,
        trace_label="draft_sow",
    )


def _draft_checklist(
    context: Dict[str, Any],
    instruction: str,
    trace: Optional[List[Dict[str, Any]]] = None,
    current_user: Optional[str] = None,
) -> str:
    instruction = _with_current_user(instruction, current_user)
    return _safe_call(
        _system_prompt("checklist"),
        _user_prompt("checklist", context, instruction),
        trace=trace,
        trace_label="draft_checklist",
    )

def _draft_solution_create(
    instruction: str,
    extracted_fields: Optional[Dict[str, Any]] = None,
    trace: Optional[List[Dict[str, Any]]] = None,
    current_user: Optional[str] = None,
) -> str:
    preamble = _run_context_preamble(current_user)
    extra = _format_extracted_fields(_filter_extracted_fields("solution", extracted_fields or {}))
    prompt = _solution_prompt(instruction)
    if extra:
        prompt = (
            f"{prompt}\n{extra}"
            "Use the extracted fields as hints. You may refine or split them if they contain multiple labeled values. "
            "Do not ask for information that is already present.\n"
        )
    return _safe_call(
        _system_prompt("solution_create"),
        preamble + prompt,
        trace=trace,
        trace_label="draft_solution_create",
    )

def _draft_subcomponent_create(
    instruction: str,
    extracted_fields: Optional[Dict[str, Any]] = None,
    trace: Optional[List[Dict[str, Any]]] = None,
    current_user: Optional[str] = None,
) -> str:
    preamble = _run_context_preamble(current_user)
    extra = _format_extracted_fields(_filter_extracted_fields("subcomponent", extracted_fields or {}))
    prompt = _subcomponent_prompt(instruction)
    if extra:
        prompt = (
            f"{prompt}\n{extra}"
            "Use the extracted fields as hints. You may refine or split them if they contain multiple labeled values. "
            "Do not ask for information that is already present.\n"
        )
    return _safe_call(
        _system_prompt("subcomponent_create"),
        preamble + prompt,
        trace=trace,
        trace_label="draft_subcomponent_create",
    )

def _draft_project_create(
    instruction: str,
    extracted_fields: Optional[Dict[str, Any]] = None,
    trace: Optional[List[Dict[str, Any]]] = None,
    current_user: Optional[str] = None,
) -> str:
    preamble = _run_context_preamble(current_user)
    extra = _format_extracted_fields(_filter_extracted_fields("project", extracted_fields or {}))
    prompt = _project_prompt(instruction)
    if extra:
        prompt = (
            f"{prompt}\n{extra}"
            "Use the extracted fields as hints. You may refine or split them if they contain multiple labeled values "
            "(e.g., project name vs client vs business unit). Do not ask for information that is already present.\n"
        )
    return _safe_call(
        _system_prompt("project_create"),
        preamble + prompt,
        trace=trace,
        trace_label="draft_project_create",
    )

def _tool_signature(tool: Optional[str], args: Dict[str, Any]) -> str:
    try:
        return json.dumps({"tool": tool, "args": args}, sort_keys=True)
    except Exception:
        return f"{tool}:{args}"


_DRILLDOWN_TOOLS = {
    "get_entity_fields",
    "read_project_detail",
    "read_solution_detail",
    "read_subcomponent_detail",
    "read_artifacts_detail",
    "read_sow_document",
    "read_external_doc",
}


def _json_metrics(value: Any) -> tuple[int, int]:
    try:
        payload = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    except Exception:
        payload = str(value)
    byte_len = len(payload.encode("utf-8"))
    token_est = max(1, int(len(payload) / 4)) if payload else 0
    return byte_len, token_est


def _tool_telemetry(tool: Optional[str], args: Dict[str, Any], output: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
    payload_bytes, payload_tokens = _json_metrics(args or {})
    output_bytes, output_tokens = _json_metrics(output or {})
    cache_hit = bool((output or {}).get("cache_hit")) if isinstance(output, dict) else False
    drilldown = bool(tool in _DRILLDOWN_TOOLS)
    if isinstance(output, dict):
        drilldown = drilldown or bool(output.get("drilldown"))
    context_packet = _context_packet(state.get("context") or {}, state.get("current_user"))
    context_bytes, _ = _json_metrics(context_packet)
    return {
        "payload_bytes": payload_bytes,
        "payload_tokens": payload_tokens,
        "output_bytes": output_bytes,
        "output_tokens": output_tokens,
        "cache_hit": cache_hit,
        "drilldown": drilldown,
        "context_bytes": context_bytes,
    }


def _tool_dispatch(state: AgentState, session) -> AgentState:
    updates: AgentState = {
        "steps": int(state.get("steps") or 0) + 1,
        "pending_tool": None,
    }
    deadline_s = state.get("deadline_s")
    if deadline_s and time.monotonic() > deadline_s:
        updates["response"] = "AI request timed out. Try again."
        updates["requires_approval"] = False
        updates["request_type"] = None
        updates["output"] = None
        updates["halt"] = True
        updates["last_error"] = "wall_timeout"
        return updates
    trace_enabled = bool(state.get("trace_enabled"))
    trace = list(state.get("trace") or [])
    max_steps = int(state.get("max_steps") or 0)
    if max_steps and int(state.get("steps") or 0) >= max_steps:
        updates["response"] = (
            "I hit the internal step limit while processing this request. "
            "Please clarify the target entity and the exact action you want."
        )
        updates["requires_approval"] = False
        updates["request_type"] = None
        updates["output"] = None
        updates["halt"] = True
        updates["last_error"] = "step_limit"
        if trace_enabled:
            trace.append(
                {
                    "type": "halt",
                    "reason": "step_limit",
                    "step": int(state.get("steps") or 0),
                    "time": datetime.now(timezone.utc).isoformat(),
                }
            )
            updates["trace"] = trace
        return updates
    pending = state.get("pending_tool") or {}
    tool = pending.get("tool")
    args = pending.get("args") or {}
    if not isinstance(args, dict):
        args = {}
    space_id = state.get("space_id")
    output: Dict[str, Any] = {}
    if tool in _WRITE_TOOLS_BLOCKED_IN_CHAT:
        output = {
            "error": (
                f"Direct write tool '{tool}' is disabled in chat. "
                "Return a draft and require explicit /ai/approve."
            )
        }
        log_tool_call(session, tool or "unknown", args, output, space_id=space_id, status="blocked", elapsed_ms=0)
        session.flush()
        updates["response"] = (
            "I can prepare a draft, but saving requires explicit approval. "
            "Please ask for a draft update/create and then approve it."
        )
        updates["requires_approval"] = False
        updates["request_type"] = None
        updates["output"] = None
        updates["halt"] = True
        updates["last_error"] = "write_tool_blocked"
        if trace_enabled:
            trace.append(
                {
                    "type": "halt",
                    "reason": "write_tool_blocked",
                    "tool": tool,
                    "args": args,
                    "time": datetime.now(timezone.utc).isoformat(),
                }
            )
            updates["trace"] = trace
        return updates

    signature = _tool_signature(tool, args)
    history = list(state.get("tool_history") or [])
    history.append(signature)
    if len(history) > 12:
        history = history[-12:]
    updates["tool_history"] = history

    last_signature = state.get("last_tool_signature")
    repeats = int(state.get("last_tool_repeats") or 0)
    if signature == last_signature:
        repeats += 1
    else:
        repeats = 0
    updates["last_tool_signature"] = signature
    updates["last_tool_repeats"] = repeats

    tool_calls = int(state.get("tool_calls") or 0)
    context_calls = int(state.get("context_calls") or 0)
    max_tool_calls = int(os.getenv("AI_MAX_TOOL_CALLS", "12"))
    max_context_calls = int(os.getenv("AI_MAX_CONTEXT_CALLS", "4"))
    if max_tool_calls and tool_calls >= max_tool_calls:
        output = {"error": "Tool call limit reached."}
        log_tool_call(session, tool or "unknown", args, output, space_id=space_id, status="error", elapsed_ms=0)
        session.flush()
        updates["response"] = (
            "I keep calling tools without making progress. "
            "Please confirm the target project/solution or provide the exact names."
        )
        updates["requires_approval"] = False
        updates["request_type"] = None
        updates["output"] = None
        updates["halt"] = True
        updates["last_error"] = output.get("error")
        if trace_enabled:
            trace.append(
                {
                    "type": "halt",
                    "reason": "tool_limit",
                    "tool": tool,
                    "args": args,
                    "time": datetime.now(timezone.utc).isoformat(),
                }
            )
            updates["trace"] = trace
        return updates
    if tool in _CONTEXT_TOOLS and max_context_calls and context_calls >= max_context_calls:
        output = {"error": "Context tool limit reached."}
        log_tool_call(session, tool or "unknown", args, output, space_id=space_id, status="error", elapsed_ms=0)
        session.flush()
        updates["response"] = (
            "I keep reloading context without making progress. "
            "Please confirm the target entity or provide any missing required fields."
        )
        updates["requires_approval"] = False
        updates["request_type"] = None
        updates["output"] = None
        updates["halt"] = True
        updates["last_error"] = output.get("error")
        if trace_enabled:
            trace.append(
                {
                    "type": "halt",
                    "reason": "context_limit",
                    "tool": tool,
                    "args": args,
                    "time": datetime.now(timezone.utc).isoformat(),
                }
            )
            updates["trace"] = trace
        return updates

    updates["tool_calls"] = tool_calls + 1
    if tool in _CONTEXT_TOOLS:
        updates["context_calls"] = context_calls + 1

    if repeats >= 2:
        output = {"error": "Repeated tool call detected; stopping to avoid a loop."}
        log_tool_call(session, tool or "unknown", args, output, space_id=space_id, status="error", elapsed_ms=0)
        session.flush()
        updates["response"] = f"AI tool failed: {output.get('error')}"
        updates["requires_approval"] = False
        updates["request_type"] = None
        updates["output"] = None
        updates["halt"] = True
        updates["last_error"] = output.get("error")
        return updates

    started = datetime.now(timezone.utc)
    status = "ok"

    try:
        if tool == "read_context_complete":
            output = read_context_complete(
                session,
                args.get("entity_type") or state.get("entity_type"),
                args.get("entity_id") or state.get("entity_id"),
                args.get("project_id") or state.get("project_id"),
                args.get("history_limit", 200),
                space_id=space_id,
            )
            updates["context"] = output
        elif tool == "read_context":
            output = read_context(
                session,
                args.get("entity_type") or state.get("entity_type"),
                args.get("entity_id") or state.get("entity_id"),
                args.get("project_id") or state.get("project_id"),
                space_id=space_id,
            )
            updates["context"] = output
        elif tool == "get_scope_digest":
            output = get_scope_digest(
                session,
                project_id=args.get("project_id") or state.get("project_id"),
                solution_id=args.get("solution_id"),
                entity_type=args.get("entity_type") or state.get("entity_type"),
                entity_id=args.get("entity_id") or state.get("entity_id"),
                limit=args.get("limit", 5),
                question=args.get("question") or _latest_user_message(state.get("messages", [])),
                space_id=space_id,
            )
            if isinstance(output, dict):
                updates["context"] = {**(state.get("context") or {}), "scope_digest": output}
        elif tool == "explain_app_usage":
            output = explain_app_usage(
                question=args.get("question") or _latest_user_message(state.get("messages", [])),
                topic=args.get("topic"),
                max_sections=args.get("max_sections", 4),
            )
            if isinstance(output, dict):
                updates["context"] = {**(state.get("context") or {}), "usage_guide": output}
        elif tool == "read_external_doc":
            output = read_external_doc(session, args.get("document_id"), space_id=space_id)
        elif tool == "read_project_detail":
            output = read_project_detail(session, args.get("project_id") or state.get("project_id"), space_id=space_id)
            if isinstance(output, dict):
                updates["context"] = {**(state.get("context") or {}), **output}
        elif tool == "read_solution_detail":
            output = read_solution_detail(session, args.get("solution_id") or state.get("entity_id"), space_id=space_id)
            if isinstance(output, dict):
                updates["context"] = {**(state.get("context") or {}), **output}
        elif tool == "read_subcomponent_detail":
            output = read_subcomponent_detail(
                session,
                args.get("subcomponent_id") or state.get("entity_id"),
                space_id=space_id,
            )
            if isinstance(output, dict):
                updates["context"] = {**(state.get("context") or {}), **output}
        elif tool == "read_artifacts_detail":
            output = read_artifacts_detail(session, args.get("project_id") or state.get("project_id"), space_id=space_id)
            if isinstance(output, dict):
                updates["context"] = {**(state.get("context") or {}), **output}
        elif tool == "read_sow_document":
            output = read_sow_document(session, args.get("sow_id"), space_id=space_id)
            if isinstance(output, dict):
                updates["context"] = {**(state.get("context") or {}), "sow_document_detail": output}
        elif tool == "list_projects":
            output = list_projects(session, args.get("limit", 200), space_id=space_id)
        elif tool == "list_solutions_for_project":
            output = list_solutions_for_project(
                session,
                args.get("project_id") or state.get("project_id"),
                args.get("limit", 200),
                space_id=space_id,
            )
        elif tool == "list_project_cards":
            output = list_project_cards(
                session,
                limit=args.get("limit", 50),
                cursor=args.get("cursor"),
                project_id=args.get("project_id") or state.get("project_id"),
                status=args.get("status"),
                query=args.get("query"),
                fields=args.get("fields"),
                field_pack=args.get("field_pack"),
                question=args.get("question") or _latest_user_message(state.get("messages", [])),
                response_format=args.get("response_format") or args.get("format") or "packed",
                space_id=space_id,
            )
            if isinstance(output, dict):
                updates["context"] = {**(state.get("context") or {}), "project_cards": output}
        elif tool == "list_solution_cards":
            output = list_solution_cards(
                session,
                project_id=args.get("project_id") or state.get("project_id"),
                solution_id=args.get("solution_id"),
                limit=args.get("limit", 50),
                cursor=args.get("cursor"),
                status=args.get("status"),
                rag_status=args.get("rag_status"),
                query=args.get("query"),
                fields=args.get("fields"),
                field_pack=args.get("field_pack"),
                question=args.get("question") or _latest_user_message(state.get("messages", [])),
                response_format=args.get("response_format") or args.get("format") or "packed",
                space_id=space_id,
            )
            if isinstance(output, dict):
                updates["context"] = {**(state.get("context") or {}), "solution_cards": output}
        elif tool == "list_task_cards":
            output = list_task_cards(
                session,
                project_id=args.get("project_id") or state.get("project_id"),
                solution_id=args.get("solution_id") or (state.get("entity_id") if state.get("entity_type") == "solution" else None),
                limit=args.get("limit", 50),
                cursor=args.get("cursor"),
                status=args.get("status"),
                blocked=args.get("blocked"),
                query=args.get("query"),
                fields=args.get("fields"),
                field_pack=args.get("field_pack"),
                question=args.get("question") or _latest_user_message(state.get("messages", [])),
                response_format=args.get("response_format") or args.get("format") or "packed",
                space_id=space_id,
            )
            if isinstance(output, dict):
                updates["context"] = {**(state.get("context") or {}), "task_cards": output}
        elif tool == "get_project_card":
            target_project_id = args.get("project_id") or state.get("project_id")
            if not target_project_id:
                output = {"error": "project_id is required for get_project_card"}
                status = "error"
            else:
                output = get_project_card(
                    session,
                    target_project_id,
                    space_id=space_id,
                    fields=args.get("fields"),
                    field_pack=args.get("field_pack"),
                    question=args.get("question") or _latest_user_message(state.get("messages", [])),
                    response_format=args.get("response_format") or args.get("format") or "objects",
                )
                if isinstance(output, dict):
                    updates["context"] = {**(state.get("context") or {}), "project_card": output.get("card")}
        elif tool == "get_solution_card":
            target_solution_id = args.get("solution_id") or (state.get("entity_id") if state.get("entity_type") == "solution" else None)
            if not target_solution_id:
                output = {"error": "solution_id is required for get_solution_card"}
                status = "error"
            else:
                output = get_solution_card(
                    session,
                    target_solution_id,
                    space_id=space_id,
                    fields=args.get("fields"),
                    field_pack=args.get("field_pack"),
                    question=args.get("question") or _latest_user_message(state.get("messages", [])),
                    response_format=args.get("response_format") or args.get("format") or "objects",
                )
                if isinstance(output, dict):
                    updates["context"] = {**(state.get("context") or {}), "solution_card": output.get("card")}
        elif tool == "get_task_card":
            target_task_id = args.get("task_id") or args.get("subcomponent_id") or (state.get("entity_id") if state.get("entity_type") == "subcomponent" else None)
            if not target_task_id:
                output = {"error": "task_id is required for get_task_card"}
                status = "error"
            else:
                output = get_task_card(
                    session,
                    target_task_id,
                    space_id=space_id,
                    fields=args.get("fields"),
                    field_pack=args.get("field_pack"),
                    question=args.get("question") or _latest_user_message(state.get("messages", [])),
                    response_format=args.get("response_format") or args.get("format") or "objects",
                )
                if isinstance(output, dict):
                    updates["context"] = {**(state.get("context") or {}), "task_card": output.get("card")}
        elif tool == "get_entity_fields":
            target_entity_type = args.get("entity_type") or state.get("entity_type") or ""
            target_entity_id = args.get("entity_id") or state.get("entity_id") or ""
            if not target_entity_type or not target_entity_id:
                output = {"error": "entity_type and entity_id are required for get_entity_fields"}
                status = "error"
            else:
                output = get_entity_fields(
                    session,
                    target_entity_type,
                    target_entity_id,
                    space_id=space_id,
                    fields=args.get("fields"),
                    field_pack=args.get("field_pack"),
                    question=args.get("question") or _latest_user_message(state.get("messages", [])),
                )
                if isinstance(output, dict):
                    updates["context"] = {**(state.get("context") or {}), "entity_fields": output}
        elif tool == "get_entity_deltas":
            output = get_entity_deltas(
                session,
                since_cursor=args.get("since_cursor") or args.get("since"),
                entity_types=args.get("entity_types"),
                project_id=args.get("project_id") or state.get("project_id"),
                solution_id=args.get("solution_id"),
                limit=args.get("limit", 200),
                space_id=space_id,
                fields=args.get("fields"),
                field_pack=args.get("field_pack") or "minimal",
                question=args.get("question") or _latest_user_message(state.get("messages", [])),
            )
            if isinstance(output, dict):
                updates["context"] = {**(state.get("context") or {}), "entity_deltas": output}
        elif tool == "read_entity_index":
            output = read_entity_index(
                session,
                args.get("entity_type") or state.get("entity_type") or "",
                args.get("project_id") or state.get("project_id"),
                args.get("solution_id"),
                args.get("limit", 200),
                space_id=space_id,
            )
        elif tool == "read_entity_deltas":
            output = read_entity_deltas(
                session,
                args.get("entity_type") or state.get("entity_type") or "",
                args.get("since"),
                args.get("limit", 200),
                space_id=space_id,
            )
        elif tool == "validate_draft":
            output = validate_draft(
                session,
                args.get("entity_type") or state.get("entity_type") or "",
                args.get("fields") or {},
                args.get("action", "create"),
                space_id=space_id,
            )
            updates["last_validation"] = output
        elif tool == "apply_draft":
            last_validation = state.get("last_validation") or {}
            if not last_validation or not last_validation.get("valid"):
                output = {"error": "Draft must be validated before apply_draft."}
                status = "error"
            else:
                output = apply_draft(
                    session,
                    args.get("entity_type") or state.get("entity_type") or "",
                    args.get("action", "create"),
                    args.get("fields") or {},
                    args.get("entity_id") or state.get("entity_id"),
                    space_id=space_id,
                )
                if isinstance(output, dict):
                    updates["context"] = {**(state.get("context") or {}), **output}
        elif tool == "verify_write":
            output = verify_write(
                session,
                args.get("entity_type") or state.get("entity_type") or "",
                args.get("entity_id") or state.get("entity_id") or "",
                args.get("expected_fields") or {},
                space_id=space_id,
            )
        elif tool == "search_entities":
            entity_types = args.get("entity_types") if isinstance(args, dict) else None
            if not entity_types and isinstance(args, dict):
                entity_types = args.get("type") or args.get("entity_type")
            return_mode = "ids"
            if isinstance(args, dict):
                return_mode = args.get("return_mode") or args.get("return") or "ids"
            output = search_entities(
                session,
                args.get("query", ""),
                entity_types,
                args.get("limit", 5),
                project_id=args.get("project_id") or state.get("project_id"),
                solution_id=args.get("solution_id"),
                return_mode=return_mode,
                fields=args.get("fields"),
                field_pack=args.get("field_pack"),
                response_format=args.get("response_format") or args.get("format") or "packed",
                space_id=space_id,
            )
            # If there's exactly one match, auto-bind it into context and fetch full details.
            results = output.get("results") if isinstance(output, dict) else None
            if isinstance(results, list) and len(results) == 1:
                match = results[0] or {}
                updates["entity_type"] = match.get("entity_type") or state.get("entity_type")
                updates["entity_id"] = match.get("entity_id") or state.get("entity_id")
                updates["project_id"] = match.get("project_id") or state.get("project_id")
                updates["pending_tool"] = {
                    "tool": "read_context",
                    "args": {
                        "entity_type": updates.get("entity_type") or state.get("entity_type"),
                        "entity_id": updates.get("entity_id") or state.get("entity_id"),
                        "project_id": updates.get("project_id") or state.get("project_id"),
                    },
                }
        elif tool == "draft_update":
            context = state.get("context") or {}
            if isinstance(args, dict):
                if args.get("entity_type"):
                    updates["entity_type"] = args.get("entity_type")
                if args.get("entity_id"):
                    updates["entity_id"] = args.get("entity_id")
                if args.get("project_id"):
                    updates["project_id"] = args.get("project_id")
            fields = args.get("fields") if isinstance(args, dict) else None
            if not fields and isinstance(args, dict):
                fields = args.get("updates")
            if not fields and isinstance(args, dict):
                # If the tool was called with an explicit target entity_id, prefer a deterministic
                # "set field to value" parse to avoid LLM ambiguity ("which entity should I update?").
                target_entity_type = str(updates.get("entity_type") or state.get("entity_type") or "").strip()
                target_entity_id = str(updates.get("entity_id") or state.get("entity_id") or "").strip()
                if target_entity_type and target_entity_id and isinstance(args.get("instruction"), str):
                    parsed = _parse_simple_update_fields(
                        target_entity_type,
                        args.get("instruction") or "",
                        contracts=context.get("contracts") if isinstance(context, dict) else None,
                        current_date=state.get("current_date"),
                    )
                    if parsed:
                        fields = parsed
            if isinstance(fields, dict) and fields:
                normalized = _normalize_date_fields(fields, state.get("current_date"))
                output = {"output": _render_fields_payload(normalized)}
            else:
                output = {
                    "output": _draft_update(
                        context,
                        args.get("instruction", ""),
                        trace if trace_enabled else None,
                        state.get("current_user"),
                    )
                }
            if _handle_question_output(output.get("output", ""), updates, trace, trace_enabled):
                return updates
            updates["request_type"] = "autofill"
            updates["output"] = output.get("output")
            updates["requires_approval"] = True
        elif tool == "draft_charter":
            context = state.get("context") or {}
            output = {
                "output": _draft_charter(
                    context,
                    args.get("instruction", ""),
                    trace if trace_enabled else None,
                    state.get("current_user"),
                )
            }
            if _handle_question_output(output.get("output", ""), updates, trace, trace_enabled):
                return updates
            updates["request_type"] = "charter_create"
            updates["output"] = output.get("output")
            updates["requires_approval"] = True
        elif tool == "draft_plan":
            context = state.get("context") or {}
            output = {
                "output": _draft_plan(
                    context,
                    args.get("instruction", ""),
                    trace if trace_enabled else None,
                    state.get("current_user"),
                )
            }
            if _handle_question_output(output.get("output", ""), updates, trace, trace_enabled):
                return updates
            updates["request_type"] = "plan_create"
            updates["output"] = output.get("output")
            updates["requires_approval"] = True
        elif tool == "draft_decision_log":
            context = state.get("context") or {}
            output = {
                "output": _draft_decision_log(
                    context,
                    args.get("instruction", ""),
                    trace if trace_enabled else None,
                    state.get("current_user"),
                )
            }
            if _handle_question_output(output.get("output", ""), updates, trace, trace_enabled):
                return updates
            updates["request_type"] = "decision_log_create"
            updates["output"] = output.get("output")
            updates["requires_approval"] = True
        elif tool == "draft_subcomponents":
            instruction = args.get("instruction") or _latest_user_message(state.get("messages", []))
            # Drafting subcomponents should always be scoped to a specific solution. If the agent didn't pass a
            # solution_id, resolve it deterministically (prefer project scoping) and then load solution context.
            solution_id = None
            if isinstance(args, dict):
                solution_id = args.get("solution_id") or args.get("entity_id")
            if not solution_id and state.get("entity_type") == "solution" and state.get("entity_id"):
                solution_id = state.get("entity_id")

            project_id = None
            if isinstance(args, dict):
                project_id = args.get("project_id")
            if not project_id:
                project_id = state.get("project_id")
            if not project_id and state.get("entity_type") == "project" and state.get("entity_id"):
                project_id = state.get("entity_id")

            if not solution_id:
                # Use an LLM to interpret solution/project references from the instruction (more robust than regex).
                refs: Dict[str, str] = {}
                try:
                    refs = _extract_references_from_instruction_llm(
                        instruction,
                        trace=trace if trace_enabled else None,
                        current_user=state.get("current_user"),
                    )
                except Exception:
                    refs = {}

                solution_name = refs.get("solution_name") or _extract_name_from_instruction("solution", instruction)
                project_name = refs.get("project_name")

                if project_name and not project_id:
                    try:
                        proj_matches = search_entities(
                            session,
                            project_name,
                            ["project"],
                            5,
                            space_id=space_id,
                        ).get("results") or []
                        if isinstance(proj_matches, list) and len(proj_matches) == 1:
                            match = proj_matches[0] or {}
                            project_id = match.get("project_id") or match.get("entity_id") or project_id
                    except Exception:
                        pass

                # Prefer resolving from the currently loaded context, if present.
                context = state.get("context") or {}
                if (
                    solution_name
                    and isinstance(context, dict)
                    and isinstance(context.get("solutions"), list)
                ):
                    candidates = [
                        s
                        for s in (context.get("solutions") or [])
                        if isinstance(s, dict)
                        and (str(s.get("solution_name") or "").strip().lower() == solution_name.strip().lower())
                    ]
                    if len(candidates) > 1 and project_id and isinstance(context.get("project"), dict):
                        # In a project-scoped context, candidates should already be from that project.
                        candidates = candidates
                    if len(candidates) == 1:
                        solution_id = candidates[0].get("solution_id")

                if solution_name and not solution_id:
                    matches = search_entities(
                        session,
                        solution_name,
                        ["solution"],
                        10,
                        space_id=space_id,
                    ).get("results") or []
                    if isinstance(matches, list) and len(matches) > 1 and project_id:
                        scoped = [
                            m
                            for m in matches
                            if isinstance(m, dict) and (m.get("project_id") or "") == project_id
                        ]
                        if len(scoped) == 1:
                            matches = scoped
                        elif scoped:
                            matches = scoped

                    if isinstance(matches, list) and len(matches) == 1:
                        match = matches[0] or {}
                        solution_id = match.get("entity_id")
                        project_id = match.get("project_id") or project_id
                    elif isinstance(matches, list) and len(matches) > 1:
                        # Present choices grouped by project to avoid a second "which solution?" loop.
                        proj_map = {
                            p.get("project_id"): p
                            for p in (list_projects(session, 200, space_id=space_id).get("projects") or [])
                        }
                        lines = [f"I found multiple solutions named '{solution_name}' in different projects:"]
                        for idx, m in enumerate(matches[:5], start=1):
                            pid = m.get("project_id")
                            proj = proj_map.get(pid) or {}
                            pname = proj.get("project_name") or pid or "Unknown project"
                            pstatus = proj.get("status")
                            status_suffix = f" (Status: {str(pstatus).replace('_', ' ').title()})" if pstatus else ""
                            lines.append(f"{idx}. Project: {pname}{status_suffix}")
                        question = "\n".join(lines) + "\n\nWhich project should I use?"
                        updates["response"] = question
                        updates["requires_approval"] = False
                        updates["request_type"] = None
                        updates["output"] = None
                        updates["halt"] = True
                        updates["awaiting_user"] = True
                        if trace_enabled:
                            trace.append(
                                {
                                    "type": "ask",
                                    "question": question,
                                    "time": datetime.now(timezone.utc).isoformat(),
                                }
                            )
                            updates["trace"] = trace
                        return updates

            if not solution_id:
                # As a last resort, ask the user for the target solution.
                question = "Which solution should these subcomponents be added to?"
                updates["response"] = question
                updates["requires_approval"] = False
                updates["request_type"] = None
                updates["output"] = None
                updates["halt"] = True
                updates["awaiting_user"] = True
                if trace_enabled:
                    trace.append(
                        {
                            "type": "ask",
                            "question": question,
                            "time": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    updates["trace"] = trace
                return updates

            # Load solution-scoped context so the LLM doesn't have to infer "which solution" from a project-level view.
            updates["entity_type"] = "solution"
            updates["entity_id"] = solution_id
            if project_id:
                updates["project_id"] = project_id
            context = read_context(session, "solution", solution_id, project_id, space_id=space_id)
            updates["context"] = context

            output = {
                "output": _draft_subcomponents(
                    context,
                    instruction,
                    trace if trace_enabled else None,
                    state.get("current_user"),
                )
            }
            if _handle_question_output(output.get("output", ""), updates, trace, trace_enabled):
                return updates
            updates["request_type"] = "subcomponents"
            updates["output"] = output.get("output")
            updates["requires_approval"] = True
        elif tool == "draft_sow":
            context = state.get("context") or {}
            output = {
                "output": _draft_sow(
                    context,
                    args.get("instruction", ""),
                    trace if trace_enabled else None,
                    state.get("current_user"),
                )
            }
            if _handle_question_output(output.get("output", ""), updates, trace, trace_enabled):
                return updates
            updates["request_type"] = "sow"
            updates["output"] = output.get("output")
            updates["requires_approval"] = True
        elif tool == "draft_checklist":
            context = state.get("context") or {}
            output = {
                "output": _draft_checklist(
                    context,
                    args.get("instruction", ""),
                    trace if trace_enabled else None,
                    state.get("current_user"),
                )
            }
            if _handle_question_output(output.get("output", ""), updates, trace, trace_enabled):
                return updates
            updates["request_type"] = "checklist"
            updates["output"] = output.get("output")
            updates["requires_approval"] = True
        elif tool == "draft_create_solution":
            instruction = args.get("instruction") or _latest_user_message(state.get("messages", []))
            extracted_fields = args if isinstance(args, dict) else {}
            augmented_fields = dict(extracted_fields)
            current_user = state.get("current_user") or {}
            current_user_name = (current_user.get("display_name") or "").strip()
            current_user_soeid = (current_user.get("soeid") or "").strip()
            if not augmented_fields.get("solution_name"):
                inferred_name = _extract_name_from_instruction("solution", instruction)
                if inferred_name:
                    augmented_fields["solution_name"] = inferred_name
            if not augmented_fields.get("status"):
                inferred_status = _extract_status_from_instruction("solution", instruction)
                if inferred_status:
                    augmented_fields["status"] = inferred_status
            if not augmented_fields.get("status"):
                augmented_fields["status"] = "not_started"
            if not augmented_fields.get("version"):
                augmented_fields["version"] = "0.1.0"
            if not augmented_fields.get("owner"):
                inferred_owner = _extract_assignee_from_instruction(instruction)
                if inferred_owner:
                    augmented_fields["owner"] = inferred_owner
            if not augmented_fields.get("owner"):
                augmented_fields["owner"] = current_user_name or current_user_soeid or "Owner"
            if not augmented_fields.get("owner_user_soeid"):
                owner = str(augmented_fields.get("owner") or "").strip()
                if current_user_soeid and (owner == current_user_name or owner == current_user_soeid):
                    augmented_fields["owner_user_soeid"] = current_user_soeid
            if not augmented_fields.get("assignee"):
                inferred_assignee = _extract_assignee_from_instruction(instruction)
                if inferred_assignee:
                    augmented_fields["assignee"] = inferred_assignee
            if not augmented_fields.get("assignee"):
                augmented_fields["assignee"] = augmented_fields.get("owner")
            if not augmented_fields.get("assignee_user_soeid"):
                assignee = str(augmented_fields.get("assignee") or "").strip()
                if current_user_soeid and (assignee == current_user_name or assignee == current_user_soeid):
                    augmented_fields["assignee_user_soeid"] = current_user_soeid
            if augmented_fields.get("priority") is None:
                augmented_fields["priority"] = 3
            if not augmented_fields.get("rag_status"):
                augmented_fields["rag_status"] = "green"
            if not augmented_fields.get("due_date"):
                inferred_due = _extract_due_date_from_instruction(instruction, state.get("current_date"))
                if inferred_due:
                    augmented_fields["due_date"] = inferred_due
            augmented_fields = _normalize_date_fields(augmented_fields, state.get("current_date"))
            project_id = augmented_fields.get("project_id") or state.get("project_id")
            if not project_id and state.get("entity_type") == "project" and state.get("entity_id"):
                project_id = state.get("entity_id")
            if not project_id:
                # Use an LLM to interpret the instruction instead of brittle regex matching.
                project_name: Optional[str] = None
                try:
                    refs = _extract_references_from_instruction_llm(
                        instruction,
                        trace=trace if trace_enabled else None,
                        current_user=state.get("current_user"),
                    )
                    project_name = refs.get("project_name")
                except Exception:
                    project_name = None

                if project_name:
                    matches = search_entities(
                        session,
                        project_name,
                        ["project"],
                        5,
                        space_id=space_id,
                    ).get("results") or []
                    if isinstance(matches, list) and len(matches) == 1:
                        match = matches[0] or {}
                        project_id = match.get("project_id") or match.get("entity_id")
                    elif isinstance(matches, list) and len(matches) > 1:
                        labels = [
                            m.get("label")
                            for m in matches
                            if isinstance(m, dict) and isinstance(m.get("label"), str) and m.get("label")
                        ]
                        options = ", ".join(labels[:5]) if labels else "multiple projects"
                        question = (
                            f"I found multiple projects matching '{project_name}': {options}. "
                            "Which one should I use?"
                        )
                        updates["response"] = question
                        updates["requires_approval"] = False
                        updates["request_type"] = None
                        updates["output"] = None
                        updates["halt"] = True
                        updates["awaiting_user"] = True
                        if trace_enabled:
                            trace.append(
                                {
                                    "type": "ask",
                                    "question": question,
                                    "time": datetime.now(timezone.utc).isoformat(),
                                }
                            )
                            updates["trace"] = trace
                        return updates
                    else:
                        question = (
                            f"I couldn't find a project matching '{project_name}'. "
                            "Which project should this solution belong to?"
                        )
                        updates["response"] = question
                        updates["requires_approval"] = False
                        updates["request_type"] = None
                        updates["output"] = None
                        updates["halt"] = True
                        updates["awaiting_user"] = True
                        if trace_enabled:
                            trace.append(
                                {
                                    "type": "ask",
                                    "question": question,
                                    "time": datetime.now(timezone.utc).isoformat(),
                                }
                            )
                            updates["trace"] = trace
                        return updates
            if not project_id:
                question = "Which project should this solution belong to?"
                updates["response"] = question
                updates["requires_approval"] = False
                updates["request_type"] = None
                updates["output"] = None
                updates["halt"] = True
                updates["awaiting_user"] = True
                if trace_enabled:
                    trace.append(
                        {
                            "type": "ask",
                            "question": question,
                            "time": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    updates["trace"] = trace
                return updates

            augmented_fields["project_id"] = project_id
            updates["project_id"] = project_id
            updates["entity_type"] = "project"
            updates["entity_id"] = project_id
            output_text = _draft_solution_create(
                instruction,
                augmented_fields,
                trace if trace_enabled else None,
                state.get("current_user"),
            )
            if _handle_question_output(output_text, updates, trace, trace_enabled):
                return updates
            filtered_fields = _filter_extracted_fields("solution", augmented_fields)
            parsed_fields = _parse_fields_block(output_text) if _has_fields_section(output_text) else {}
            merged_fields = _normalize_date_fields({**filtered_fields, **parsed_fields}, state.get("current_date"))
            if merged_fields:
                output_text = _render_fields_payload(merged_fields)
            if isinstance(output_text, str) and not _has_fields_section(output_text):
                coerced = _render_fields_payload(filtered_fields) if filtered_fields else None
                if not coerced:
                    coerced = _coerce_create_output("solution", instruction, state.get("current_date"))
                if coerced:
                    output_text = coerced
                else:
                    updates["response"] = "What should the solution be called?"
                    updates["requires_approval"] = False
                    updates["request_type"] = None
                    updates["output"] = None
                    updates["halt"] = True
                    updates["awaiting_user"] = True
                    if trace_enabled:
                        trace.append(
                            {
                                "type": "ask",
                                "question": updates["response"],
                                "time": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                        updates["trace"] = trace
                    return updates
            output = {"output": output_text}
            updates["request_type"] = "solution_create"
            updates["output"] = output.get("output")
            updates["requires_approval"] = True
        elif tool == "draft_create_subcomponent":
            instruction = args.get("instruction") or _latest_user_message(state.get("messages", []))
            extracted_fields = args if isinstance(args, dict) else {}
            augmented_fields = dict(extracted_fields)
            current_user = state.get("current_user") or {}
            current_user_name = (current_user.get("display_name") or "").strip()
            current_user_soeid = (current_user.get("soeid") or "").strip()
            if not augmented_fields.get("subcomponent_name"):
                inferred_name = _extract_name_from_instruction("subcomponent", instruction)
                if inferred_name:
                    augmented_fields["subcomponent_name"] = inferred_name
            if not augmented_fields.get("status"):
                inferred_status = _extract_status_from_instruction("subcomponent", instruction)
                if inferred_status:
                    augmented_fields["status"] = inferred_status
            if not augmented_fields.get("status"):
                augmented_fields["status"] = "to_do"
            if augmented_fields.get("priority") is None:
                augmented_fields["priority"] = 3
            if augmented_fields.get("blocked") is None:
                augmented_fields["blocked"] = False
            if not augmented_fields.get("assignee"):
                inferred_assignee = _extract_assignee_from_instruction(instruction)
                if inferred_assignee:
                    augmented_fields["assignee"] = inferred_assignee
            if not augmented_fields.get("assignee"):
                augmented_fields["assignee"] = current_user_name or current_user_soeid or ""
            if not augmented_fields.get("assignee_user_soeid"):
                assignee = str(augmented_fields.get("assignee") or "").strip()
                if current_user_soeid and (assignee == current_user_name or assignee == current_user_soeid):
                    augmented_fields["assignee_user_soeid"] = current_user_soeid
            if not augmented_fields.get("due_date"):
                inferred_due = _extract_due_date_from_instruction(instruction, state.get("current_date"))
                if inferred_due:
                    augmented_fields["due_date"] = inferred_due
            augmented_fields = _normalize_date_fields(augmented_fields, state.get("current_date"))

            # Prefer the existing solution context; otherwise resolve by a referenced solution name.
            solution_id = augmented_fields.get("solution_id")
            project_id = augmented_fields.get("project_id") or state.get("project_id")
            if not solution_id and state.get("entity_type") == "solution" and state.get("entity_id"):
                solution_id = state.get("entity_id")
            if not solution_id:
                # Use an LLM to interpret solution/project references instead of regex matching.
                refs: Dict[str, str] = {}
                try:
                    refs = _extract_references_from_instruction_llm(
                        instruction,
                        trace=trace if trace_enabled else None,
                        current_user=state.get("current_user"),
                    )
                except Exception:
                    refs = {}

                solution_name = refs.get("solution_name") or _extract_name_from_instruction("solution", instruction)
                project_name_hint = refs.get("project_name")
                if project_name_hint and not project_id:
                    # If a project name is present, try to scope the solution search to that project.
                    try:
                        proj_matches = search_entities(
                            session,
                            project_name_hint,
                            ["project"],
                            5,
                            space_id=space_id,
                        ).get("results") or []
                        if isinstance(proj_matches, list) and len(proj_matches) == 1:
                            match = proj_matches[0] or {}
                            project_id = match.get("project_id") or match.get("entity_id") or project_id
                    except Exception:
                        pass
                if solution_name:
                    matches = search_entities(
                        session,
                        solution_name,
                        ["solution"],
                        5,
                        space_id=space_id,
                    ).get("results") or []
                    if isinstance(matches, list) and len(matches) > 1 and project_id:
                        scoped = [
                            m
                            for m in matches
                            if isinstance(m, dict) and (m.get("project_id") or "") == project_id
                        ]
                        if len(scoped) == 1:
                            matches = scoped
                        elif scoped:
                            matches = scoped

                    if isinstance(matches, list) and len(matches) == 1:
                        match = matches[0] or {}
                        solution_id = match.get("entity_id")
                        project_id = match.get("project_id") or project_id
                    elif isinstance(matches, list) and len(matches) > 1:
                        labels = [
                            m.get("label")
                            for m in matches
                            if isinstance(m, dict) and isinstance(m.get("label"), str) and m.get("label")
                        ]
                        options = ", ".join(labels[:5]) if labels else "multiple solutions"
                        question = (
                            f"I found multiple solutions matching '{solution_name}': {options}. "
                            "Which one should I use?"
                        )
                        updates["response"] = question
                        updates["requires_approval"] = False
                        updates["request_type"] = None
                        updates["output"] = None
                        updates["halt"] = True
                        updates["awaiting_user"] = True
                        if trace_enabled:
                            trace.append(
                                {
                                    "type": "ask",
                                    "question": question,
                                    "time": datetime.now(timezone.utc).isoformat(),
                                }
                            )
                            updates["trace"] = trace
                        return updates
                    else:
                        question = (
                            f"I couldn't find a solution matching '{solution_name}'. "
                            "Which solution should this subcomponent belong to?"
                        )
                        updates["response"] = question
                        updates["requires_approval"] = False
                        updates["request_type"] = None
                        updates["output"] = None
                        updates["halt"] = True
                        updates["awaiting_user"] = True
                        if trace_enabled:
                            trace.append(
                                {
                                    "type": "ask",
                                    "question": question,
                                    "time": datetime.now(timezone.utc).isoformat(),
                                }
                            )
                            updates["trace"] = trace
                        return updates

            if not solution_id:
                question = "Which solution should this subcomponent belong to?"
                updates["response"] = question
                updates["requires_approval"] = False
                updates["request_type"] = None
                updates["output"] = None
                updates["halt"] = True
                updates["awaiting_user"] = True
                if trace_enabled:
                    trace.append(
                        {
                            "type": "ask",
                            "question": question,
                            "time": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    updates["trace"] = trace
                return updates

            augmented_fields["solution_id"] = solution_id
            updates["entity_type"] = "solution"
            updates["entity_id"] = solution_id
            if project_id:
                augmented_fields["project_id"] = project_id
                updates["project_id"] = project_id

            output_text = _draft_subcomponent_create(
                instruction,
                augmented_fields,
                trace if trace_enabled else None,
                state.get("current_user"),
            )
            if _handle_question_output(output_text, updates, trace, trace_enabled):
                return updates
            filtered_fields = _filter_extracted_fields("subcomponent", augmented_fields)
            parsed_fields = _parse_fields_block(output_text) if _has_fields_section(output_text) else {}
            merged_fields = _normalize_date_fields({**filtered_fields, **parsed_fields}, state.get("current_date"))
            if merged_fields:
                output_text = _render_fields_payload(merged_fields)
            if isinstance(output_text, str) and not _has_fields_section(output_text):
                coerced = _render_fields_payload(filtered_fields) if filtered_fields else None
                if not coerced:
                    coerced = _coerce_create_output("subcomponent", instruction, state.get("current_date"))
                if coerced:
                    output_text = coerced
                else:
                    updates["response"] = "What should the subcomponent be called?"
                    updates["requires_approval"] = False
                    updates["request_type"] = None
                    updates["output"] = None
                    updates["halt"] = True
                    updates["awaiting_user"] = True
                    if trace_enabled:
                        trace.append(
                            {
                                "type": "ask",
                                "question": updates["response"],
                                "time": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                        updates["trace"] = trace
                    return updates
            output = {"output": output_text}
            updates["request_type"] = "subcomponent_create"
            updates["output"] = output.get("output")
            updates["requires_approval"] = True
        elif tool == "draft_create_project":
            instruction = args.get("instruction") or _latest_user_message(state.get("messages", []))
            extracted_fields = args if isinstance(args, dict) else {}
            augmented_fields = dict(extracted_fields)
            current_user = state.get("current_user") or {}
            current_user_name = (current_user.get("display_name") or "").strip()
            current_user_soeid = (current_user.get("soeid") or "").strip()
            if not augmented_fields.get("project_name"):
                inferred_name = _extract_name_from_instruction("project", instruction)
                if inferred_name:
                    augmented_fields["project_name"] = inferred_name
            if not augmented_fields.get("status"):
                inferred_status = _extract_status_from_instruction("project", instruction)
                if inferred_status:
                    augmented_fields["status"] = inferred_status
            if not augmented_fields.get("status"):
                augmented_fields["status"] = "not_started"
            if not augmented_fields.get("sponsor"):
                inferred_sponsor = _extract_assignee_from_instruction(instruction)
                if inferred_sponsor:
                    augmented_fields["sponsor"] = inferred_sponsor
            if not augmented_fields.get("sponsor"):
                augmented_fields["sponsor"] = current_user_name or current_user_soeid or "Sponsor"
            if not augmented_fields.get("sponsor_user_soeid"):
                # Only default the sponsor SOEID when sponsor is the current user (or unspecified).
                sponsor = str(augmented_fields.get("sponsor") or "").strip()
                if (not sponsor) or (current_user_soeid and sponsor == current_user_name):
                    augmented_fields["sponsor_user_soeid"] = current_user_soeid or None
            if augmented_fields.get("priority") is None:
                augmented_fields["priority"] = 3
            if not augmented_fields.get("description"):
                inferred_description = _extract_project_metadata(instruction)
                if inferred_description:
                    augmented_fields["description"] = inferred_description
            if augmented_fields.get("project_id"):
                updates["project_id"] = augmented_fields.get("project_id")
            output_text = _draft_project_create(
                instruction,
                augmented_fields,
                trace if trace_enabled else None,
                state.get("current_user"),
            )
            if _handle_question_output(output_text, updates, trace, trace_enabled):
                return updates
            filtered_fields = _filter_extracted_fields("project", augmented_fields)
            parsed_fields = _parse_fields_block(output_text) if _has_fields_section(output_text) else {}
            merged_fields = _normalize_project_fields({**filtered_fields, **parsed_fields})
            if merged_fields:
                output_text = _render_fields_payload(merged_fields)
            if isinstance(output_text, str) and not _has_fields_section(output_text):
                coerced = _render_fields_payload(_normalize_project_fields(filtered_fields)) if filtered_fields else None
                if not coerced:
                    coerced = _coerce_create_output("project", instruction, state.get("current_date"))
                if coerced:
                    output_text = coerced
                else:
                    updates["response"] = "What should the project be called?"
                    updates["requires_approval"] = False
                    updates["request_type"] = None
                    updates["output"] = None
                    updates["halt"] = True
                    updates["awaiting_user"] = True
                    if trace_enabled:
                        trace.append(
                            {
                                "type": "ask",
                                "question": updates["response"],
                                "time": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                        updates["trace"] = trace
                    return updates
            output = {"output": output_text}
            updates["request_type"] = "project_create"
            updates["output"] = output.get("output")
            updates["requires_approval"] = True
        else:
            output = {"error": f"Unknown tool: {tool}"}
            status = "error"
    except Exception as exc:
        output = {"error": str(exc)}
        status = "error"

    elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    telemetry = _tool_telemetry(tool, args, output, state)
    updates["metric_bytes_sent"] = int(state.get("metric_bytes_sent") or 0) + int(telemetry.get("payload_bytes") or 0)
    updates["metric_tokens_sent"] = int(state.get("metric_tokens_sent") or 0) + int(telemetry.get("payload_tokens") or 0)
    updates["metric_bytes_returned"] = int(state.get("metric_bytes_returned") or 0) + int(telemetry.get("output_bytes") or 0)
    updates["metric_tokens_returned"] = int(state.get("metric_tokens_returned") or 0) + int(telemetry.get("output_tokens") or 0)
    updates["metric_cache_hits"] = int(state.get("metric_cache_hits") or 0) + (1 if telemetry.get("cache_hit") else 0)
    updates["metric_drilldowns"] = int(state.get("metric_drilldowns") or 0) + (1 if telemetry.get("drilldown") else 0)
    log_tool_call(
        session,
        tool or "unknown",
        args,
        output,
        space_id=space_id,
        status=status,
        elapsed_ms=elapsed_ms,
        telemetry=telemetry,
    )
    session.flush()

    if tool in _CONTEXT_TOOLS:
        queued = state.get("queued_tool")
        if isinstance(queued, dict) and queued.get("tool"):
            updates["pending_tool"] = queued
            updates["queued_tool"] = None

    if trace_enabled:
        trace.append(
            {
                "type": "tool",
                "tool": tool,
                "args": args,
                "status": status,
                "elapsed_ms": elapsed_ms,
                "payload_bytes": telemetry.get("payload_bytes"),
                "output_bytes": telemetry.get("output_bytes"),
                "cache_hit": telemetry.get("cache_hit"),
                "drilldown": telemetry.get("drilldown"),
                "output": output,
                "time": datetime.now(timezone.utc).isoformat(),
            }
        )
        updates["trace"] = trace

    compact_chars = 280
    if tool == "explain_app_usage":
        compact_chars = 1800
    compact_output = _compact_for_prompt(output, max_depth=4, max_items=12, max_chars=compact_chars)
    tool_message = json.dumps({"tool": tool, "result": compact_output}, ensure_ascii=True, separators=(",", ":"))
    updates["messages"] = _append_message([], "tool", tool_message)
    if status == "error":
        updates["response"] = f"AI tool failed: {output.get('error') or 'unknown error'}"
        updates["requires_approval"] = False
        updates["request_type"] = None
        updates["output"] = None
        updates["halt"] = True
        updates["last_error"] = output.get("error") or "unknown error"
        return updates
    if tool and tool.startswith("draft_") and updates.get("output"):
        output_text = str(updates.get("output") or "")
        if "QUESTION:" in output_text:
            question = output_text.split("QUESTION:", 1)[1].strip()
            updates["response"] = question
            updates["requires_approval"] = False
            updates["request_type"] = None
            updates["output"] = None
            updates["halt"] = True
            updates["awaiting_user"] = True
            return updates
        updates["response"] = output_text
        updates["halt"] = True
    return updates


def _agent_step(state: AgentState) -> AgentState:
    if state.get("pending_tool") or state.get("halt"):
        return {}
    deadline_s = state.get("deadline_s")
    if deadline_s and time.monotonic() > deadline_s:
        return {
            "response": "AI request timed out. Try again.",
            "requires_approval": False,
            "request_type": None,
            "output": None,
            "halt": True,
            "last_error": "wall_timeout",
        }
    trace_enabled = bool(state.get("trace_enabled"))
    trace = list(state.get("trace") or [])
    max_steps = int(state.get("max_steps") or 0)
    if max_steps and int(state.get("steps") or 0) >= max_steps:
        return {
            "response": (
                "I hit the internal step limit while processing this request. "
                "Please clarify the target entity and the exact action you want."
            ),
            "requires_approval": False,
            "request_type": None,
            "output": None,
            "halt": True,
            "awaiting_user": True,
            "last_error": "step_limit",
            "trace": trace
            + [
                {
                    "type": "halt",
                    "reason": "step_limit",
                    "step": int(state.get("steps") or 0),
                    "time": datetime.now(timezone.utc).isoformat(),
                }
            ]
            if trace_enabled
            else trace,
        }
    updates: AgentState = {
        "steps": int(state.get("steps") or 0) + 1,
        "pending_tool": None,
    }
    messages = state.get("messages", [])
    system = _agent_system_prompt()
    convo = _compact_history(messages)
    now = datetime.now(timezone.utc).isoformat()
    convo = f"Today's date and time: {now}\n" + convo
    if state.get("current_date"):
        convo = f"Today's date: {state['current_date']}\n" + convo
    if state.get("current_user"):
        user_name = (state.get("current_user") or {}).get("display_name") or ""
        user_soeid = (state.get("current_user") or {}).get("soeid") or ""
        user_name = str(user_name).strip()
        user_soeid = str(user_soeid).strip()
        if user_name or user_soeid:
            if user_name and user_soeid:
                convo = (
                    f"Current user display_name: {user_name}\n"
                    f"Current user soeid (user identifier): {user_soeid}\n"
                    + convo
                )
            elif user_name:
                convo = f"Current user display_name: {user_name}\n" + convo
            else:
                convo = f"Current user soeid (user identifier): {user_soeid}\n" + convo
    if state.get("context"):
        packet = _context_packet(state["context"], state.get("current_user"))
        convo = f"Context JSON:\n{json.dumps(packet, ensure_ascii=True, separators=(',', ':'))}\n" + convo
    try:
        raw = _safe_call(system, convo, trace=trace if trace_enabled else None, trace_label="agent_step")
    except concurrent.futures.TimeoutError:
        updates["response"] = "AI request timed out. Try again."
        updates["last_error"] = "timeout"
        updates["requires_approval"] = False
        updates["request_type"] = None
        updates["output"] = None
        if trace_enabled:
            trace.append(
                {
                    "type": "error",
                    "stage": "agent_step",
                    "error": "timeout",
                    "time": datetime.now(timezone.utc).isoformat(),
                }
            )
            updates["trace"] = trace
        return updates
    except GenAIConfigError as exc:
        updates["response"] = f"AI unavailable: {exc}"
        updates["last_error"] = "config_error"
        updates["requires_approval"] = False
        updates["request_type"] = None
        updates["output"] = None
        if trace_enabled:
            trace.append(
                {
                    "type": "error",
                    "stage": "agent_step",
                    "error": str(exc),
                    "time": datetime.now(timezone.utc).isoformat(),
                }
            )
            updates["trace"] = trace
        return updates

    data = _parse_json(raw)
    if data is None:
        repaired = _repair_json(raw, trace=trace if trace_enabled else None)
        data = _parse_json(repaired or "")
    if data is None:
        updates["response"] = "AI returned invalid JSON. Please try again."
        updates["last_error"] = "invalid_json"
        updates["requires_approval"] = False
        updates["request_type"] = None
        updates["output"] = None
        if trace_enabled:
            trace.append(
                {
                    "type": "error",
                    "stage": "agent_step",
                    "error": "invalid_json",
                    "raw": raw,
                    "time": datetime.now(timezone.utc).isoformat(),
                }
            )
            updates["trace"] = trace
        return updates

    action = _normalize_action(data.get("action"))
    if action == "tool":
        tool_name = data.get("tool")
        args = data.get("args", {}) if isinstance(data.get("args", {}), dict) else {}
        updates["pending_tool"] = {"tool": tool_name, "args": args}
        updates["response"] = None
        updates["requires_approval"] = False
        updates["request_type"] = None
        updates["output"] = None
        if trace_enabled:
            trace.append(
                {
                    "type": "action",
                    "action": "tool",
                    "tool": tool_name,
                    "args": args,
                    "time": datetime.now(timezone.utc).isoformat(),
                }
            )
            updates["trace"] = trace
        return updates

    if action in {"final", "ask"}:
        output = data.get("output")
        reply = data.get("reply") or ""
        if not reply and output:
            reply = output if isinstance(output, str) else json.dumps(output)
        updates["response"] = reply
        if action == "final":
            updates["requires_approval"] = bool(data.get("requires_approval"))
            updates["request_type"] = data.get("request_type")
            updates["output"] = output
        else:
            updates["requires_approval"] = False
            updates["request_type"] = None
            updates["output"] = None
            updates["awaiting_user"] = True
        if trace_enabled:
            trace.append(
                {
                    "type": "action",
                    "action": action,
                    "reply": reply,
                    "requires_approval": updates.get("requires_approval"),
                    "request_type": updates.get("request_type"),
                    "time": datetime.now(timezone.utc).isoformat(),
                }
            )
            updates["trace"] = trace
        return updates

    updates["response"] = "AI returned an invalid action. Please try again."
    updates["last_error"] = "invalid_action"
    updates["requires_approval"] = False
    updates["request_type"] = None
    updates["output"] = None
    if trace_enabled:
        trace.append(
            {
                "type": "error",
                "stage": "agent_step",
                "error": "invalid_action",
                "raw": raw,
                "time": datetime.now(timezone.utc).isoformat(),
            }
        )
        updates["trace"] = trace
    return updates


def _route_next(state: AgentState) -> str:
    if state.get("halt"):
        return END
    if state.get("pending_tool"):
        return "tool"
    return END


def _trace_policy_violations(trace: List[Dict[str, Any]]) -> List[str]:
    if not trace:
        return []
    tool_calls = [t for t in trace if t.get("type") == "tool"]
    tools = [t.get("tool") for t in tool_calls]
    violations: List[str] = []

    if "apply_draft" in tools and "validate_draft" not in tools:
        violations.append("write_without_validation")
    if "verify_write" in tools and "apply_draft" not in tools:
        violations.append("verify_without_apply")
    if "apply_draft" in tools and "verify_write" not in tools:
        violations.append("missing_read_after_write")

    if "apply_draft" in tools or "validate_draft" in tools:
        if "read_entity_index" not in tools:
            violations.append("missing_entity_index_before_write")

    if ("validate_draft" in tools or "apply_draft" in tools or "verify_write" in tools) and (
        "read_context" in tools or "read_context_complete" in tools
    ):
        violations.append("query_only_context_used_in_write_flow")

    return violations


def _query_telemetry(result: AgentState) -> Dict[str, Any]:
    tool_calls = int(result.get("tool_calls") or 0)
    context_calls = int(result.get("context_calls") or 0)
    bytes_returned = int(result.get("metric_bytes_returned") or 0)
    tokens_returned = int(result.get("metric_tokens_returned") or 0)
    bytes_sent = int(result.get("metric_bytes_sent") or 0)
    tokens_sent = int(result.get("metric_tokens_sent") or 0)
    cache_hits = int(result.get("metric_cache_hits") or 0)
    drilldowns = int(result.get("metric_drilldowns") or 0)
    return {
        "tool_calls_count": tool_calls,
        "context_calls_count": context_calls,
        "bytes_returned": bytes_returned,
        "approx_tokens_returned": tokens_returned,
        "bytes_sent": bytes_sent,
        "approx_tokens_sent": tokens_sent,
        "cache_hit_rate": (cache_hits / tool_calls) if tool_calls else None,
        "drilldown_rate": (drilldowns / tool_calls) if tool_calls else None,
    }


def _coerce_messages(raw_messages: List[Any]) -> List[BaseMessage]:
    messages: List[BaseMessage] = []
    for msg in raw_messages:
        if isinstance(msg, BaseMessage):
            messages.append(msg)
            continue
        if isinstance(msg, dict):
            messages.append(_message_from_role(msg.get("role"), str(msg.get("content") or "")))
            continue
        role = getattr(msg, "role", None)
        content = getattr(msg, "content", None)
        if role or content:
            messages.append(_message_from_role(role, str(content or "")))
        else:
            messages.append(HumanMessage(content=str(msg)))
    return messages


FOLLOWUP_APPEND_SYSTEM_PROMPT = (
    "You are a strict JSON assistant.\n"
    "Return JSON only with schema: {\"append\": \"...\"}.\n"
)

EXTRACT_REFERENCES_SYSTEM_PROMPT = (
    "You are a strict JSON extractor.\n"
    "Return JSON only with optional keys: project_name, solution_name.\n"
)


def _looks_like_new_request(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if _infer_direct_draft_tool(text):
        return True
    lower = text.lower()
    return lower.startswith(
        (
            "create ",
            "new ",
            "add ",
            "update ",
            "change ",
            "edit ",
            "draft ",
            "list ",
            "show ",
        )
    )


def _fallback_followup_append(question: str, answer: str) -> str:
    q = (question or "").lower()
    a = (answer or "").strip()
    if not a:
        return ""
    if "project" in q:
        return f"Project: {a}"
    if "solution" in q:
        return f"Solution: {a}"
    if "priority" in q:
        return f"Priority: {a}"
    if "status" in q:
        return f"Status: {a}"
    return f"Answer: {a}"


def _is_defaultish_answer(answer: str) -> bool:
    lower = (answer or "").strip().lower()
    if not lower:
        return False
    tokens = (
        "default",
        "keep the default",
        "keep default",
        "same as before",
        "same as previous",
        "unchanged",
    )
    return any(t in lower for t in tokens)


def _followup_append_line(
    instruction: str,
    question: str,
    answer: str,
    trace: Optional[List[Dict[str, Any]]] = None,
    current_user: Optional[Dict[str, Any]] = None,
) -> tuple[str, bool]:
    """Use a small LLM call to convert (question, answer) into a labeled line to append to instruction."""
    preamble = _run_context_preamble(current_user)
    user_prompt = preamble + render_prompt(
        "agent/followup_append.md",
        instruction=instruction,
        question=question,
        answer=answer,
    )
    raw = _safe_call(
        FOLLOWUP_APPEND_SYSTEM_PROMPT,
        user_prompt,
        trace=trace,
        trace_label="followup_append",
    )
    parsed = _parse_json(raw)
    if isinstance(parsed, dict) and "append" in parsed:
        append = parsed.get("append")
        if isinstance(append, str):
            return append.strip().replace("\n", " ").strip(), True
        return "", True
    return "", False

def _extract_references_from_instruction_llm(
    instruction: str,
    trace: Optional[List[Dict[str, Any]]] = None,
    current_user: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Best-effort LLM extraction for entity references (project/solution) from a free-form instruction."""
    if not instruction or not instruction.strip():
        return {}
    preamble = _run_context_preamble(current_user)
    user_prompt = preamble + render_prompt(
        "agent/extract_references.md",
        instruction=instruction.strip(),
    )
    raw = _safe_call(
        EXTRACT_REFERENCES_SYSTEM_PROMPT,
        user_prompt,
        trace=trace,
        trace_label="extract_references",
    )
    parsed = _parse_json(raw)
    if not isinstance(parsed, dict):
        return {}
    refs: Dict[str, str] = {}
    for key in ("project_name", "solution_name"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            refs[key] = value.strip()
    return refs

def _find_base_instruction_from_history(history: List[Any]) -> str:
    """Pick the base instruction for a follow-up thread (usually the first 'real' user request)."""
    if not history:
        return ""
    # Prefer the earliest user message that looks like an actual request.
    for msg in history:
        if _message_role(msg) != "user":
            continue
        content = _message_content(msg).strip()
        if content and _looks_like_new_request(content):
            return content
    # Fall back to the first user message.
    for msg in history:
        if _message_role(msg) == "user":
            return _message_content(msg).strip()
    return ""


def run_agentic_chat(session, payload) -> Dict[str, Any]:
    max_steps = int(os.getenv("AI_MAX_STEPS", "30"))
    trace_enabled = str(os.getenv("AI_DEBUG_TRACE", "")).strip().lower() in {"1", "true", "yes", "on"}
    start_s = time.monotonic()
    wall_timeout_s = int(os.getenv("AI_WALL_TIMEOUT_SECONDS", os.getenv("AI_MODEL_TIMEOUT_SECONDS", "60")))

    raw_history = payload.get("history") or []
    raw_message = payload.get("message", "")
    trace: List[Dict[str, Any]] = []

    # Follow-up handling: when the user answers a clarifying question, rebuild a single "instruction"
    # string by appending a labeled line derived from (question, answer), then re-run the normal flow.
    # This keeps each action isolated and prevents the assistant from losing the original instruction.
    effective_history = raw_history
    effective_message = raw_message
    question = (_latest_assistant_message(raw_history) or "").strip()
    if question and question.endswith("?") and (not _looks_like_new_request(raw_message)):
        base_instruction = _find_base_instruction_from_history(raw_history)
        answer = (raw_message or "").strip()
        if base_instruction and answer:
            # Build a consolidated instruction that includes prior clarifying answers (if present).
            consolidated_lines = [base_instruction]
            pending_question: Optional[str] = None
            for msg in raw_history:
                role = _message_role(msg)
                content = _message_content(msg).strip()
                if not content:
                    continue
                if role == "assistant":
                    pending_question = content
                    continue
                if role != "user":
                    continue
                # Skip the base instruction itself.
                if content == base_instruction:
                    continue
                # If the user starts a new request mid-thread, stop accumulating.
                if _looks_like_new_request(content):
                    pending_question = None
                    break
                if pending_question:
                    append = ""
                    explicit = False
                    try:
                        append, explicit = _followup_append_line(
                            base_instruction,
                            pending_question,
                            content,
                            trace=trace if trace_enabled else None,
                            current_user=payload.get("current_user"),
                        )
                    except Exception:
                        append = ""
                        explicit = False
                    if (not explicit) and (not append) and (not _is_defaultish_answer(content)):
                        append = _fallback_followup_append(pending_question, content)
                    if append:
                        consolidated_lines.append(append)
                    pending_question = None

            # Append the current (question, answer) pair.
            append = ""
            explicit = False
            try:
                append, explicit = _followup_append_line(
                    base_instruction,
                    question,
                    answer,
                    trace=trace if trace_enabled else None,
                    current_user=payload.get("current_user"),
                )
            except Exception:
                append = ""
                explicit = False
            if (not explicit) and (not append) and (not _is_defaultish_answer(answer)):
                append = _fallback_followup_append(question, answer)
            if append:
                consolidated_lines.append(append)

            effective_message = "\n".join(consolidated_lines)
            effective_history = []

    messages = _coerce_messages(effective_history)
    messages.append(_message_from_role("user", effective_message))

    state: AgentState = {
        "messages": messages,
        "entity_type": payload.get("entity_type"),
        "entity_id": payload.get("entity_id"),
        "project_id": payload.get("project_id"),
        "space_id": payload.get("space_id"),
        "current_date": payload.get("current_date"),
        "current_user": payload.get("current_user"),
        "context": {"contracts": contract_hints()},
        "requires_approval": False,
        "pending_tool": None,
        "awaiting_user": False,
        "halt": False,
        "last_tool_signature": None,
        "last_tool_repeats": 0,
        "tool_calls": 0,
        "context_calls": 0,
        "tool_history": [],
        "queued_tool": None,
        "max_steps": max_steps,
        "trace_enabled": trace_enabled,
        "trace": trace,
        "steps": 0,
        "last_validation": None,
        "deadline_s": start_s + wall_timeout_s,
        "metric_bytes_sent": 0,
        "metric_tokens_sent": 0,
        "metric_bytes_returned": 0,
        "metric_tokens_returned": 0,
        "metric_cache_hits": 0,
        "metric_drilldowns": 0,
    }

    # Note: We intentionally do not route directly to a draft tool here.
    # The agent step must interpret the request first (LLM-first), then decide which tool to call.

    graph = StateGraph(AgentState)
    graph.add_node("agent", _agent_step)
    graph.add_node("tool", lambda s: _tool_dispatch(s, session))
    graph.add_conditional_edges("agent", _route_next, {"tool": "tool", END: END})
    graph.add_edge("tool", "agent")
    graph.set_entry_point("agent")
    executor = graph.compile()

    logger.info("ai.chat start message_len=%s", len(effective_message or ""))
    try:
        result = executor.invoke(state, {"recursion_limit": max_steps * 2})
    except Exception as exc:
        result = state
        result["response"] = f"AI failed to complete the request: {exc}"
    finally:
        elapsed = time.monotonic() - start_s
        logger.info("ai.chat end elapsed_s=%.2f", elapsed)

    if not result.get("response"):
        fallback = _fallback_empty_response(result)
        if fallback:
            result["response"] = fallback
            if not result.get("requires_approval"):
                result["awaiting_user"] = True
        else:
            result["response"] = "AI did not return a usable response. Please try again."

    resolved_entity_type = result.get("entity_type") or payload.get("entity_type")
    resolved_entity_id = result.get("entity_id") or payload.get("entity_id")
    if result.get("request_type") == "solution_create" and result.get("project_id"):
        resolved_entity_type = "project"
        resolved_entity_id = result.get("project_id")

    response = {
        "reply": result.get("response") or "",
        "requires_approval": bool(result.get("requires_approval")),
        "request_type": result.get("request_type"),
        "entity_type": resolved_entity_type,
        "entity_id": resolved_entity_id,
        "output": json.dumps(result.get("output")) if isinstance(result.get("output"), dict) else result.get("output"),
    }
    reply_text = response.get("reply") or ""
    if not reply_text:
        candidate = response.get("output")
        if isinstance(candidate, str):
            reply_text = candidate
    requires_approval = bool(response.get("requires_approval"))
    awaiting_user = bool(result.get("awaiting_user"))
    if not awaiting_user and (not requires_approval) and reply_text.strip().endswith("?"):
        awaiting_user = True
    if requires_approval:
        next_action = "approve_or_discard"
    elif awaiting_user:
        next_action = "answer_question"
    else:
        next_action = "done"
    response["next_action"] = next_action
    query_metrics = _query_telemetry(result)
    logger.info(
        "ai.chat metrics tool_calls=%s context_calls=%s bytes_out=%s cache_hit_rate=%s drilldown_rate=%s",
        query_metrics.get("tool_calls_count"),
        query_metrics.get("context_calls_count"),
        query_metrics.get("bytes_returned"),
        query_metrics.get("cache_hit_rate"),
        query_metrics.get("drilldown_rate"),
    )
    try:
        user = payload.get("current_user") or {}
        log_query_metric(
            session,
            session_id=payload.get("session_id"),
            space_id=payload.get("space_id"),
            user_id=user.get("user_id"),
            project_id=(result.get("project_id") or payload.get("project_id")),
            entity_type=resolved_entity_type,
            entity_id=resolved_entity_id,
            tool_calls_count=query_metrics.get("tool_calls_count") or 0,
            context_calls_count=query_metrics.get("context_calls_count") or 0,
            bytes_returned=query_metrics.get("bytes_returned") or 0,
            approx_tokens_returned=query_metrics.get("approx_tokens_returned") or 0,
            bytes_sent=query_metrics.get("bytes_sent") or 0,
            approx_tokens_sent=query_metrics.get("approx_tokens_sent") or 0,
            cache_hit_rate=query_metrics.get("cache_hit_rate"),
            drilldown_rate=query_metrics.get("drilldown_rate"),
            answer_quality_score=None,
        )
        session.flush()
    except Exception:
        logger.exception("ai.chat metrics persistence failed")
    if trace_enabled:
        response["debug"] = {
            "trace": result.get("trace") or [],
            "steps": result.get("steps"),
            "last_error": result.get("last_error"),
            "user_visible_reply": reply_text,
            "requires_approval": requires_approval,
            "request_type": response.get("request_type"),
            "next_action": next_action,
            "policy_violations": _trace_policy_violations(result.get("trace") or []),
            "metrics": query_metrics,
        }
    return response
