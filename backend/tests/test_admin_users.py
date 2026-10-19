import uuid

import httpx
from sqlalchemy import select

from app.db import SessionFactory
from app.models import AdminAuditLog


async def test_unauthenticated_cannot_access_admin(client: httpx.AsyncClient):
    response = await client.get("/api/admin/users")
    assert response.status_code == 401


async def test_normal_user_forbidden(client: httpx.AsyncClient, credentials: dict):
    await client.post("/api/auth/register", json=credentials)
    response = await client.get("/api/admin/users")
    assert response.status_code == 403


async def test_admin_can_list_users(admin_client: httpx.AsyncClient):
    response = await admin_client.get("/api/admin/users")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body and "total" in body


async def test_admin_can_create_user(admin_client: httpx.AsyncClient):
    username = f"test_created_{uuid.uuid4().hex[:8]}"
    response = await admin_client.post(
        "/api/admin/users",
        json={"username": username, "password": "secret123", "role": "user", "is_active": True},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == username
    assert body["role"] == "user"
    assert body["is_active"] is True


async def test_admin_create_duplicate_returns_409(admin_client: httpx.AsyncClient):
    username = f"test_dup_{uuid.uuid4().hex[:8]}"
    body = {"username": username, "password": "secret123", "role": "user"}
    first = await admin_client.post("/api/admin/users", json=body)
    assert first.status_code == 201
    second = await admin_client.post("/api/admin/users", json=body)
    assert second.status_code == 409


async def test_admin_role_change_writes_audit(admin_client: httpx.AsyncClient):
    create_resp = await admin_client.post(
        "/api/admin/users",
        json={"username": f"test_promote_{uuid.uuid4().hex[:8]}", "password": "secret123", "role": "user"},
    )
    assert create_resp.status_code == 201
    target_id = create_resp.json()["id"]

    resp = await admin_client.patch(
        f"/api/admin/users/{target_id}/role", json={"role": "admin"}
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"

    async with SessionFactory() as session:
        logs = await session.scalars(
            select(AdminAuditLog).where(
                AdminAuditLog.target_id == uuid.UUID(target_id),
                AdminAuditLog.action == "user.role_changed",
            )
        )
        rows = list(logs)
        assert rows, "应有一条角色变更审计"
        assert rows[0].changes == {"from": "user", "to": "admin"}


async def test_disable_self_admin_rejected(admin_client: httpx.AsyncClient, admin_credentials: dict):
    """停用「最后一个启用管理员」必须被拒，自己也在保护范围内。

    服务端规则是"必须保留至少一个启用管理员"，不是"不能停用自己"：
    只要还有别的启用管理员，停用自己是被允许的。所以这里先把其它启用管理员停掉，
    让当前账号成为唯一一个，再验证 409。
    """
    listing = await admin_client.get("/api/admin/users", params={"role": "admin"})
    assert listing.status_code == 200
    for item in listing.json()["items"]:
        if not item["is_active"] or item["id"] == str(admin_credentials["id"]):
            continue
        stopped = await admin_client.patch(
            f"/api/admin/users/{item['id']}/active", json={"is_active": False}
        )
        assert stopped.status_code == 200, stopped.text

    resp = await admin_client.patch(
        f"/api/admin/users/{admin_credentials['id']}/active", json={"is_active": False}
    )
    assert resp.status_code == 409


async def test_disable_one_of_two_admins_succeeds(admin_client: httpx.AsyncClient):
    second = await admin_client.post(
        "/api/admin/users",
        json={
            "username": f"test_admin_other_{uuid.uuid4().hex[:8]}",
            "password": "secret123",
            "role": "admin",
        },
    )
    assert second.status_code == 201

    resp = await admin_client.patch(
        f"/api/admin/users/{second.json()['id']}/active", json={"is_active": False}
    )
    assert resp.status_code == 200


async def test_disable_then_login_rejected(admin_client: httpx.AsyncClient):
    create = await admin_client.post(
        "/api/admin/users",
        json={
            "username": f"test_disable_{uuid.uuid4().hex[:8]}",
            "password": "secret123",
            "role": "user",
        },
    )
    target_id = create.json()["id"]
    username = create.json()["username"]

    disable = await admin_client.patch(
        f"/api/admin/users/{target_id}/active", json={"is_active": False}
    )
    assert disable.status_code == 200

    fresh = httpx.AsyncClient(transport=admin_client._transport, base_url="http://test")
    try:
        response = await fresh.post(
            "/api/auth/login", json={"username": username, "password": "secret123"}
        )
        assert response.status_code == 403
    finally:
        await fresh.aclose()


async def test_reset_password_invalidates_session(admin_client: httpx.AsyncClient, admin_credentials: dict):
    username = admin_credentials["username"]
    password = admin_credentials["password"]
    admin_id = admin_credentials["id"]
    victim = httpx.AsyncClient(transport=admin_client._transport, base_url="http://test")
    try:
        login = await victim.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
        assert login.status_code == 200
        me = await victim.get("/api/auth/me")
        assert me.status_code == 200

        reset = await admin_client.post(
            f"/api/admin/users/{admin_id}/reset-password",
            json={"new_password": "NewPass456!"},
        )
        assert reset.status_code == 200

        me2 = await victim.get("/api/auth/me")
        assert me2.status_code == 401
    finally:
        await victim.aclose()


async def test_revoke_sessions_bumps_version(admin_client: httpx.AsyncClient):
    create = await admin_client.post(
        "/api/admin/users",
        json={
            "username": f"test_revoke_{uuid.uuid4().hex[:8]}",
            "password": "secret123",
            "role": "user",
        },
    )
    target_id = create.json()["id"]
    initial_version = create.json()["auth_version"]

    resp = await admin_client.post(f"/api/admin/users/{target_id}/revoke-sessions")
    assert resp.status_code == 200
    assert resp.json()["auth_version"] == initial_version + 1


async def test_user_list_filters(admin_client: httpx.AsyncClient):
    user_name = f"test_filter_user_{uuid.uuid4().hex[:6]}"
    admin_name = f"test_filter_admin_{uuid.uuid4().hex[:6]}"
    await admin_client.post(
        "/api/admin/users",
        json={"username": user_name, "password": "secret123", "role": "user"},
    )
    await admin_client.post(
        "/api/admin/users",
        json={"username": admin_name, "password": "secret123", "role": "admin"},
    )

    r = await admin_client.get("/api/admin/users", params={"role": "user"})
    assert r.status_code == 200
    assert all(item["role"] == "user" for item in r.json()["items"])

    r = await admin_client.get("/api/admin/users", params={"keyword": "test_filter"})
    assert r.status_code == 200
    assert all(item["username"].startswith("test_filter") for item in r.json()["items"])


async def test_get_me_returns_role_and_active(client: httpx.AsyncClient, credentials: dict):
    await client.post("/api/auth/register", json=credentials)
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["role"] == "user"
    assert body["is_active"] is True