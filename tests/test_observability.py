import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from server import app as server_app


@pytest.fixture
def isolated_sessions(world, tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "_SESSIONS", {})
    monkeypatch.setattr(
        server_app, "SESSIONS_DB", tmp_path / "sessions.db"
    )


def test_session_rejects_wrong_role(isolated_sessions):
    with pytest.raises(HTTPException) as caught:
        server_app.create_session(
            server_app.SessionCreate(user_id=1, role="support")
        )

    assert caught.value.status_code == 403
    assert server_app._SESSIONS == {}


def test_token_cannot_authorize_another_session(
    isolated_sessions, monkeypatch
):
    request = server_app.SessionCreate(user_id=1, role="shopper")
    first = server_app.create_session(request)
    second = server_app.create_session(request)

    runner = AsyncMock(
        side_effect=AssertionError("Agent must not run")
    )
    monkeypatch.setattr(server_app.Runner, "run", runner)

    with pytest.raises(HTTPException) as caught:
        asyncio.run(server_app.post_message(
            session_id=second["session_id"],
            body=server_app.MessageIn(message="Show my recent orders."),
            authorization=f"Bearer {first['token']}",
        ))

    assert caught.value.status_code == 403
    runner.assert_not_called()
