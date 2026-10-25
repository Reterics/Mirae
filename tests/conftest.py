from pathlib import Path

import pytest

from mirae.api.accounts import PERMISSIONS, AuthStore


@pytest.fixture(autouse=True)
def isolate_accounts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("mirae.cli.load_managed_config", lambda config: config)
    monkeypatch.setattr(
        "mirae.api.app.AuthStore", lambda path: AuthStore(str(tmp_path / "accounts.db"))
    )


@pytest.fixture
def account_store(tmp_path: Path) -> AuthStore:
    return AuthStore(str(tmp_path / "accounts.db"))


@pytest.fixture
def test_token(account_store: AuthStore) -> str:
    user = account_store.create_user(
        "test-admin", "Test Admin", "test-password-long", "admin", bootstrap=True
    )
    _, principal = account_store.login(user["username"], "test-password-long", 12)
    return str(
        account_store.issue_token(user["id"], "Test client", list(PERMISSIONS), 1, principal)[
            "secret"
        ]
    )
