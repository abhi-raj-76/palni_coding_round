import json
import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)

# If OLLAMA_MODEL is missing locally, `resolve_model_if_needed` sets this to the first installed name.
_model_override: str | None = None


def _active_model() -> str:
    return _model_override if _model_override is not None else settings.ollama_model


async def resolve_model_if_needed() -> None:
    """If OLLAMA_MODEL is not installed, use the first model from `ollama list`."""
    global _model_override
    base = settings.ollama_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{base}/api/tags")
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        log.warning("Could not reach Ollama at %s (%s). Is `ollama serve` running?", base, e)
        return

    names = [m.get("name") for m in data.get("models", []) if m.get("name")]
    if not names:
        log.warning("Ollama at %s returned no models. Run `ollama pull <model>`.", base)
        return
    if settings.ollama_model in names:
        return
    chosen = names[0]
    log.warning(
        "OLLAMA_MODEL %r is not installed. Using %r instead. Update .env or run `ollama pull %s`.",
        settings.ollama_model,
        chosen,
        settings.ollama_model,
    )
    _model_override = chosen


async def chat_completion(system: str, user: str, json_mode: bool = False) -> str:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload: dict[str, Any] = {
        "model": _active_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        body = (e.response.text or "")[:500]
        if e.response.status_code == 404 and "not found" in body.lower():
            raise RuntimeError(
                f"Ollama model {_active_model()!r} not found. "
                f"Set OLLAMA_MODEL to a name from `ollama list`, or run "
                f"`ollama pull {_active_model()}` or set OLLAMA_MODEL. Server said: {body}"
            ) from e
        raise RuntimeError(f"Ollama HTTP {e.response.status_code}: {body}") from e
    except httpx.RequestError as e:
        raise RuntimeError(
            f"Cannot reach Ollama at {settings.ollama_base_url!r}. "
            f"Start the Ollama app or `ollama serve`. ({e})"
        ) from e

    msg = data.get("message") or {}
    content = msg.get("content", "")
    if not content and isinstance(data.get("response"), str):
        content = data["response"]
    return content.strip()


def parse_json_loose(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise
