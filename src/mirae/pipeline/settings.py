"""Persisted connections and validated settings. Secrets never leave the server."""

from __future__ import annotations

import ipaddress
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from mirae.api.accounts import AccountError, AuthStore
from mirae.config import AIConfig, MiraeConfig

SECTIONS = ("hardware", "drive", "safety", "vision", "speech")


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=80)
    provider: Literal["ollama", "lmstudio", "openai", "openai_compat"]
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field("", max_length=256)
    timeout_s: float = Field(20.0, gt=0.0, le=120.0)
    api_key: SecretStr | None = Field(None, exclude=True)
    clear_api_key: bool = Field(False, exclude=True)

    @field_validator("base_url")
    @classmethod
    def endpoint(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("endpoint must be an HTTP or HTTPS URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("endpoint must not contain credentials, query parameters or fragments")
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            address = None
        if address and (address.is_link_local or address.is_multicast or address.is_unspecified):
            raise ValueError("link-local, multicast and unspecified endpoints are not allowed")
        return value.rstrip("/")


class PipelineSettings:
    def __init__(self, accounts: AuthStore) -> None:
        self.accounts = accounts
        self.key_path = accounts.path.with_suffix(".key")
        with accounts.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS pipeline_connections (
                    id TEXT PRIMARY KEY, config TEXT NOT NULL, secret BLOB,
                    checked TEXT, updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pipeline_settings (
                    name TEXT PRIMARY KEY, value TEXT NOT NULL
                );
            """)

    def _cipher(self) -> Fernet:
        if not self.key_path.exists():
            with self.accounts.connection() as db:
                if db.execute(
                    "SELECT 1 FROM pipeline_connections WHERE secret IS NOT NULL LIMIT 1"
                ).fetchone():
                    raise AccountError(503, "credential key is missing; restore it from backup")
            try:
                fd = os.open(self.key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(fd, "wb") as output:
                    output.write(Fernet.generate_key())
                    output.flush()
                    os.fsync(output.fileno())
        return Fernet(self.key_path.read_bytes())

    def value(self, name: str, default: Any = None) -> Any:
        with self.accounts.connection() as db:
            row = db.execute("SELECT value FROM pipeline_settings WHERE name=?", (name,)).fetchone()
            return json.loads(row[0]) if row else default

    def set_value(self, name: str, value: Any, actor: str) -> None:
        with self.accounts.connection(write=True) as db:
            db.execute(
                "INSERT INTO pipeline_settings VALUES (?,?) ON CONFLICT(name) "
                "DO UPDATE SET value=excluded.value",
                (name, json.dumps(value)),
            )
            self.accounts.audit(db, actor, "pipeline.updated", name)

    def secret(self, name: str) -> str | None:
        """A service credential (e.g. ``elevenlabs``), decrypted. None when not set."""
        token = self.value(f"secret:{name}")
        if token is None:
            return None
        try:
            return self._cipher().decrypt(token.encode()).decode()
        except (InvalidToken, ValueError) as exc:
            raise AccountError(
                503, "cannot decrypt API credentials; check the credential key"
            ) from exc

    def set_secret(self, name: str, value: str | None, actor: str) -> None:
        token = self._cipher().encrypt(value.encode()).decode() if value else None
        with self.accounts.connection(write=True) as db:
            if token is None:
                db.execute("DELETE FROM pipeline_settings WHERE name=?", (f"secret:{name}",))
            else:
                db.execute(
                    "INSERT INTO pipeline_settings VALUES (?,?) ON CONFLICT(name) "
                    "DO UPDATE SET value=excluded.value",
                    (f"secret:{name}", json.dumps(token)),
                )
            self.accounts.audit(db, actor, "secret.updated" if token else "secret.cleared", name)

    def connections(self) -> list[dict[str, Any]]:
        with self.accounts.connection() as db:
            rows = db.execute(
                "SELECT * FROM pipeline_connections ORDER BY updated_at DESC"
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    **json.loads(row["config"]),
                    "has_api_key": row["secret"] is not None,
                    "check": json.loads(row["checked"]) if row["checked"] else None,
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]

    def connection(self, connection_id: str) -> tuple[ConnectionInput, str | None]:
        config, key, _ = self.connection_snapshot(connection_id)
        return config, key

    def connection_snapshot(self, connection_id: str) -> tuple[ConnectionInput, str | None, float]:
        with self.accounts.connection() as db:
            row = db.execute(
                "SELECT * FROM pipeline_connections WHERE id=?", (connection_id,)
            ).fetchone()
            if row is None:
                raise AccountError(404, "connection not found")
            key = None
            if row["secret"] is not None:
                try:
                    key = self._cipher().decrypt(row["secret"]).decode()
                except (InvalidToken, ValueError) as exc:
                    raise AccountError(
                        503, "cannot decrypt API credentials; check the credential key"
                    ) from exc
            return ConnectionInput.model_validate_json(row["config"]), key, float(row["updated_at"])

    def save_connection(self, connection_id: str | None, value: ConnectionInput, actor: str) -> str:
        encrypted = (
            self._cipher().encrypt(value.api_key.get_secret_value().encode())
            if value.api_key
            else None
        )
        with self.accounts.connection(write=True) as db:
            old = None
            if connection_id:
                old = db.execute(
                    "SELECT * FROM pipeline_connections WHERE id=?", (connection_id,)
                ).fetchone()
                if old is None:
                    raise AccountError(404, "connection not found")
            if old and not value.clear_api_key and value.api_key is None:
                encrypted = old["secret"]
            if value.clear_api_key:
                encrypted = None
            # Replacing the endpoint must never silently send an existing key to a
            # different server. Re-enter the credential explicitly for that change.
            if (
                old
                and json.loads(old["config"])["base_url"] != value.base_url
                and value.api_key is None
            ):
                encrypted = None
            if value.provider == "openai" and encrypted is None:
                raise AccountError(422, "OpenAI requires an API key")
            connection_id = connection_id or secrets.token_hex(12)
            db.execute(
                "INSERT INTO pipeline_connections VALUES (?,?,?,NULL,?) ON CONFLICT(id) "
                "DO UPDATE SET config=excluded.config,secret=excluded.secret,checked=NULL,"
                "updated_at=excluded.updated_at",
                (connection_id, value.model_dump_json(), encrypted, time.time()),
            )
            self.accounts.audit(db, actor, "connection.saved", value.name)
            return connection_id

    def save_check(self, connection_id: str, result: dict[str, Any], revision: float) -> bool:
        with self.accounts.connection(write=True) as db:
            updated = db.execute(
                "UPDATE pipeline_connections SET checked=? WHERE id=? AND updated_at=?",
                (json.dumps(result), connection_id, revision),
            )
            return updated.rowcount == 1

    def delete_connection(self, connection_id: str, actor: str) -> None:
        with self.accounts.connection(write=True) as db:
            active = db.execute(
                "SELECT value FROM pipeline_settings WHERE name='active_connection'"
            ).fetchone()
            if active and json.loads(active[0]) == connection_id:
                raise AccountError(409, "disable the selected LLM before deleting its connection")
            row = db.execute(
                "SELECT config FROM pipeline_connections WHERE id=?", (connection_id,)
            ).fetchone()
            if row is None:
                raise AccountError(404, "connection not found")
            db.execute("DELETE FROM pipeline_connections WHERE id=?", (connection_id,))
            self.accounts.audit(db, actor, "connection.deleted", json.loads(row[0])["name"])

    def desired_config(self, base: MiraeConfig) -> MiraeConfig:
        data = base.model_dump()
        for section in SECTIONS:
            saved = self.value(section)
            if section == "hardware" and saved and saved.get("backend") == "sim":
                saved = {**saved, "backend": "none"}
            if saved is not None:
                data[section] = saved
        # AI secrets are excluded from serialization, so retain an explicit
        # non-managed provider when no dashboard selection has been saved.
        data["ai"] = base.ai
        selected = self.value("active_connection", "unmanaged")
        if selected is None:
            data["ai"] = AIConfig(provider="none")
        elif selected != "unmanaged":
            connection, key = self.connection(selected)
            data["ai"] = ai_config(connection, key)
        return MiraeConfig.model_validate(data)


def ai_config(connection: ConnectionInput, key: str | None) -> AIConfig:
    return AIConfig(
        provider="openai_compat",
        base_url=connection.base_url,
        model=connection.model,
        timeout_s=connection.timeout_s,
        api_key=SecretStr(key) if key else None,
    )


def load_managed_config(config: MiraeConfig) -> MiraeConfig:
    if not Path(config.api.database_path).is_file():
        return config
    return PipelineSettings(AuthStore(config.api.database_path)).desired_config(config)
