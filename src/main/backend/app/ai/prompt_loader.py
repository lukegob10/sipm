from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict


def _find_prompts_dir() -> Path:
    env = os.getenv("SIPM_PROMPTS_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "prompts"
        if candidate.exists() and candidate.is_dir():
            return candidate
    return here.parent / "prompts"


@lru_cache(maxsize=128)
def load_prompt(relative_path: str) -> str:
    base = _find_prompts_dir()
    path = base / relative_path
    return path.read_text(encoding="utf-8")


def render_prompt(relative_path: str, **kwargs: Dict[str, str]) -> str:
    template = load_prompt(relative_path)
    if not kwargs:
        return template
    # Prompts often include JSON examples and other brace-heavy content that is not
    # meant to be interpreted by `str.format`. Using `.format` can raise KeyError
    # (e.g. when a JSON example contains `{ "month": ... }`) and crash request
    # handling. Instead, do a conservative placeholder substitution:
    # - Replace only exact `{key}` occurrences for provided keys.
    # - Support `{{` / `}}` escapes (converted to literal braces) for backward compatibility.
    sentinel_l = "\0PROMPT_LBRACE\0"
    sentinel_r = "\0PROMPT_RBRACE\0"
    out = template.replace("{{", sentinel_l).replace("}}", sentinel_r)
    for key, value in kwargs.items():
        out = out.replace("{" + str(key) + "}", str(value))
    return out.replace(sentinel_l, "{").replace(sentinel_r, "}")
