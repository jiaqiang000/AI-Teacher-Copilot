"""演示登录只能使用固定体验身份，并复用普通登录的安全会话。"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.auth.config import AuthConfig, set_auth_config
from app.gateway.auth.models import User
from app.gateway.auth_middleware import AuthMiddleware
from app.gateway.csrf_middleware import CSRFMiddleware
from app.gateway.routers import auth


@pytest.fixture
def demo_client(monkeypatch):
    monkeypatch.setenv("DEER_FLOW_AUTH_DISABLED", "0")
    set_auth_config(AuthConfig(jwt_secret="demo-test-secret-with-at-least-32-characters"))
    auth._login_attempts.clear()
    provider = MagicMock()
    provider.authenticate = AsyncMock(return_value=User(email="teacher@demo.com"))
    monkeypatch.setattr(auth, "get_local_provider", lambda: provider)
    session = AsyncMock()
    session.get.return_value = MagicMock(biz_type="teacher", biz_id="teacher_01")
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=session)
    context.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr("app.teacher_copilot.db.engine.get_session", lambda: context)
    app = FastAPI()
    app.include_router(auth.router)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(CSRFMiddleware)
    with TestClient(app, base_url="https://testserver") as client:
        yield client, provider, session
    auth._login_attempts.clear()


@pytest.mark.parametrize("role,biz_id", [("teacher", "teacher_01"), ("student", "stu_003")])
@pytest.mark.parametrize("remember", [True, False])
def test_demo_login_session(demo_client, role, biz_id, remember):
    client, provider, session = demo_client
    provider.authenticate.return_value = User(email=f"{role}@demo.com", token_version=3)
    session.get.return_value = MagicMock(biz_type=role, biz_id=biz_id)
    response = client.post("/api/v1/auth/login/demo", json={"role": role, "remember_me": remember})
    assert response.status_code == 200
    assert set(response.json()) == {"expires_in", "needs_setup"}
    assert response.json()["needs_setup"] is False
    cookies = response.headers.get_list("set-cookie")
    for name in ("access_token", "csrf_token"):
        cookie = next(c for c in cookies if c.startswith(f"{name}="))
        assert "Secure" in cookie
        assert ("Max-Age" in cookie) == remember
        if name == "access_token":
            assert "HttpOnly" in cookie
    assert provider.authenticate.call_args.args[0]["email"] == f"{role}@demo.com"


@pytest.mark.parametrize("payload", [{"role": "admin"}, {"role": "teacher", "email": "admin@example.com"}, {}])
def test_rejects_arbitrary_identity(demo_client, payload):
    client, provider, _ = demo_client
    assert client.post("/api/v1/auth/login/demo", json=payload).status_code == 422
    provider.authenticate.assert_not_called()


@pytest.mark.parametrize("problem", ["missing", "admin", "setup", "mapping", "database"])
def test_unavailable_demo_never_issues_session(demo_client, problem):
    client, provider, session = demo_client
    if problem == "missing":
        provider.authenticate.return_value = None
    elif problem == "admin":
        provider.authenticate.return_value.system_role = "admin"
    elif problem == "setup":
        provider.authenticate.return_value.needs_setup = True
    elif problem == "mapping":
        session.get.return_value = MagicMock(biz_type="student", biz_id="stu_003")
    else:
        session.get.side_effect = RuntimeError("database unavailable")
    response = client.post("/api/v1/auth/login/demo", json={"role": "teacher"})
    assert response.status_code == 503
    assert "access_token" not in response.cookies


def test_cross_origin_cannot_switch_session(demo_client):
    client, provider, _ = demo_client
    response = client.post("/api/v1/auth/login/demo", json={"role": "teacher"}, headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    provider.authenticate.assert_not_called()


def test_failures_are_rate_limited(demo_client):
    client, provider, _ = demo_client
    provider.authenticate.return_value = None
    for _ in range(5):
        assert client.post("/api/v1/auth/login/demo", json={"role": "teacher"}).status_code == 503
    assert client.post("/api/v1/auth/login/demo", json={"role": "teacher"}).status_code == 429
