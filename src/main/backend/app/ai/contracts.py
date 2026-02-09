from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional


def _find_contracts_dir() -> Path:
    env = os.getenv("SIPM_CONTRACTS_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "prompts" / "contracts"
        if candidate.exists() and candidate.is_dir():
            return candidate
    return here.parent / "contracts"


@lru_cache(maxsize=1)
def load_contracts() -> Dict[str, Dict[str, Any]]:
    base = _find_contracts_dir()
    contracts: Dict[str, Dict[str, Any]] = {}
    if not base.exists():
        return contracts
    for path in base.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        entity = str(data.get("entity") or path.stem)
        contracts[entity] = data
    return contracts


def get_contract(entity_type: str) -> Optional[Dict[str, Any]]:
    return load_contracts().get(entity_type)


def contract_hints() -> Dict[str, Any]:
    contracts = load_contracts()
    hints: Dict[str, Any] = {}
    for key, contract in contracts.items():
        fields = contract.get("fields", {})
        hints[key] = {
            "required": contract.get("required", []),
            "optional": contract.get("optional", []),
            "constraints": contract.get("constraints", {}),
            "fields": {name: {
                "type": meta.get("type"),
                "enum": meta.get("enum"),
                "read_only": bool(meta.get("read_only")),
                # Defaults and basic validation hints help the LLM avoid unnecessary clarifying questions.
                "default": meta.get("default"),
                "min": meta.get("min"),
                "max": meta.get("max"),
                "description": meta.get("description"),
            } for name, meta in fields.items()},
            "relationships": contract.get("relationships", {}),
        }
    return hints
