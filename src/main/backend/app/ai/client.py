from __future__ import annotations

import os
from typing import Optional

from .errors import GenAIConfigError

_CACHED_CLIENT: Optional[object] = None


def get_client() -> object:
    """
    Return a cached Google GenAI client.

    This file intentionally exposes a single seam (`get_client`) so it can be
    replaced wholesale without requiring changes in the rest of the AI stack.
    """
    global _CACHED_CLIENT

    if _CACHED_CLIENT is not None:
        return _CACHED_CLIENT

    try:
        from google import genai  # type: ignore
    except Exception as exc:  # pragma: no cover - import depends on runtime env
        raise GenAIConfigError("google-genai package is not available") from exc

    # Canonical configuration names (single source of truth):
    # - GENAI_API_KEY
    # - GENAI_USE_VERTEXAI
    # - GENAI_PROJECT
    # - GENAI_LOCATION
    api_key = (os.getenv("GENAI_API_KEY") or "").strip()
    use_vertex = str(os.getenv("GENAI_USE_VERTEXAI") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    project = (os.getenv("GENAI_PROJECT") or "").strip()
    location = (os.getenv("GENAI_LOCATION") or "us-central1").strip()

    try:
        if use_vertex or (project and not api_key):
            if not project:
                raise GenAIConfigError("Vertex mode requires GENAI_PROJECT.")
            _CACHED_CLIENT = genai.Client(vertexai=True, project=project, location=location)
        elif api_key:
            _CACHED_CLIENT = genai.Client(api_key=api_key, vertexai=False)
        else:
            _CACHED_CLIENT = genai.Client()
    except GenAIConfigError:
        raise
    except Exception as exc:  # pragma: no cover - runtime auth/config errors
        raise GenAIConfigError(f"Failed to initialize genai.Client: {exc}") from exc

    return _CACHED_CLIENT
