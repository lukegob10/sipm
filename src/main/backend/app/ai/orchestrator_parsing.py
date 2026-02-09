from __future__ import annotations

import json
from typing import Any, Dict, Optional


def extract_json_object(text: str) -> Optional[str]:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        pass
    extracted = extract_json_object(text)
    if not extracted:
        return None
    try:
        data = json.loads(extracted)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def normalize_action(action: Optional[str]) -> str:
    return (action or "").strip().lower()
