import logging
import os
from typing import Any, Dict, List, Optional

from .client import get_client
from .errors import GenAIConfigError

logger = logging.getLogger(__name__)

_MODEL_ENV_NAME = "GENAI_MODEL"
_DEFAULT_MODEL = "gemini-2.5-flash"


def _is_enabled(env_name: str) -> bool:
    return str(os.getenv(env_name, "")).strip().lower() in {"1", "true", "yes", "on"}


def _debug_enabled() -> bool:
    return _is_enabled("GENAI_DEBUG")


def _trace_enabled() -> bool:
    return _is_enabled("AI_DEBUG_TRACE")


def resolve_model_with_source(default: Optional[str] = None) -> tuple[str, str]:
    fallback = (default or _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
    value = (os.getenv(_MODEL_ENV_NAME) or "").strip()
    if value:
        return value, _MODEL_ENV_NAME
    return fallback, "default"


def config_diagnostics() -> str:
    model, model_source = resolve_model_with_source()
    return ", ".join(
        [
            f"model={model}",
            f"model_from={model_source}",
            f"trace_enabled={'true' if _trace_enabled() else 'false'}",
        ]
    )


def _extract_text_from_parts(parts: Any) -> Optional[str]:
    if not isinstance(parts, list):
        return None
    chunks: List[str] = []
    for part in parts:
        if isinstance(part, str):
            token = part.strip()
            if token:
                chunks.append(token)
            continue
        if isinstance(part, dict):
            token = part.get("text")
            if isinstance(token, str) and token.strip():
                chunks.append(token.strip())
    if chunks:
        return "\n".join(chunks)
    return None


def _extract_text_from_dict(payload: Dict[str, Any]) -> Optional[str]:
    # Generic direct keys used by adapter wrappers.
    for key in ("content", "message", "text", "output_text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, dict):
            nested = _extract_text_from_dict(value)
            if nested:
                return nested
        extracted_parts = _extract_text_from_parts(value)
        if extracted_parts:
            return extracted_parts

    # OpenAI-compatible shape: choices[0].message.content or choices[0].text
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content
                if isinstance(content, list):
                    extracted = _extract_text_from_parts(content)
                    if extracted:
                        return extracted
            text = first.get("text")
            if isinstance(text, str) and text.strip():
                return text

    # Gemini-compatible shape: candidates[0].content.parts[*].text
    candidates = payload.get("candidates")
    if isinstance(candidates, list) and candidates:
        first = candidates[0]
        if isinstance(first, dict):
            content = first.get("content")
            if isinstance(content, dict):
                extracted = _extract_text_from_parts(content.get("parts"))
                if extracted:
                    return extracted
            text = first.get("text")
            if isinstance(text, str) and text.strip():
                return text

    return None


def _extract_text_from_response(response: Any) -> Optional[str]:
    if isinstance(response, str):
        text = response.strip()
        return text or None
    if isinstance(response, dict):
        return _extract_text_from_dict(response)

    # Object responses from SDKs with attribute-based access.
    text_attr = getattr(response, "text", None)
    if isinstance(text_attr, str) and text_attr.strip():
        return text_attr

    # Some SDK wrappers expose a `.dict()` method.
    dict_method = getattr(response, "dict", None)
    if callable(dict_method):
        try:
            payload = dict_method()
            if isinstance(payload, dict):
                text = _extract_text_from_dict(payload)
                if text:
                    return text
        except Exception:
            pass

    # Some SDK wrappers expose `.model_dump()` (pydantic models).
    model_dump = getattr(response, "model_dump", None)
    if callable(model_dump):
        try:
            payload = model_dump()
            if isinstance(payload, dict):
                text = _extract_text_from_dict(payload)
                if text:
                    return text
        except Exception:
            pass

    return None


def get_genai_client() -> object:
    """Back-compat alias for the cached GenAI client."""
    return get_client()


def build_messages(system_prompt: str, user_prompt: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def call_chat_completion(system_prompt: str, user_prompt: str) -> str:
    client = get_client()
    model, model_source = resolve_model_with_source()
    messages = build_messages(system_prompt, user_prompt)
    models_obj = getattr(client, "models", None)
    has_generate_content = bool(models_obj is not None and hasattr(models_obj, "generate_content"))
    if _trace_enabled():
        logger.info(
            "genai.trace got a real object that works=%s client_type=%s has_models=%s has_generate_content=%s",
            "true" if has_generate_content else "false",
            type(client).__name__,
            "true" if models_obj is not None else "false",
            "true" if has_generate_content else "false",
        )
    if not has_generate_content:
        raise GenAIConfigError("GenAI client is not usable: expected client.models.generate_content(...)")

    if _debug_enabled():
        logger.info(
            "genai.call start model=%s model_source=%s system_chars=%s user_chars=%s",
            model,
            model_source,
            len(system_prompt or ""),
            len(user_prompt or ""),
        )

    try:
        prompt = "\n".join([m["content"] for m in messages])
        response = models_obj.generate_content(model=model, contents=prompt)
        if hasattr(response, "text"):
            if _debug_enabled():
                logger.info("genai.call ok model=%s", model)
            return response.text
        extracted = _extract_text_from_response(response)
        if extracted:
            if _debug_enabled():
                logger.info("genai.call ok model=%s", model)
            return extracted
        if _debug_enabled():
            logger.info("genai.call ok model=%s (no text attr)", model)
        return str(response)
    except GenAIConfigError:
        raise
    except Exception as exc:
        message = str(exc) if exc is not None else ""
        lower = message.lower()
        status_code = getattr(exc, "status_code", None)
        if status_code in {401, 403}:
            detail = message or "Unauthorized"
            raise GenAIConfigError(
                f"GenAI permission error ({status_code}) model={model} source={model_source}: {detail}"
            ) from exc
        if status_code == 400 and any(token in lower for token in ("auth", "credential", "permission")):
            raise GenAIConfigError(
                "GenAI authentication/configuration error. "
                f"({config_diagnostics()}) "
                f"detail={message or 'unknown'}"
            ) from exc
        if "permission_denied" in lower:
            raise GenAIConfigError(f"GenAI permission denied: {message}") from exc
        if any(token in lower for token in ("unauthorized", "not authenticated", "authentication", "credentials")):
            raise GenAIConfigError(f"GenAI authentication error: {message}") from exc

        logger.exception("genai.call failed model=%s", model)
        raise
