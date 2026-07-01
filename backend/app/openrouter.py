"""OpenRouter integration — the enforcement core.

``build_payload`` constructs the *entire* provider request from server-side
constants plus the participant's messages. The browser can influence only the
conversation content; model, max_tokens, temperature, top_p, streaming and the
absence of tools are all fixed here and cannot be overridden.
"""
import httpx

from .config import Settings
from .constants import ALLOWED_CLIENT_ROLES, SYSTEM_PROMPT


class ProviderError(Exception):
    """A provider-side failure mapped to a safe, participant-facing message."""

    def __init__(self, http_status: int, user_message: str, provider_status: int | None = None):
        super().__init__(user_message)
        self.http_status = http_status
        self.user_message = user_message
        self.provider_status = provider_status


def build_payload(client_messages: list[dict], settings: Settings) -> dict:
    """Build the OpenRouter payload with fixed, non-overridable settings.

    Only ``role``/``content`` are copied from client messages, only user/assistant
    roles are accepted, and the list is trimmed to the last N (server-controlled),
    with the fixed system prompt prepended.
    """
    trimmed = client_messages[-settings.MAX_CONTEXT_MESSAGES:]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in trimmed:
        role = m.get("role")
        if role in ALLOWED_CLIENT_ROLES:
            messages.append({"role": role, "content": str(m.get("content", ""))})

    # Every generation setting is fixed server-side. No tools, no plugins, no
    # streaming, no passthrough of arbitrary client keys.
    return {
        "model": settings.OPENROUTER_MODEL,
        "messages": messages,
        "max_tokens": settings.MAX_OUTPUT_TOKENS,
        "temperature": settings.TEMPERATURE,
        "top_p": settings.TOP_P,
        "stream": False,
    }


async def _http_post(url: str, headers: dict, payload: dict, timeout: float) -> httpx.Response:
    """Isolated network call — monkeypatched in tests."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url, headers=headers, json=payload)


async def call_openrouter(payload: dict, settings: Settings) -> dict:
    url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        resp = await _http_post(url, headers, payload, settings.REQUEST_TIMEOUT_SECONDS)
    except (httpx.TimeoutException, httpx.TransportError):
        raise ProviderError(503, "The LLM service is temporarily unavailable. Please retry.")

    status = resp.status_code
    if status in (401, 403):
        raise ProviderError(
            502, "LLM provider authentication failed. Please contact organizer.", status
        )
    if status == 429:
        raise ProviderError(
            503, "The shared LLM provider limit was reached. Please wait and try again.", status
        )
    if status >= 500:
        raise ProviderError(
            503, "The LLM service is temporarily unavailable. Please retry.", status
        )
    if status >= 400:
        raise ProviderError(
            502, "The LLM service returned an error. Please retry.", status
        )

    try:
        return resp.json()
    except ValueError:
        raise ProviderError(502, "The LLM service returned an invalid response.", status)


def extract_content(body: dict) -> str:
    try:
        return body["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return ""
