import pytest

from backend.app.models import ApiToken, User
from backend.app.routes import users as users_routes


@pytest.mark.anyio
async def test_token_issuance_rolls_back_when_audit_fails(client, db_sessionmaker, monkeypatch):
    with db_sessionmaker() as session:
        session.add(User(
            user_id="token-target",
            soeid="token-target",
            email="token-target@example.com",
            display_name="Token Target",
            password_hash="unused",
            role="user",
            is_active=True,
        ))
        session.commit()

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(users_routes, "log_changes", fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await client.post(
            "/project-manager/api/users/token-target/api-tokens",
            json={"name": "review token"},
        )

    with db_sessionmaker() as session:
        assert session.query(ApiToken).filter_by(user_id="token-target").count() == 0
