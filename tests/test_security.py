from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from mirae.api.accounts import AccountError, AuthStore, digest
from mirae.api.app import create_app
from mirae.config import load_config
from mirae.robot import Robot

PASSWORD = "correct-horse-mirae-42"


@pytest.fixture
def access_client() -> Iterator[TestClient]:
    with TestClient(create_app(Robot(load_config("local")))) as client:
        yield client


def register(client: TestClient) -> dict[str, Any]:
    result = client.post(
        "/api/auth/register",
        json={
            "username": "admin",
            "display_name": "Administrator",
            "password": PASSWORD,
        },
    )
    assert result.status_code == 201, result.text
    body: dict[str, Any] = result.json()
    client.headers["X-CSRF-Token"] = body["csrf_token"]
    user: dict[str, Any] = body["user"]
    return user


def add_user(client: TestClient, role: str = "viewer", username: str = "viewer") -> dict[str, Any]:
    response = client.post(
        "/api/admin/users",
        json={
            "username": username,
            "display_name": username.title(),
            "password": PASSWORD,
            "role_id": role,
        },
    )
    assert response.status_code == 201, response.text
    user: dict[str, Any] = response.json()
    return user


def issue(client: TestClient, owner: str, scopes: list[str]) -> dict[str, Any]:
    response = client.post(
        "/api/admin/tokens",
        json={"name": "integration", "user_id": owner, "scopes": scopes, "expires_days": 30},
    )
    assert response.status_code == 201, response.text
    token: dict[str, Any] = response.json()
    return token


def test_bootstrap_closes_registration_and_locks_anonymous_robot(access_client: TestClient) -> None:
    client = access_client
    assert client.get("/api/auth/status").json() == {"registration_open": True}
    assert client.get("/api/status").status_code == 401
    assert client.post("/api/drive", json={"linear": 0.3}).status_code == 401
    assert client.get("/admin").status_code == 200
    assert client.get("/admin/assets/admin.js").status_code == 200
    user = register(client)
    assert user["role_id"] == "admin"
    assert client.get("/api/auth/status").json() == {"registration_open": False}
    second = client.post(
        "/api/auth/register",
        json={"username": "other", "display_name": "Other", "password": PASSWORD},
    )
    assert second.status_code == 403
    assert client.get("/api/auth/me").json()["user"]["id"] == user["id"]
    assert client.get("/api/admin/users").status_code == 200


def test_csrf_cookie_flags_origin_and_logout(access_client: TestClient) -> None:
    client = access_client
    register(client)
    cookie = client.cookies.get("mirae_session")
    client.headers.pop("X-CSRF-Token")
    assert client.post("/api/stop").status_code == 403
    client.headers["X-CSRF-Token"] = client.get("/api/auth/me").json()["csrf_token"]
    assert (
        client.post("/api/stop", headers={"Origin": "https://attacker.example"}).status_code == 403
    )
    assert client.post("/api/stop").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert (
        client.get("/api/status", headers={"Cookie": f"mirae_session={cookie}"}).status_code == 401
    )
    response = client.post("/api/auth/login", json={"username": "admin", "password": PASSWORD})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert "no-store" in response.headers["cache-control"]


def test_last_active_admin_cannot_be_removed(access_client: TestClient) -> None:
    client = access_client
    user = register(client)
    for changes in ({"active": False}, {"role_id": "viewer"}):
        assert client.patch(f"/api/admin/users/{user['id']}", json=changes).status_code == 409
    assert client.delete(f"/api/admin/users/{user['id']}").status_code == 409
    assert (
        client.put("/api/admin/roles/admin", json={"name": "new", "permissions": []}).status_code
        == 409
    )
    assert client.delete("/api/admin/roles/admin").status_code == 409


def test_scoped_tokens_live_role_changes_revocation_and_hashes(
    access_client: TestClient,
    account_store: AuthStore,
) -> None:
    client = access_client
    register(client)
    user = add_user(client, "operator", "operator")
    token = issue(client, user["id"], ["robot:read", "robot:control"])
    headers = {"Authorization": f"Bearer {token['secret']}"}
    assert client.get("/api/status", headers=headers).status_code == 200
    assert client.post("/api/drive", json={"linear": -0.2}, headers=headers).status_code == 503
    assert client.post("/api/estop/release", headers=headers).status_code == 403
    assert client.get("/api/admin/users", headers=headers).status_code == 403
    listing = client.get("/api/admin/tokens").json()
    assert "secret" not in listing[0] and "hash" not in listing[0]
    with account_store.connection() as db:
        row = db.execute("SELECT hash FROM tokens WHERE id=?", (token["id"],)).fetchone()
        assert row[0] == digest(token["secret"])
        assert db.execute("SELECT password_hash FROM users LIMIT 1").fetchone()[0] != PASSWORD
    assert (
        client.patch(f"/api/admin/users/{user['id']}", json={"role_id": "viewer"}).status_code
        == 200
    )
    assert client.post("/api/drive", json={"linear": -0.2}, headers=headers).status_code == 403
    assert client.get("/api/status", headers=headers).status_code == 200
    assert client.delete(f"/api/admin/tokens/{token['id']}").status_code == 200
    assert client.get("/api/status", headers=headers).status_code == 401


def test_custom_roles_and_disable_reenable_revoke_old_credentials(
    access_client: TestClient,
) -> None:
    client = access_client
    register(client)
    role = client.post(
        "/api/admin/roles", json={"name": "Telemetry auditor", "permissions": ["robot:read"]}
    ).json()
    user = add_user(client, role["id"], "auditor")
    token = issue(client, user["id"], ["robot:read"])
    assert client.delete(f"/api/admin/roles/{role['id']}").status_code == 409
    assert (
        client.put(
            f"/api/admin/roles/{role['id']}", json={"name": "No access", "permissions": []}
        ).status_code
        == 200
    )
    headers = {"Authorization": f"Bearer {token['secret']}"}
    assert client.get("/api/status", headers=headers).status_code == 403
    assert client.patch(f"/api/admin/users/{user['id']}", json={"active": False}).status_code == 200
    assert client.patch(f"/api/admin/users/{user['id']}", json={"active": True}).status_code == 200
    assert client.get("/api/status", headers=headers).status_code == 401
    assert client.delete(f"/api/admin/users/{user['id']}").status_code == 200
    assert client.delete(f"/api/admin/roles/{role['id']}").status_code == 200
    assert any(a["action"] == "user.deleted" for a in client.get("/api/admin/audit").json())


def test_token_scope_escalation_expiration_and_websocket_revocation(
    access_client: TestClient,
    account_store: AuthStore,
) -> None:
    client = access_client
    register(client)
    user = add_user(client)
    assert (
        client.post(
            "/api/admin/tokens",
            json={"name": "bad", "user_id": user["id"], "scopes": ["users:manage"]},
        ).status_code
        == 422
    )
    token = issue(client, user["id"], ["robot:read"])
    headers = {"Authorization": f"Bearer {token['secret']}"}
    with client.websocket_connect("/ws/telemetry", headers=headers) as ws:
        assert ws.receive_json()["backend"] == "none"
        client.delete(f"/api/admin/tokens/{token['id']}")
        with pytest.raises(WebSocketDisconnect):
            for _ in range(5):
                ws.receive_json()
    token = issue(client, user["id"], ["robot:read"])
    with account_store.connection(write=True) as db:
        db.execute("UPDATE tokens SET expires_at=0 WHERE id=?", (token["id"],))
    assert (
        client.get(
            "/api/status", headers={"Authorization": f"Bearer {token['secret']}"}
        ).status_code
        == 401
    )


def test_first_admin_registration_is_atomic(account_store: AuthStore) -> None:
    def bootstrap(username: str) -> int:
        try:
            account_store.create_user(username, username, PASSWORD, "admin", bootstrap=True)
            return 201
        except AccountError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(bootstrap, ["admin-one", "admin-two"]))
    assert sorted(results) == [201, 403]
    assert len(account_store.users()) == 1


def test_password_reset_invalidates_sessions_and_tokens(
    access_client: TestClient,
    account_store: AuthStore,
) -> None:
    client = access_client
    register(client)
    user = add_user(client)
    secret, principal = account_store.login(user["username"], PASSWORD, 12)
    token = issue(client, user["id"], ["robot:read"])
    viewer = {"Cookie": f"mirae_session={secret}", "X-CSRF-Token": principal.csrf}
    assert client.get("/api/status", headers=viewer).status_code == 200
    assert (
        client.patch(
            f"/api/admin/users/{user['id']}", json={"password": "new-password-mirae-42"}
        ).status_code
        == 200
    )
    assert client.get("/api/status", headers=viewer).status_code == 401
    assert (
        client.get(
            "/api/status", headers={"Authorization": f"Bearer {token['secret']}"}
        ).status_code
        == 401
    )


def test_own_password_change_checks_current_password_and_revokes_session(
    access_client: TestClient,
) -> None:
    client = access_client
    register(client)
    assert (
        client.post(
            "/api/auth/password",
            json={"current_password": "wrong", "password": "new-password-mirae-42"},
        ).status_code
        == 401
    )
    assert client.get("/api/auth/me").status_code == 200
    assert (
        client.post(
            "/api/auth/password",
            json={"current_password": PASSWORD, "password": "new-password-mirae-42"},
        ).status_code
        == 200
    )
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.post("/api/auth/login", json={"username": "admin", "password": PASSWORD}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login", json={"username": "admin", "password": "new-password-mirae-42"}
        ).status_code
        == 200
    )


def test_login_rate_limit_is_persistent_and_generic(
    access_client: TestClient,
    account_store: AuthStore,
) -> None:
    for _ in range(20):
        account_store.check_attempt("auth:testclient")
    response = access_client.post(
        "/api/auth/login", json={"username": "missing", "password": "anything"}
    )
    assert response.status_code == 429


def test_accounts_survive_app_restart(access_client: TestClient) -> None:
    user = register(access_client)
    with TestClient(create_app(Robot(load_config("local")))) as restarted:
        assert restarted.get("/api/auth/status").json() == {"registration_open": False}
        response = restarted.post(
            "/api/auth/login", json={"username": "admin", "password": PASSWORD}
        )
        assert response.status_code == 200
        assert response.json()["user"]["id"] == user["id"]


def test_concurrent_demotion_preserves_one_active_admin(account_store: AuthStore) -> None:
    first = account_store.create_user("first", "First", PASSWORD, "admin", bootstrap=True)
    second = account_store.create_user("second", "Second", PASSWORD, "admin")

    def demote(user_id: str) -> int:
        try:
            account_store.update_user(user_id, {"role_id": "viewer"}, "test")
            return 200
        except AccountError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(demote, [first["id"], second["id"]])) == [200, 409]
    assert sum(u["active"] and u["role_id"] == "admin" for u in account_store.users()) == 1


def test_large_requests_and_cross_origin_login_are_rejected(access_client: TestClient) -> None:
    client = access_client
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "admin", "password": PASSWORD},
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/auth/login",
            content='{"password":"' + "x" * 20000 + '"}',
            headers={"Content-Type": "application/json"},
        ).status_code
        == 413
    )
