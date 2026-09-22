"""LLM provider: Google Gemini (free tier).

Open-stack replacement for the reference project's llm/azure_openai.py. Exposes:
- get_structured_completion(prompt, response_model): JSON-mode extraction parsed
  into a Pydantic model, with a regex fallback (mirrors the reference's robust
  handling of models that don't return clean JSON).
- generate_text(prompt): plain-text answer for the chat endpoint.
"""
from __future__ import annotations

import json
import re
import time
from functools import lru_cache

from pydantic import BaseModel

from config import get_settings

SYSTEM_PREAMBLE = "You are an expert financial analyst."


def _generate_with_retry(model, *args, retries: int = 4, **kwargs):
    """Call generate_content, retrying on free-tier rate limits (429)."""
    from google.api_core.exceptions import ResourceExhausted

    for attempt in range(retries):
        try:
            return model.generate_content(*args, **kwargs)
        except ResourceExhausted as exc:
            if attempt == retries - 1:
                raise
            delay = getattr(exc, "retry_delay", None)
            seconds = getattr(delay, "seconds", 0) or 0
            time.sleep(max(seconds + 1, 2 ** attempt))
    raise RuntimeError("unreachable")


@lru_cache
def _get_model():
    import google.generativeai as genai

    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to your .env file.")
    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(
        settings.gemini_model,
        system_instruction=SYSTEM_PREAMBLE,
    )


def _extract_json(text: str) -> str:
    """Pull the first JSON object out of a model response."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        return fenced.group(1)
    match = re.search(r"\{.*\}", text, re.S)
    return match.group(0) if match else text


def get_structured_completion(
    prompt: str,
    response_model: type[BaseModel],
) -> BaseModel:
    """Generate a response and parse it into `response_model`."""
    import google.generativeai as genai

    model = _get_model()
    response = _generate_with_retry(
        model,
        prompt,
        generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )

    raw = (response.text or "").strip()
    if raw in ("", "null", "None"):
        return response_model.model_construct()

    json_text = _extract_json(raw)
    try:
        return response_model.model_validate_json(json_text)
    except Exception:
        # Last-ditch: coerce a dict then validate, tolerating extra keys.
        data = json.loads(json_text)
        return response_model.model_validate(data)


def generate_text(prompt: str) -> str:
    """Generate a plain-text answer (used by the chat endpoint)."""
    model = _get_model()
    response = _generate_with_retry(model, prompt)
    return (response.text or "").strip()
