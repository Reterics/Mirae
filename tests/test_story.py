import asyncio
import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from mirae.ai.providers import ChatMessage
from mirae.api.accounts import AuthStore
from mirae.api.app import ACTIONS, create_app
from mirae.config import AIConfig, load_config
from mirae.robot import Robot
from mirae.story.store import Character, Departure, StoryState, StoryStore
from mirae.story.teller import (
    StoryTeller,
    StoryUpdate,
    apply_update,
    parse_notes,
    story_messages,
)

EPISODE = "John and Clay mended the nets.\n\nThe tide came in softly and everyone slept."


class ScriptedProvider:
    """Answers the episode call with prose and the notes call with the queued JSON."""

    def __init__(self, *notes: object) -> None:
        self.notes = list(notes)
        self.calls: list[list[ChatMessage]] = []

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        timeout_s: float | None = None,
    ) -> str:
        self.calls.append(messages)
        if not json_mode:
            return EPISODE
        note = self.notes.pop(0)
        return note if isinstance(note, str) else json.dumps(note)

    async def aclose(self) -> None:
        pass


def seed() -> StoryState:
    return StoryState(
        premise="A fishing village by a quiet sea.",
        genre="fantasy",
        protagonist="John",
        cast=[
            Character(name="John", role="harbour master"),
            Character(name="Clay", role="John's apprentice"),
        ],
    )


def notes(**changes: object) -> dict[str, object]:
    return {"summary": "John and Clay keep the harbour.", "situation": "Night falls."} | changes


def names(state: StoryState) -> list[str]:
    return [c.name for c in state.cast]


def test_cast_survives_episodes_without_changes() -> None:
    state, _ = apply_update(seed(), EPISODE, StoryUpdate.model_validate(notes()))
    state, _ = apply_update(state, EPISODE, StoryUpdate.model_validate(notes()))
    assert names(state) == ["John", "Clay"]
    assert state.night == 2


def test_arrivals_and_departures_update_the_cast() -> None:
    update = StoryUpdate.model_validate(
        notes(
            added=[{"name": "Mira", "role": "lighthouse keeper", "age": 70}],
            removed=[{"name": "clay", "reason": "died"}],
        )
    )
    state, changes = apply_update(seed(), EPISODE, update)
    assert names(state) == ["John", "Mira"]
    assert [(d.name, d.reason, d.night) for d in state.departed] == [("Clay", "died", 1)]
    assert changes == ["Clay died", "Mira joined as lighthouse keeper"]


def test_continuity_rules_reject_bad_proposals() -> None:
    update = StoryUpdate.model_validate(
        notes(removed=[{"name": "John", "reason": "left"}, {"name": "Ghost", "reason": "left"}])
    )
    state, changes = apply_update(seed(), EPISODE, update)
    assert names(state) == ["John", "Clay"]
    assert len(changes) == 2

    dead = state.model_copy(
        update={"cast": state.cast[:1], "departed": [_departure("Clay", "died")]}
    )
    back = StoryUpdate.model_validate(notes(added=[{"name": "Clay", "role": "apprentice"}]))
    state, changes = apply_update(dead, EPISODE, back)
    assert names(state) == ["John"]
    assert changes == ["ignored the return of Clay, who died"]


def test_someone_who_left_can_return() -> None:
    gone = seed().model_copy(update={"cast": seed().cast[:1], "departed": [_departure("Clay")]})
    back = StoryUpdate.model_validate(notes(added=[{"name": "Clay", "role": "apprentice"}]))
    state, _ = apply_update(gone, EPISODE, back)
    assert names(state) == ["John", "Clay"]
    assert state.departed == []


def test_one_malformed_entry_does_not_hide_a_death() -> None:
    raw = json.dumps(
        {
            "added": None,
            "removed": [{"name": "Clay", "reason": "passed away"}, {"reason": "left"}],
            "summary": "",
        }
    )
    update, rejected = parse_notes(raw)
    assert update is not None
    assert rejected == ["ignored a malformed removed entry"]
    state, changes = apply_update(seed().model_copy(update={"summary": "Before."}), EPISODE, update)
    assert names(state) == ["John"]
    assert changes == ["Clay died"]
    assert state.summary == "Before."
    assert state.situation == "The tide came in softly and everyone slept."
    assert parse_notes("[]") == (None, [])
    assert parse_notes("not json") == (None, [])


def test_invalid_notes_keep_the_cast_and_move_the_story_on() -> None:
    state, changes = apply_update(seed(), EPISODE, None)
    assert names(state) == ["John", "Clay"]
    assert state.night == 1
    assert state.situation == "The tide came in softly and everyone slept."
    assert changes


def test_prompt_carries_state_reference_and_situation() -> None:
    state = seed().model_copy(
        update={
            "summary": "Clay found a map.",
            "situation": "The boat is ready.",
            "departed": [_departure("Old Tom", "died")],
        }
    )
    prompt = story_messages(state, 300)[0].content
    for expected in (
        "A fishing village",
        "Stay in the genre: fantasy.",
        "Genre: fantasy",
        "Clay found a map.",
        "- Clay: John's apprentice",
        "- Old Tom: died (night 1)",
        "The boat is ready.",
        "About 300 words",
    ):
        assert expected in prompt


def test_teller_persists_episodes(account_store: AuthStore) -> None:
    store = StoryStore(account_store)
    store.reset(seed())
    provider = ScriptedProvider(notes(added=[{"name": "Mira", "role": "keeper"}]), "not json")
    teller = StoryTeller(store, lambda: provider, AIConfig)

    first = asyncio.run(teller.tell())
    assert first.continuity_updated
    second = asyncio.run(teller.tell())
    assert not second.continuity_updated

    saved = store.load()
    assert saved is not None
    assert saved.night == 2
    assert names(saved) == ["John", "Clay", "Mira"]
    assert [e.night for e in store.episodes()] == [2, 1]
    # The second episode was written from the state the first one left behind.
    assert "Mira" in provider.calls[2][0].content


def test_commit_refuses_a_forked_story(account_store: AuthStore) -> None:
    store = StoryStore(account_store)
    store.reset(seed())
    state, _ = apply_update(seed(), EPISODE, None)
    store.commit(0, state, EPISODE)
    with pytest.raises(Exception, match="changed"):
        store.commit(0, state, EPISODE)


@pytest.fixture
def robot() -> Robot:
    robot = Robot(load_config("local"))
    robot._provider = ScriptedProvider(notes(), notes())
    return robot


@pytest.fixture
def client(robot: Robot, test_token: str) -> Iterator[TestClient]:
    with TestClient(create_app(robot), headers={"Authorization": f"Bearer {test_token}"}) as c:
        yield c


def test_story_api(client: TestClient, robot: Robot, monkeypatch: pytest.MonkeyPatch) -> None:
    assert client.post("/api/story/tell", json={}).status_code == 409
    start = {
        "premise": "A fishing village by a quiet sea.",
        "genre": "fantasy",
        "protagonist": "John",
        "cast": [{"name": "John", "role": "harbour master"}],
    }
    assert client.put("/api/story", json={**start, "protagonist": "Nobody"}).status_code == 422
    assert client.put("/api/story", json=start).status_code == 200

    response = client.post("/api/story/tell", json={"sleep": True})
    assert response.status_code == 200
    body = response.json()
    assert body["episode"]["night"] == 1
    assert body["behavior"] == "SLEEP"
    assert client.get("/api/story").json()["episodes"][0]["text"] == EPISODE

    # An unhealthy robot refuses before writing, so the night does not advance.
    monkeypatch.setattr(Robot, "healthy", property(lambda self: False))
    assert client.post("/api/story/tell", json={"sleep": True}).status_code == 503
    assert client.get("/api/story").json()["story"]["night"] == 1


def test_story_action_can_be_turned_off(client: TestClient) -> None:
    assert client.get("/api/actions").json()["actions"][0] == {
        "id": "story",
        "name": "Story",
        "description": ACTIONS["story"][1],
        "enabled": True,
    }
    assert client.put("/api/actions/dance", json={"enabled": False}).status_code == 404
    response = client.put("/api/actions/story", json={"enabled": False})
    assert response.json()["actions"][0]["enabled"] is False

    start = {
        "premise": "A quiet sea.",
        "genre": "fantasy",
        "protagonist": "John",
        "cast": [{"name": "John", "role": "harbour master"}],
    }
    assert client.put("/api/story", json=start).status_code == 409
    assert client.post("/api/story/tell", json={}).status_code == 409
    # Reading the story still works, so turning it back on loses nothing.
    assert client.get("/api/story").status_code == 200

    client.put("/api/actions/story", json={"enabled": True})
    assert client.put("/api/story", json=start).status_code == 200


def _departure(name: str, reason: str = "left") -> Departure:
    return Departure.model_validate({"name": name, "reason": reason, "night": 1})
