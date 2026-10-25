"""Persisted story state: the cast, who has left, the running summary and each episode.

The LLM never writes this state directly. It proposes changes, ``teller.apply_update``
validates them, and the store saves the episode and the new state in one transaction.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from mirae.api.accounts import AccountError, AuthStore

MAX_CAST = 12
MAX_DEPARTED = 100

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class Character(BaseModel):
    # Lenient on input: models often add fields such as "age" to a character.
    model_config = ConfigDict(extra="ignore")
    name: Name
    role: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""


class Departure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    reason: Literal["left", "died"]
    night: int = Field(ge=1)


class StoryState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    premise: str = Field(min_length=1, max_length=1000)
    # Keeps the model in one kind of story: "science fiction", "fantasy", "mystery", ...
    genre: str = Field("", max_length=60)
    protagonist: Name
    cast: list[Character] = Field(min_length=1, max_length=MAX_CAST)
    departed: list[Departure] = Field(default_factory=list, max_length=MAX_DEPARTED)
    summary: str = Field("", max_length=1500)
    situation: str = Field("", max_length=1000)
    night: int = Field(0, ge=0)

    @model_validator(mode="after")
    def consistent_cast(self) -> Self:
        names = [c.name.casefold() for c in self.cast]
        if len(set(names)) != len(names):
            raise ValueError("cast names must be unique")
        if self.protagonist.casefold() not in names:
            raise ValueError("the protagonist must be in the cast")
        return self


@dataclass(frozen=True)
class Episode:
    night: int
    text: str
    created_at: float


class StoryStore:
    def __init__(self, accounts: AuthStore) -> None:
        self.accounts = accounts
        with accounts.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS story_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    state TEXT NOT NULL, updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS story_episodes (
                    night INTEGER PRIMARY KEY, text TEXT NOT NULL, created_at REAL NOT NULL
                );
            """)

    def load(self) -> StoryState | None:
        with self.accounts.connection() as db:
            row = db.execute("SELECT state FROM story_state WHERE id=1").fetchone()
            return StoryState.model_validate_json(row[0]) if row else None

    def reset(self, state: StoryState) -> None:
        with self.accounts.connection(write=True) as db:
            db.execute("DELETE FROM story_episodes")
            db.execute(
                "INSERT OR REPLACE INTO story_state (id, state, updated_at) VALUES (1, ?, ?)",
                (state.model_dump_json(), time.time()),
            )

    def commit(self, previous_night: int, state: StoryState, text: str) -> Episode:
        """Save one episode, unless the story moved on (or was reset) while it was written."""
        now = time.time()
        with self.accounts.connection(write=True) as db:
            row = db.execute("SELECT state FROM story_state WHERE id=1").fetchone()
            if row is None or StoryState.model_validate_json(row[0]).night != previous_night:
                raise AccountError(409, "the story changed while this episode was written")
            db.execute(
                "INSERT INTO story_episodes (night, text, created_at) VALUES (?, ?, ?)",
                (state.night, text, now),
            )
            db.execute(
                "UPDATE story_state SET state=?, updated_at=? WHERE id=1",
                (state.model_dump_json(), now),
            )
        return Episode(state.night, text, now)

    def episodes(self, limit: int = 3) -> list[Episode]:
        with self.accounts.connection() as db:
            rows = db.execute(
                "SELECT night, text, created_at FROM story_episodes ORDER BY night DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [Episode(row["night"], row["text"], row["created_at"]) for row in rows]
