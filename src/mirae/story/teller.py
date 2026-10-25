"""Writes tonight's episode, then updates the story's continuity notes.

Two LLM calls per episode. The first writes plain prose: small local models write
worse stories inside JSON. The second extracts who joined, who left or died, a
rolling summary and the closing situation as JSON. Code, not the model, applies
those changes to the cast, so a character only disappears when an episode says so.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from mirae.ai.providers import ChatMessage, LLMProvider
from mirae.config import AIConfig
from mirae.story.store import (
    MAX_CAST,
    MAX_DEPARTED,
    Character,
    Departure,
    Episode,
    Name,
    StoryState,
    StoryStore,
)

log = logging.getLogger(__name__)

SUMMARY_CHARS = 1500
SITUATION_CHARS = 1000
MAX_PROPOSALS = 4

STORY_PROMPT = """\
You are Mirae, a small robot who tells one serial bedtime story, one episode each night.
Write episode {night}. Rules:
- Continue exactly from the current situation below.
- Stay in the genre: {genre}. Keep its setting, rules and tone; never mix in another genre.
- Keep every character's name, role and relationships as listed. Never rename anyone.
- Departed characters are gone. Those who died never return. Those who left return only
  if this episode clearly brings them back.
- If someone new joins, introduce them by name. If someone leaves or dies, say so plainly.
- Introduce at most one new character.
- Keep a calm, gentle pace and end at a quiet resting point, ready for sleep.
- About {words} words of plain prose. No title, headings or lists.

STORY REFERENCE
Genre: {genre}
Premise: {premise}
The story so far: {summary}

CURRENT STATE
Main character: {protagonist}
Cast:
{cast}
Departed:
{departed}

CURRENT SITUATION
{situation}"""

NOTES_PROMPT = """\
You keep the continuity notes of a serial story. Read the new episode and reply with
one JSON object and nothing else:
{{"added": [{{"name": "...", "role": "...", "description": "..."}}],
 "removed": [{{"name": "...", "reason": "left" or "died"}}],
 "summary": "...", "situation": "..."}}

- added: characters who join the story for the first time in this episode.
- removed: cast members who leave the story or die in this episode, named exactly as
  in the cast. Leave it empty when nobody leaves.
- summary: the whole story so far, including this episode, in at most 150 words.
  Keep key events, relationships and promises.
- situation: two or three sentences on where things stand at the end of the episode.

Cast before this episode:
{cast}

Story so far before this episode: {summary}"""


class Removal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Name
    reason: Literal["left", "died"]


class StoryUpdate(BaseModel):
    """What the notes call may propose. Long text is clipped, missing text falls back."""

    model_config = ConfigDict(extra="ignore")
    added: list[Character] = Field(default_factory=list, max_length=MAX_PROPOSALS)
    removed: list[Removal] = Field(default_factory=list, max_length=MAX_PROPOSALS)
    summary: str | None = Field(None, max_length=6000)
    situation: str | None = Field(None, max_length=6000)


def _reason(value: Any) -> str:
    text = str(value).casefold()
    return "died" if any(w in text for w in ("die", "dead", "death", "kill", "pass")) else "left"


def _entries(value: Any, model: type[BaseModel], label: str, notes: list[str]) -> list[Any]:
    """Each proposal stands alone: one malformed entry must not hide a valid death."""
    valid: list[Any] = []
    for entry in value if isinstance(value, list) else []:
        if isinstance(entry, dict) and model is Removal:
            entry = {**entry, "reason": _reason(entry.get("reason", ""))}
        try:
            valid.append(model.model_validate(entry))
        except ValidationError:
            notes.append(f"ignored a malformed {label} entry")
    if len(valid) > MAX_PROPOSALS:
        notes.append(f"ignored {len(valid) - MAX_PROPOSALS} extra {label} entries")
    return valid[:MAX_PROPOSALS]


def parse_notes(raw: str) -> tuple[StoryUpdate | None, list[str]]:
    """Lenient reading of the notes call. None only when the reply is not a JSON object."""
    try:
        data = json.loads(raw)
    except ValueError:
        return None, []
    if not isinstance(data, dict):
        return None, []
    notes: list[str] = []
    text = {
        key: value.strip() if isinstance(value, str) and value.strip() else None
        for key, value in ((k, data.get(k)) for k in ("summary", "situation"))
    }
    update = StoryUpdate(
        added=_entries(data.get("added"), Character, "added", notes),
        removed=_entries(data.get("removed"), Removal, "removed", notes),
        summary=text["summary"][:6000] if text["summary"] else None,
        situation=text["situation"][:6000] if text["situation"] else None,
    )
    return update, notes


class StoryError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


@dataclass(frozen=True)
class TellResult:
    episode: Episode
    state: StoryState
    continuity_updated: bool
    notes: list[str]


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = cut.rfind(". ")
    return cut[: end + 1] if end > limit // 2 else cut.rstrip()


def _last_paragraph(text: str) -> str:
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    return _clip(paragraphs[-1] if paragraphs else text, SITUATION_CHARS)


def _cast_lines(state: StoryState) -> str:
    return "\n".join(
        f"- {c.name}: {c.role}" + (f". {c.description}" if c.description else "")
        for c in state.cast
    )


def story_messages(state: StoryState, words: int) -> list[ChatMessage]:
    departed = "\n".join(f"- {d.name}: {d.reason} (night {d.night})" for d in state.departed)
    system = STORY_PROMPT.format(
        night=state.night + 1,
        words=words,
        genre=state.genre or "as set by the premise",
        premise=state.premise,
        summary=state.summary or "This is the first episode.",
        protagonist=state.protagonist,
        cast=_cast_lines(state),
        departed=departed or "- nobody",
        situation=state.situation or "The story begins.",
    )
    return [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=f"Tell episode {state.night + 1}."),
    ]


def notes_messages(state: StoryState, text: str) -> list[ChatMessage]:
    system = NOTES_PROMPT.format(
        cast=_cast_lines(state), summary=state.summary or "Nothing yet; this is the first episode."
    )
    return [
        ChatMessage(role="system", content=system),
        ChatMessage(role="user", content=text),
    ]


def apply_update(
    state: StoryState, text: str, update: StoryUpdate | None
) -> tuple[StoryState, list[str]]:
    """The new state after one episode. Proposals that break continuity are dropped."""
    night = state.night + 1
    if update is None:
        return state.model_copy(update={"night": night, "situation": _last_paragraph(text)}), [
            "continuity notes were invalid; the cast and summary are unchanged"
        ]

    notes: list[str] = []
    cast = list(state.cast)
    departed = list(state.departed)
    for removal in update.removed:
        key = removal.name.casefold()
        if key == state.protagonist.casefold():
            notes.append(f"kept {state.protagonist}: the main character stays in the story")
            continue
        leaving = next((c for c in cast if c.name.casefold() == key), None)
        if leaving is None:
            notes.append(f"ignored removal of {removal.name}, who is not in the cast")
            continue
        cast.remove(leaving)
        departed.append(Departure(name=leaving.name, reason=removal.reason, night=night))
        notes.append(f"{leaving.name} {removal.reason}")

    dead = {d.name.casefold() for d in departed if d.reason == "died"}
    for character in update.added:
        key = character.name.casefold()
        if any(c.name.casefold() == key for c in cast):
            continue
        if key in dead:
            notes.append(f"ignored the return of {character.name}, who died")
            continue
        if len(cast) >= MAX_CAST:
            notes.append(f"ignored {character.name}: the cast is full")
            continue
        cast.append(character)
        # Someone who left earlier and has come back is no longer departed.
        departed = [d for d in departed if d.name.casefold() != key]
        notes.append(f"{character.name} joined as {character.role}")

    new_state = StoryState(
        premise=state.premise,
        genre=state.genre,
        protagonist=state.protagonist,
        cast=cast,
        departed=departed[-MAX_DEPARTED:],
        summary=_clip(update.summary, SUMMARY_CHARS) if update.summary else state.summary,
        situation=(
            _clip(update.situation, SITUATION_CHARS) if update.situation else _last_paragraph(text)
        ),
        night=night,
    )
    return new_state, notes


class StoryTeller:
    """One episode at a time. The provider and config are read per call: they hot-swap."""

    def __init__(
        self,
        store: StoryStore,
        provider: Callable[[], LLMProvider | None],
        config: Callable[[], AIConfig],
    ) -> None:
        self.store = store
        self._provider = provider
        self._config = config
        self._lock = asyncio.Lock()

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    async def tell(self) -> TellResult:
        if self._lock.locked():
            raise StoryError(429, "an episode is already being written")
        async with self._lock:
            state = await asyncio.to_thread(self.store.load)
            if state is None:
                raise StoryError(409, "no story yet; start one first")
            provider = self._provider()
            if provider is None:
                raise StoryError(503, "no AI provider configured")
            cfg = self._config()
            loop = asyncio.get_running_loop()
            deadline = loop.time() + cfg.story_timeout_s

            try:
                text = await asyncio.wait_for(
                    provider.complete(
                        story_messages(state, cfg.story_words), timeout_s=cfg.story_timeout_s
                    ),
                    timeout=cfg.story_timeout_s,
                )
            except TimeoutError as exc:
                raise StoryError(504, "the episode took too long to write") from exc
            except Exception as exc:
                log.exception("story generation failed")
                raise StoryError(502, "the AI provider failed to write the episode") from exc
            text = text.strip()
            if not text:
                raise StoryError(502, "the AI provider returned an empty episode")

            update: StoryUpdate | None = None
            rejected: list[str] = []
            remaining = max(deadline - loop.time(), 1.0)
            try:
                raw = await asyncio.wait_for(
                    provider.complete(
                        notes_messages(state, text), json_mode=True, timeout_s=remaining
                    ),
                    timeout=remaining,
                )
                update, rejected = parse_notes(raw)
                if update is None:
                    log.warning("rejected story notes: %r", raw[:500])
            except Exception:
                log.exception("story notes failed")

            new_state, notes = apply_update(state, text, update)
            episode = await asyncio.to_thread(self.store.commit, state.night, new_state, text)
            return TellResult(episode, new_state, update is not None, rejected + notes)
