"""Thin wrapper around the Groq SDK (GPT-OSS-120B).

`is_available()` gates every call site: when GROQ_API_KEY is unset, callers
must use their deterministic fallback instead. This is what lets the whole
app run and be verified today, before a key exists.
"""

import json
import logging

from groq import AsyncGroq

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        settings = get_settings()
        self._api_key = settings.GROQ_API_KEY
        self._model = settings.GROQ_MODEL
        self._client = AsyncGroq(api_key=self._api_key) if self._api_key else None

    def is_available(self) -> bool:
        return self._client is not None

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict | None:
        """Request a strict JSON object completion. Returns None (never
        fabricated content) if the LLM is unavailable or the call fails.
        """
        if not self._client:
            return None
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=1200,
            )
            content = resp.choices[0].message.content
            return json.loads(content)
        except Exception:
            logger.exception("Groq JSON completion failed; caller should use fallback")
            return None

    async def complete_text(self, system_prompt: str, user_prompt: str) -> str | None:
        if not self._client:
            return None
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=800,
            )
            return resp.choices[0].message.content
        except Exception:
            logger.exception("Groq text completion failed; caller should use fallback")
            return None


_client_singleton: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = LLMClient()
    return _client_singleton
