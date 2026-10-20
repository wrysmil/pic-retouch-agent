import httpx

from app.security import SESSION_COOKIE


async def test_register_sets_session_cookie(client: httpx.AsyncClient, credentials):
    response = await client.post("/api/auth/register", json=credentials)

    assert response.status_code == 201
    assert response.json()["username"] == credentials["username"]
    assert SESSION_COOKIE in response.cookies


async def test_register_rejects_duplicate_username(client: httpx.AsyncClient, credentials):
    await client.post("/api/auth/register", json=credentials)

    response = await client.post("/api/auth/register", json=credentials)

    assert response.status_code == 409


async def test_login_then_me_returns_current_user(client: httpx.AsyncClient, credentials):
    await client.post("/api/auth/register", json=credentials)
    await client.post("/api/auth/logout")

    await client.post("/api/auth/login", json=credentials)
    response = await client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["username"] == credentials["username"]


async def test_login_rejects_wrong_password(client: httpx.AsyncClient, credentials):
    await client.post("/api/auth/register", json=credentials)

    response = await client.post(
        "/api/auth/login", json={**credentials, "password": "wrong-password"}
    )

    assert response.status_code == 401


async def test_me_requires_session(client: httpx.AsyncClient):
    response = await client.get("/api/auth/me")

    assert response.status_code == 401


async def test_logout_clears_session(client: httpx.AsyncClient, credentials):
    await client.post("/api/auth/register", json=credentials)

    await client.post("/api/auth/logout")

    assert (await client.get("/api/auth/me")).status_code == 401


async def test_admin_session_is_isolated_from_workbench_session(
    client: httpx.AsyncClient,
    credentials,
    admin_credentials,
):
    """同一浏览器登录后台后，工作台仍保持原普通用户会话。"""
    await client.post("/api/auth/register", json=credentials)

    response = await client.post(
        "/api/auth/admin/login",
        json={
            "username": admin_credentials["username"],
            "password": admin_credentials["password"],
        },
    )

    assert response.status_code == 200
    assert "admin_session" in response.cookies
    assert (await client.get("/api/auth/me")).json()["username"] == credentials["username"]
    admin_me = await client.get("/api/auth/admin/me")
    assert admin_me.json()["username"] == admin_credentials["username"]
    assert (await client.get("/api/admin/users")).status_code == 200


async def test_admin_logout_keeps_workbench_session(
    client: httpx.AsyncClient,
    credentials,
    admin_credentials,
):
    await client.post("/api/auth/register", json=credentials)
    await client.post(
        "/api/auth/admin/login",
        json={
            "username": admin_credentials["username"],
            "password": admin_credentials["password"],
        },
    )

    await client.post("/api/auth/admin/logout")

    assert (await client.get("/api/auth/admin/me")).status_code == 401
    assert (await client.get("/api/auth/me")).json()["username"] == credentials["username"]


async def test_admin_login_rejects_regular_user_without_replacing_workbench_session(
    client: httpx.AsyncClient,
    credentials,
):
    await client.post("/api/auth/register", json=credentials)

    response = await client.post("/api/auth/admin/login", json=credentials)

    assert response.status_code == 403
    assert "admin_session" not in response.cookies
    assert (await client.get("/api/auth/me")).json()["username"] == credentials["username"]


async def test_register_validates_username_charset(client: httpx.AsyncClient):
    response = await client.post(
        "/api/auth/register", json={"username": "bad name!", "password": "secret123"}
    )

    assert response.status_code == 422


async def test_validation_errors_are_localized(client: httpx.AsyncClient):
    response = await client.post(
        "/api/auth/register", json={"username": "ab", "password": "123"}
    )

    assert response.status_code == 422
    messages = [error["msg"] for error in response.json()["detail"]]
    assert "用户名至少需要 3 个字符" in messages
    assert "密码至少需要 6 个字符" in messages
