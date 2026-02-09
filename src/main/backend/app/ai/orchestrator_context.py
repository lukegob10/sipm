from __future__ import annotations

from typing import Any, Dict, List, Optional


def message_role(message: Any) -> str:
    if isinstance(message, dict):
        role = str(message.get("role") or "user").strip().lower()
        if role in {"user", "human"}:
            return "user"
        if role in {"assistant", "ai"}:
            return "assistant"
        if role in {"tool", "system"}:
            return role
        return role or "user"
    if hasattr(message, "type"):
        msg_type = str(getattr(message, "type", "") or "")
        if msg_type == "human":
            return "user"
        if msg_type == "ai":
            return "assistant"
        if msg_type == "tool":
            return "tool"
        if msg_type == "system":
            return "system"
        if msg_type == "chat":
            return getattr(message, "role", "user") or "user"
        return msg_type or "user"
    return getattr(message, "role", "user") or "user"


def message_content(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("content") or "")
    if hasattr(message, "content"):
        return str(getattr(message, "content", "") or "")
    return str(getattr(message, "content", "") or "")


def latest_user_message(messages: List[Any]) -> str:
    for msg in reversed(messages or []):
        if message_role(msg) == "user":
            return message_content(msg)
    return ""


def resolved_entity_label(state: Dict[str, Any]) -> Optional[str]:
    context = state.get("context")
    if not isinstance(context, dict):
        return None
    entity_type = str(state.get("entity_type") or "").strip().lower()
    if entity_type == "project":
        project = context.get("project")
        if isinstance(project, dict):
            label = project.get("project_name")
            if isinstance(label, str) and label.strip():
                return label.strip()
    if entity_type == "solution":
        solution = context.get("solution")
        if isinstance(solution, dict):
            label = solution.get("solution_name")
            if isinstance(label, str) and label.strip():
                return label.strip()
    if entity_type == "subcomponent":
        subcomponent = context.get("subcomponent")
        if isinstance(subcomponent, dict):
            label = subcomponent.get("subcomponent_name")
            if isinstance(label, str) and label.strip():
                return label.strip()
    return None


def fallback_empty_response(state: Dict[str, Any]) -> Optional[str]:
    entity_type = str(state.get("entity_type") or "").strip().lower()
    if entity_type not in {"project", "solution", "subcomponent"}:
        return None
    label = resolved_entity_label(state)
    if label:
        return f"I selected {entity_type} '{label}'. What would you like to do next?"
    if state.get("entity_id"):
        return f"I selected that {entity_type}. What would you like to do next?"
    return None


def compact_for_prompt(
    value: Any,
    *,
    max_depth: int = 3,
    max_items: int = 8,
    max_chars: int = 240,
) -> Any:
    if value is None:
        return None
    if max_depth <= 0:
        return "..."
    if isinstance(value, str):
        if len(value) <= max_chars:
            return value
        return value[: max_chars - 3] + "..."
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, list):
        trimmed = [
            compact_for_prompt(item, max_depth=max_depth - 1, max_items=max_items, max_chars=max_chars)
            for item in value[:max_items]
        ]
        if len(value) > max_items:
            trimmed.append({"_truncated_items": len(value) - max_items})
        return trimmed
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        keys = list(value.keys())
        for idx, key in enumerate(keys):
            if idx >= max_items:
                out["_truncated_keys"] = len(keys) - max_items
                break
            out[str(key)] = compact_for_prompt(
                value.get(key),
                max_depth=max_depth - 1,
                max_items=max_items,
                max_chars=max_chars,
            )
        return out
    return str(value)


def compact_contract_hints_payload(contracts: Dict[str, Any]) -> Dict[str, Any]:
    compact: Dict[str, Any] = {}
    for entity_type, meta in (contracts or {}).items():
        if not isinstance(meta, dict):
            continue
        fields_meta = meta.get("fields")
        field_names = list(fields_meta.keys()) if isinstance(fields_meta, dict) else []
        constraints = meta.get("constraints") if isinstance(meta.get("constraints"), dict) else {}
        enum_fields = [name for name, rules in constraints.items() if isinstance(rules, dict) and rules.get("enum")]
        compact[entity_type] = {
            "required": list(meta.get("required") or [])[:12],
            "fields": field_names[:20],
            "enum_fields": enum_fields[:12],
        }
    return compact


def compact_history(messages: List[Any], limit: int = 10) -> str:
    tail = messages[-limit:] if len(messages) > limit else messages
    normalized = []
    for msg in tail:
        role = message_role(msg)
        content = message_content(msg)
        if len(content) > 1200:
            content = content[:1197] + "..."
        normalized.append({"role": role, "content": content})
    return "\n".join([f"{m['role']}: {m['content']}" for m in normalized])


def context_packet(context: Dict[str, Any], current_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if context.get("context_mode") == "complete":
        packet = compact_for_prompt(context, max_depth=3, max_items=8, max_chars=200)
        if not isinstance(packet, dict):
            packet = {"context": packet}
        if current_user:
            name = (current_user.get("display_name") or "").strip()
            soeid = (current_user.get("soeid") or "").strip()
            if name or soeid:
                packet["current_user"] = {"display_name": name or None, "soeid": soeid or None}
        return packet
    packet: Dict[str, Any] = {}
    if current_user:
        name = (current_user.get("display_name") or "").strip()
        soeid = (current_user.get("soeid") or "").strip()
        if name or soeid:
            packet["current_user"] = {"display_name": name or None, "soeid": soeid or None}
    if context.get("project"):
        p = context["project"]
        packet["project"] = {
            "project_id": p.get("project_id"),
            "project_name": p.get("project_name"),
            "status": p.get("status"),
            "priority": p.get("priority"),
            "sponsor": p.get("sponsor"),
        }
    if context.get("solution"):
        s = context["solution"]
        packet["solution"] = {
            "solution_id": s.get("solution_id"),
            "solution_name": s.get("solution_name"),
            "status": s.get("status"),
            "rag_status": s.get("rag_status"),
            "current_phase": s.get("current_phase"),
            "due_date": s.get("due_date"),
            "priority": s.get("priority"),
        }
    if context.get("subcomponent"):
        sc = context["subcomponent"]
        packet["subcomponent"] = {
            "subcomponent_id": sc.get("subcomponent_id"),
            "subcomponent_name": sc.get("subcomponent_name"),
            "status": sc.get("status"),
            "due_date": sc.get("due_date"),
            "priority": sc.get("priority"),
            "blocked": sc.get("blocked"),
        }
    if context.get("solutions"):
        packet["solutions"] = [
            {
                "solution_id": s.get("solution_id"),
                "solution_name": s.get("solution_name"),
                "status": s.get("status"),
                "current_phase": s.get("current_phase"),
                "due_date": s.get("due_date"),
            }
            for s in context.get("solutions", [])[:10]
        ]
    if context.get("subcomponents"):
        packet["subcomponents"] = [
            {
                "subcomponent_id": sc.get("subcomponent_id"),
                "subcomponent_name": sc.get("subcomponent_name"),
                "status": sc.get("status"),
                "due_date": sc.get("due_date"),
            }
            for sc in context.get("subcomponents", [])[:10]
        ]
    if context.get("project_charter"):
        packet["project_charter"] = context.get("project_charter")
    if context.get("project_plan"):
        packet["project_plan"] = context.get("project_plan")
    if context.get("project_decision_log"):
        packet["project_decision_log"] = context.get("project_decision_log")
    if context.get("sow_documents"):
        packet["sow_documents"] = context.get("sow_documents", [])[:2]
    if context.get("latest_sow"):
        packet["latest_sow"] = context.get("latest_sow")
    if context.get("solution_sow_documents"):
        packet["solution_sow_documents"] = compact_for_prompt(context.get("solution_sow_documents", [])[:2], max_depth=2)
    if context.get("phases"):
        packet["phases"] = [p.get("phase_name") for p in context.get("phases", []) if p.get("phase_name")][:20]
    if context.get("dropdowns"):
        packet["dropdowns"] = compact_for_prompt(context.get("dropdowns"), max_depth=2, max_items=6, max_chars=64)
    if context.get("scope_digest"):
        packet["scope_digest"] = compact_for_prompt(context.get("scope_digest"), max_depth=3, max_items=8, max_chars=180)
    if context.get("project_cards"):
        packet["project_cards"] = compact_for_prompt(context.get("project_cards"), max_depth=3, max_items=8, max_chars=160)
    if context.get("solution_cards"):
        packet["solution_cards"] = compact_for_prompt(context.get("solution_cards"), max_depth=3, max_items=8, max_chars=160)
    if context.get("task_cards"):
        packet["task_cards"] = compact_for_prompt(context.get("task_cards"), max_depth=3, max_items=8, max_chars=160)
    if context.get("entity_fields"):
        packet["entity_fields"] = compact_for_prompt(context.get("entity_fields"), max_depth=3, max_items=10, max_chars=160)
    if context.get("entity_deltas"):
        packet["entity_deltas"] = compact_for_prompt(context.get("entity_deltas"), max_depth=3, max_items=10, max_chars=160)
    if context.get("usage_guide"):
        guide = context.get("usage_guide") or {}
        packet["usage_guide"] = {
            "query": guide.get("query"),
            "retrieval": guide.get("retrieval"),
            "source": guide.get("source"),
            "assistant_instruction": guide.get("assistant_instruction"),
            "sections": compact_for_prompt(guide.get("sections"), max_depth=4, max_items=8, max_chars=2200),
            "guide_context": compact_for_prompt(guide.get("guide_context"), max_depth=1, max_items=1, max_chars=14000),
        }
    if context.get("contracts"):
        packet["contracts"] = compact_contract_hints_payload(context.get("contracts") or {})
    return packet


def latest_assistant_message(messages: List[Any]) -> str:
    for msg in reversed(messages or []):
        if message_role(msg) == "assistant":
            return message_content(msg)
    return ""


def prior_user_message_before_last_assistant(messages: List[Any]) -> str:
    if not messages:
        return ""
    last_ai_idx = None
    for idx in range(len(messages) - 1, -1, -1):
        if message_role(messages[idx]) == "assistant":
            last_ai_idx = idx
            break
    if last_ai_idx is None:
        return ""
    for idx in range(last_ai_idx - 1, -1, -1):
        if message_role(messages[idx]) == "user":
            return message_content(messages[idx])
    return ""
