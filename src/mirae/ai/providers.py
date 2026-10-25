from __future__ import annotations

import json
import os
import re
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel

from mirae.config import AIConfig


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        timeout_s: float | None = None,
    ) -> str: ...

    async def aclose(self) -> None: ...


class FakeProvider:
    """Offline keyword matcher. Lets the full intent pipeline run in dev and CI."""

    _RULES: tuple[tuple[str, dict[str, object]], ...] = (
        (r"\bstop\b|\bhalt\b", {"action": "stop"}),
        (r"\b(back|backward|reverse)\b", {"action": "move", "direction": "backward"}),
        (r"\b(forward|ahead|go)\b", {"action": "move", "direction": "forward"}),
        (r"\bleft\b", {"action": "turn", "direction": "left"}),
        (r"\bright\b", {"action": "turn", "direction": "right"}),
        (r"\bfollow\b", {"action": "follow_person"}),
        (r"\b(come here|approach)\b", {"action": "approach_person"}),
        (r"\bexplore\b", {"action": "explore"}),
        (r"\bsleep\b", {"action": "sleep"}),
    )

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        timeout_s: float | None = None,
    ) -> str:
        text = messages[-1].content.lower()
        for pattern, intent in self._RULES:
            if re.search(pattern, text):
                return json.dumps(intent)
        return json.dumps({"action": "say", "text": "Sorry, I did not understand that."})

    async def aclose(self) -> None:
        pass


class OpenAICompatProvider:
    """Chat Completions over HTTP: Ollama, llama.cpp server, LM Studio, vLLM, hosted APIs."""

    def __init__(self, cfg: AIConfig) -> None:
        headers = {}
        key = cfg.api_key.get_secret_value() if cfg.api_key else None
        if key is None and cfg.api_key_env:
            key = os.environ.get(cfg.api_key_env)
        if key:
            headers["Authorization"] = f"Bearer {key}"
        self._model = cfg.model
        self._client = httpx.AsyncClient(
            base_url=cfg.base_url.rstrip("/") + "/",
            headers=headers,
            timeout=cfg.timeout_s,
            trust_env=False,
            follow_redirects=False,
        )

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        timeout_s: float | None = None,
    ) -> str:
        body: dict[str, object] = {
            "model": self._model,
            "messages": [m.model_dump() for m in messages],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        # Long generations (stories) pass their own timeout; commands use the client default.
        timeout = httpx.USE_CLIENT_DEFAULT if timeout_s is None else httpx.Timeout(timeout_s)
        response = await self._client.post("chat/completions", json=body, timeout=timeout)
        response.raise_for_status()
        content: str = response.json()["choices"][0]["message"]["content"]
        return content

    async def aclose(self) -> None:
        await self._client.aclose()


def build_provider(cfg: AIConfig) -> LLMProvider | None:
    if cfg.provider == "openai_compat":
        return OpenAICompatProvider(cfg)
    return None
