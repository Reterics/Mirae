from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from mirae.ai.providers import ChatMessage, LLMProvider
from mirae.behavior.intents import Intent, intent_adapter

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are Mirae, a small two-wheeled robot. Turn the user's request into exactly one
action. Reply with a single JSON object matching this JSON Schema and nothing else:

{schema}

Prefer "say" to answer questions or when no movement is wanted. Keep speeds low."""


class IntentPlanner:
    """Text -> one validated Intent. Invalid or failed output yields None, never motion."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider
        schema = json.dumps(intent_adapter.json_schema(), separators=(",", ":"))
        self._system = SYSTEM_PROMPT.format(schema=schema)

    async def plan(self, text: str) -> Intent | None:
        messages = [
            ChatMessage(role="system", content=self._system),
            ChatMessage(role="user", content=text),
        ]
        try:
            raw = await self._provider.complete(messages, json_mode=True)
        except Exception:
            log.exception("LLM provider failed")
            return None
        try:
            return intent_adapter.validate_json(raw)
        except ValidationError as exc:
            log.warning("rejected LLM output %r: %s", raw, exc)
            return None
