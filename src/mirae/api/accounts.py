"""Local accounts, live RBAC and revocable opaque credentials in SQLite.

Each operation owns its connection. Call from worker threads after startup; no
password hashing or database I/O belongs on the robot's asyncio control loop.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

PERMISSIONS = {
    "robot:read": "Read robot status and telemetry",
    "robot:control": "Send movement, stop and AI commands",
    "robot:release": "Release emergency stop",
    "users:manage": "Create and manage users",
    "roles:manage": "Create and manage roles",
    "tokens:manage": "Create and revoke API keys",
    "audit:read": "Read access audit log",
    "pipeline:manage": "Manage LLM connections, local processing and hardware settings",
}
BUILTINS = {
    "admin": ("Administrator", list(PERMISSIONS)),
    "operator": ("Operator", ["robot:read", "robot:control"]),
    "viewer": ("Viewer", ["robot:read"]),
}


class AccountError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    hashed = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=2**15, r=8, p=3, maxmem=64 * 1024 * 1024
    )
    return f"scrypt$32768$8$3${salt}${hashed.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    # The format is versioned for a future hash migration; parameters are fixed
    # here so a corrupt database cannot request arbitrary memory/CPU resources.
    return hmac.compare_digest(hash_password(password, encoded.split("$")[4]), encoded)


@dataclass(frozen=True)
class Principal:
    user_id: str
    username: str
    display_name: str
    role_id: str
    permissions: frozenset[str]
    kind: Literal["session", "token"]
    credential_hash: str
    csrf: str = ""
    role_name: str = ""

    def public(self) -> dict[str, Any]:
        return {
            "id": self.user_id,
            "username": self.username,
            "display_name": self.display_name,
            "role_id": self.role_id,
            "role_name": self.role_name,
            "permissions": sorted(self.permissions),
        }


class AuthStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError:
            pass
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            version = int(db.execute("PRAGMA user_version").fetchone()[0])
            if version not in (0, 1):
                raise ValueError("unsupported account database version")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS roles (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE,
                    permissions TEXT NOT NULL, builtin INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL, password_hash TEXT NOT NULL,
                    role_id TEXT NOT NULL REFERENCES roles(id), active INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL, last_login REAL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    csrf TEXT NOT NULL, expires_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tokens (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL, prefix TEXT NOT NULL, hash TEXT NOT NULL UNIQUE,
                    scopes TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL,
                    last_used REAL, revoked_at REAL
                );
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY, at REAL NOT NULL, actor TEXT NOT NULL,
                    action TEXT NOT NULL, target TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    key TEXT PRIMARY KEY, count INTEGER, until REAL
                );
                PRAGMA user_version=1;
            """)
            for role_id, (name, permissions) in BUILTINS.items():
                db.execute(
                    "INSERT INTO roles VALUES (?,?,?,1) ON CONFLICT(id) DO UPDATE SET "
                    "name=excluded.name,permissions=excluded.permissions WHERE roles.builtin=1",
                    (role_id, name, json.dumps(permissions)),
                )
        # Same expensive verification path for an unknown username.
        self._dummy_hash = hash_password(secrets.token_urlsafe(32))

    @contextmanager
    def connection(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=3.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except sqlite3.IntegrityError as exc:
            db.rollback()
            raise AccountError(409, "name already exists or record is still in use") from exc
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def audit(db: sqlite3.Connection, actor: str, action: str, target: str) -> None:
        db.execute(
            "INSERT INTO audit(at,actor,action,target) VALUES (?,?,?,?)",
            (time.time(), actor, action, target),
        )

    def registration_open(self) -> bool:
        with self.connection() as db:
            return db.execute("SELECT 1 FROM users LIMIT 1").fetchone() is None

    def check_attempt(self, key: str) -> None:
        now = time.time()
        with self.connection(write=True) as db:
            db.execute("DELETE FROM attempts WHERE until < ?", (now,))
            row = db.execute("SELECT count FROM attempts WHERE key=?", (key,)).fetchone()
            if row is not None and row[0] >= 20:
                raise AccountError(429, "too many attempts; try again in 15 minutes")
            db.execute(
                "INSERT INTO attempts VALUES (?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1",
                (key, now + 900),
            )

    @staticmethod
    def user(db: sqlite3.Connection, user_id: str) -> dict[str, Any]:
        row = db.execute(
            "SELECT id,username,display_name,role_id,active,created_at,last_login "
            "FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
        if row is None:
            raise AccountError(404, "user not found")
        result = dict(row)
        result["active"] = bool(result["active"])
        return result

    def create_user(
        self,
        username: str,
        display_name: str,
        password: str,
        role_id: str,
        actor: str = "bootstrap",
        *,
        bootstrap: bool = False,
    ) -> dict[str, Any]:
        encoded = hash_password(password)
        user_id = secrets.token_hex(12)
        with self.connection(write=True) as db:
            if bootstrap:
                if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                    raise AccountError(403, "registration is closed; contact an administrator")
                role_id = "admin"
            db.execute(
                "INSERT INTO users VALUES (?,?,?,?,?,1,?,NULL)",
                (user_id, username.lower(), display_name, encoded, role_id, time.time()),
            )
            self.audit(db, actor, "user.registered" if bootstrap else "user.created", username)
            return self.user(db, user_id)

    def login(self, username: str, password: str, hours: float) -> tuple[str, Principal]:
        with self.connection() as db:
            row = db.execute("SELECT * FROM users WHERE username=?", (username.lower(),)).fetchone()
        encoded = row["password_hash"] if row else self._dummy_hash
        valid = verify_password(password, encoded)
        if not valid or row is None or not row["active"]:
            with self.connection(write=True) as db:
                self.audit(db, "anonymous", "session.denied", username.lower())
            raise AccountError(401, "invalid username or password")
        secret, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.connection(write=True) as db:
            current = db.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
            if current is None or not current["active"] or current["password_hash"] != encoded:
                raise AccountError(401, "invalid username or password")
            db.execute("DELETE FROM sessions WHERE expires_at <= ?", (time.time(),))
            db.execute(
                "INSERT INTO sessions VALUES (?,?,?,?)",
                (digest(secret), row["id"], csrf, time.time() + hours * 3600),
            )
            db.execute("UPDATE users SET last_login=? WHERE id=?", (time.time(), row["id"]))
            self.audit(db, username.lower(), "session.created", username.lower())
        principal = self.authenticate(secret, "session")
        if principal is None:
            raise AccountError(401, "session invalidated")
        return secret, principal

    def authenticate(self, secret: str, kind: Literal["session", "token"]) -> Principal | None:
        if not secret or len(secret) > 256:
            return None
        table = "sessions" if kind == "session" else "tokens"
        hashed = digest(secret)
        with self.connection() as db:
            row = db.execute(
                "SELECT c.*,u.username,u.display_name,u.role_id,u.active,r.permissions,"
                "r.name AS role_name "
                f"FROM {table} c JOIN users u ON u.id=c.user_id JOIN roles r ON r.id=u.role_id "
                "WHERE c.hash=? AND c.expires_at>?",
                (hashed, time.time()),
            ).fetchone()
            if (
                row is None
                or not row["active"]
                or (kind == "token" and row["revoked_at"] is not None)
            ):
                return None
            permissions = frozenset(json.loads(row["permissions"]))
            if kind == "token":
                permissions &= frozenset(json.loads(row["scopes"]))
                if row["last_used"] is None or row["last_used"] < time.time() - 60:
                    db.execute("UPDATE tokens SET last_used=? WHERE hash=?", (time.time(), hashed))
            return Principal(
                row["user_id"],
                row["username"],
                row["display_name"],
                row["role_id"],
                permissions,
                kind,
                hashed,
                row["csrf"] if kind == "session" else "",
                row["role_name"],
            )

    def logout(self, principal: Principal) -> None:
        with self.connection(write=True) as db:
            if principal.kind == "token":
                db.execute(
                    "UPDATE tokens SET revoked_at=? WHERE hash=?",
                    (time.time(), principal.credential_hash),
                )
            else:
                db.execute("DELETE FROM sessions WHERE hash=?", (principal.credential_hash,))
            self.audit(db, principal.username, "session.revoked", principal.username)

    def users(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            return [
                self.user(db, row[0])
                for row in db.execute("SELECT id FROM users ORDER BY created_at")
            ]

    def update_user(
        self,
        user_id: str,
        changes: dict[str, Any],
        actor: str,
        *,
        expected_hash: str | None = None,
        session_hash: str | None = None,
    ) -> dict[str, Any]:
        encoded = hash_password(changes["password"]) if changes.get("password") else None
        with self.connection(write=True) as db:
            current = self.user(db, user_id)
            if expected_hash is not None:
                stored = db.execute(
                    "SELECT password_hash FROM users WHERE id=?", (user_id,)
                ).fetchone()[0]
                session = db.execute(
                    "SELECT 1 FROM sessions WHERE hash=? AND user_id=? AND expires_at>?",
                    (session_hash, user_id, time.time()),
                ).fetchone()
                if not current["active"] or stored != expected_hash or session is None:
                    raise AccountError(401, "credentials changed; sign in again")
            role_id = changes.get("role_id", current["role_id"])
            active = changes.get("active", current["active"])
            if (
                current["role_id"] == "admin"
                and current["active"]
                and (role_id != "admin" or not active)
            ):
                count = db.execute(
                    "SELECT COUNT(*) FROM users WHERE role_id='admin' AND active=1"
                ).fetchone()[0]
                if count <= 1:
                    raise AccountError(409, "the last active administrator must be retained")
            db.execute(
                "UPDATE users SET display_name=?,role_id=?,active=? WHERE id=?",
                (
                    changes.get("display_name", current["display_name"]),
                    role_id,
                    int(active),
                    user_id,
                ),
            )
            if encoded:
                db.execute("UPDATE users SET password_hash=? WHERE id=?", (encoded, user_id))
            if encoded or not active:
                db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
                db.execute(
                    "UPDATE tokens SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL",
                    (time.time(), user_id),
                )
            self.audit(db, actor, "user.updated", current["username"])
            return self.user(db, user_id)

    def delete_user(self, user_id: str, actor: str) -> None:
        with self.connection(write=True) as db:
            user = self.user(db, user_id)
            if user["role_id"] == "admin" and user["active"]:
                count = db.execute(
                    "SELECT COUNT(*) FROM users WHERE role_id='admin' AND active=1"
                ).fetchone()[0]
                if count <= 1:
                    raise AccountError(409, "the last active administrator must be retained")
            db.execute("DELETE FROM users WHERE id=?", (user_id,))
            self.audit(db, actor, "user.deleted", user["username"])

    def change_password(self, principal: Principal, current_password: str, password: str) -> None:
        if principal.kind != "session":
            raise AccountError(403, "password change requires a browser session")
        with self.connection() as db:
            row = db.execute(
                "SELECT password_hash FROM users WHERE id=?", (principal.user_id,)
            ).fetchone()
        if row is None or not verify_password(current_password, row[0]):
            raise AccountError(401, "current password is incorrect")
        self.update_user(
            principal.user_id,
            {"password": password},
            principal.username,
            expected_hash=row[0],
            session_hash=principal.credential_hash,
        )

    def roles(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT r.*,COUNT(u.id) AS members FROM roles r LEFT JOIN users u "
                "ON u.role_id=r.id GROUP BY r.id ORDER BY r.builtin DESC,r.name"
            ).fetchall()
            return [
                dict(row, permissions=json.loads(row["permissions"]), builtin=bool(row["builtin"]))
                for row in rows
            ]

    def save_role(self, role_id: str | None, name: str, permissions: list[str], actor: str) -> str:
        if not set(permissions) <= PERMISSIONS.keys():
            raise AccountError(422, "unknown permission")
        with self.connection(write=True) as db:
            if role_id:
                row = db.execute("SELECT builtin FROM roles WHERE id=?", (role_id,)).fetchone()
                if row is None:
                    raise AccountError(404, "role not found")
                if row[0]:
                    raise AccountError(409, "built-in roles cannot be edited")
                db.execute(
                    "UPDATE roles SET name=?,permissions=? WHERE id=?",
                    (name, json.dumps(sorted(set(permissions))), role_id),
                )
            else:
                role_id = secrets.token_hex(12)
                db.execute(
                    "INSERT INTO roles VALUES (?,?,?,0)",
                    (role_id, name, json.dumps(sorted(set(permissions)))),
                )
            self.audit(db, actor, "role.saved", name)
            return role_id

    def delete_role(self, role_id: str, actor: str) -> None:
        with self.connection(write=True) as db:
            row = db.execute("SELECT name,builtin FROM roles WHERE id=?", (role_id,)).fetchone()
            if row is None:
                raise AccountError(404, "role not found")
            if row["builtin"]:
                raise AccountError(409, "built-in roles cannot be deleted")
            db.execute("DELETE FROM roles WHERE id=?", (role_id,))
            self.audit(db, actor, "role.deleted", row["name"])

    def issue_token(
        self, user_id: str, name: str, scopes: list[str], expires_days: int, actor: Principal
    ) -> dict[str, Any]:
        secret = "mra_" + secrets.token_urlsafe(32)
        token_id = secrets.token_hex(12)
        with self.connection(write=True) as db:
            user = self.user(db, user_id)
            owner = db.execute(
                "SELECT permissions FROM roles WHERE id=?", (user["role_id"],)
            ).fetchone()
            allowed = set(json.loads(owner[0])) & actor.permissions
            if not user["active"] or not scopes or not set(scopes) <= allowed:
                raise AccountError(422, "token scopes must be allowed for issuer and active owner")
            db.execute(
                "INSERT INTO tokens VALUES (?,?,?,?,?,?,?,?,NULL,NULL)",
                (
                    token_id,
                    user_id,
                    name,
                    secret[:12],
                    digest(secret),
                    json.dumps(sorted(set(scopes))),
                    time.time(),
                    time.time() + expires_days * 86400,
                ),
            )
            self.audit(db, actor.username, "token.issued", name)
        return {"id": token_id, "secret": secret}

    def tokens(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT t.id,t.name,t.prefix,t.scopes,t.user_id,u.username,t.created_at,"
                "t.expires_at,t.last_used,t.revoked_at FROM tokens t JOIN users u "
                "ON u.id=t.user_id ORDER BY t.created_at DESC"
            ).fetchall()
            return [dict(row, scopes=json.loads(row["scopes"])) for row in rows]

    def revoke_token(self, token_id: str, actor: str) -> None:
        with self.connection(write=True) as db:
            row = db.execute("SELECT name FROM tokens WHERE id=?", (token_id,)).fetchone()
            if row is None:
                raise AccountError(404, "token not found")
            db.execute(
                "UPDATE tokens SET revoked_at=COALESCE(revoked_at,?) WHERE id=?",
                (time.time(), token_id),
            )
            self.audit(db, actor, "token.revoked", row["name"])

    def audit_log(self) -> list[dict[str, Any]]:
        with self.connection() as db:
            return [
                dict(row) for row in db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 100")
            ]
