import time
import uuid

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import delete, select

from app.config import get_settings
from app.db import SessionFactory
from app.models import (
    AdminAuditLog,
    AdapterType,
    ModelConnection,
    ModelConnectionVersion,
    ModelDefinition,
    ModelStatus,
    ModelType,
    RuntimeConfigState,
    RuntimeConfigVersion,
    User,
    UserRole,
)
from app.security import hash_password
from app.security_vault import encrypt_secret
from app.services import model_config


@pytest.fixture
async def admin_actor() -> dict:
    settings = get_settings()
    if not settings.secret_enc_key:
        settings.secret_enc_key = Fernet.generate_key().decode()

    username = f"test_cfg_admin_{int(time.time() * 1000) % 10**8}_{uuid.uuid4().hex[:6]}"
    password = "AdminPass123!"
    async with SessionFactory() as session:
        admin = User(
            username=username,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        admin_id = admin.id
    yield {"id": admin_id, "username": username, "password": password}
    async with SessionFactory() as session:
        await session.execute(delete(AdminAuditLog).where(AdminAuditLog.actor_id == admin_id))
        await session.execute(delete(User).where(User.id == admin_id))
        await session.commit()


async def _make_conn(slug: str, actor_id: uuid.UUID, *, adapter: AdapterType = AdapterType.MOCK) -> tuple[ModelConnection, ModelConnectionVersion]:
    async with SessionFactory() as session:
        conn = await model_config.create_connection(
            session,
            actor_id,
            slug=slug,
            vendor="mock",
            adapter_type=adapter,
            display_name=slug,
            base_url="http://localhost/mock",
            api_key="test-key",
        )
        await session.commit()
        await session.refresh(conn)
        version = await session.get(ModelConnectionVersion, conn.current_version_id)
        return conn, version


async def _make_models(session, conn, prefix: str) -> tuple[ModelDefinition, ModelDefinition]:
    """建一对文本/生图模型定义，供发布测试复用。"""
    text_def = ModelDefinition(
        slug=f"{prefix}_text",
        connection_id=conn.id,
        vendor_model_id="mock-text",
        display_name=f"{prefix} text",
        model_type=ModelType.TEXT,
    )
    image_def = ModelDefinition(
        slug=f"{prefix}_image",
        connection_id=conn.id,
        vendor_model_id="mock-image",
        display_name=f"{prefix} image",
        model_type=ModelType.IMAGE,
    )
    session.add_all([text_def, image_def])
    await session.commit()
    await session.refresh(text_def)
    await session.refresh(image_def)
    return text_def, image_def


async def test_publish_creates_version_and_advances_revision(admin_actor: AdminUser):
    async with SessionFactory() as session:
        conn, conn_version = await _make_conn("t_conn_pub_1", admin_actor["id"])
        text_def, image_def = await _make_models(session, conn, "t_pub")

        before_state = await model_config.get_state(session)
        version = await model_config.publish_version(
            session,
            admin_actor["id"],
            text_model_id=text_def.id,
            image_model_id=image_def.id,
            note="first",
            expected_revision=before_state.revision,
        )
        await session.commit()
        assert version.version_seq >= 1

        # current 指针已更新
        after_state = await model_config.get_state(session)
        assert after_state.current_version_id == version.id
        assert after_state.revision == before_state.revision + 1


async def test_publish_revision_conflict_rejected(admin_actor: AdminUser):
    async with SessionFactory() as session:
        conn, _ = await _make_conn("t_conn_conflict", admin_actor["id"])
        text_def, image_def = await _make_models(session, conn, "t_conf")

        before_state = await model_config.get_state(session)

        # 先发一次
        await model_config.publish_version(
            session,
            admin_actor["id"],
            text_model_id=text_def.id,
            image_model_id=image_def.id,
            expected_revision=before_state.revision,
        )
        await session.commit()

        # 第二次用旧的 expected_revision 应被拒
        with pytest.raises(model_config.RevisionConflict):
            await model_config.publish_version(
                session,
                admin_actor["id"],
                text_model_id=text_def.id,
                image_model_id=image_def.id,
                expected_revision=before_state.revision,
            )


async def test_rollback_creates_new_version_with_history(admin_actor: AdminUser):
    async with SessionFactory() as session:
        conn, _ = await _make_conn("t_conn_rb", admin_actor["id"])
        text_def, image_def = await _make_models(session, conn, "t_rb")

        before_state = await model_config.get_state(session)
        first = await model_config.publish_version(
            session,
            admin_actor["id"],
            text_model_id=text_def.id,
            image_model_id=image_def.id,
            note="v1",
            expected_revision=before_state.revision,
        )
        await session.commit()
        # 改一个模型再发一次
        image_def.vendor_model_id = "y"
        session.add(image_def)
        await session.flush()
        state2 = await model_config.get_state(session)
        second = await model_config.publish_version(
            session,
            admin_actor["id"],
            text_model_id=text_def.id,
            image_model_id=image_def.id,
            note="v2",
            expected_revision=state2.revision,
        )
        await session.commit()
        assert second.version_seq > first.version_seq

        # 回滚到 first
        state3 = await model_config.get_state(session)
        rolled = await model_config.rollback_to(
            session, admin_actor["id"], target_seq=first.version_seq, expected_revision=state3.revision
        )
        await session.commit()
        assert rolled.rolled_back_from == first.version_seq
        assert rolled.note.startswith("回滚")


async def test_slug_uniqueness(admin_actor: AdminUser):
    async with SessionFactory() as session:
        with pytest.raises(model_config.SlugTaken):
            await model_config.create_connection(
                session,
                admin_actor["id"],
                slug="t_dup_slug",
                vendor="mock",
                adapter_type=AdapterType.MOCK,
                display_name="first",
                base_url="http://localhost",
                api_key="k",
            )
            await session.commit()
            await model_config.create_connection(
                session,
                admin_actor["id"],
                slug="t_dup_slug",
                vendor="mock",
                adapter_type=AdapterType.MOCK,
                display_name="second",
                base_url="http://localhost",
                api_key="k",
            )


async def test_connection_version_immutable(admin_actor: AdminUser):
    async with SessionFactory() as session:
        conn, first = await _make_conn("t_conn_immut", admin_actor["id"])
        await session.commit()

        second = await model_config.new_connection_version(
            session, admin_actor["id"], conn.id, base_url="http://localhost/v2", api_key="k2"
        )
        await session.commit()
        assert second.version_seq == first.version_seq + 1
        # 旧版本号保留
        old = await session.get(ModelConnectionVersion, first.id)
        assert old.version_seq == first.version_seq
        assert old.base_url == first.base_url


async def test_revoke_marks_revoked(admin_actor: AdminUser):
    async with SessionFactory() as session:
        conn, version = await _make_conn("t_conn_revoke", admin_actor["id"])
        await model_config.revoke_connection_version(session, admin_actor["id"], version.id)
        await session.commit()
        again = await session.get(ModelConnectionVersion, version.id)
        assert again.revoked is True


async def test_admin_config_endpoints_require_admin(client: httpx.AsyncClient, credentials: dict):
    await client.post("/api/auth/register", json=credentials)
    r = await client.get("/api/admin/model-config/connections")
    assert r.status_code == 403
    r = await client.get("/api/admin/model-config/current")
    assert r.status_code == 403


async def test_admin_list_connections(admin_client, admin_actor):
    # admin_client fixtures is from test_admin_users; it has its own admin. We add a connection via this client too.
    r = await admin_client.get("/api/admin/model-config/connections")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_admin_publish_and_rollback_flow(admin_client):
    # 基于现有 runtime 版本（由 test_runtime_config 创建的文本+生图模型）做回滚 / 重新发布
    r = await admin_client.get("/api/admin/model-config/current")
    assert r.status_code == 200
    body = r.json()
    assert body["current_version_seq"] is not None
    initial_seq = body["current_version_seq"]
    initial_rev = body["revision"]

    r = await admin_client.post(
        "/api/admin/model-config/publish",
        json={
            "text_model_id": body["text_model_id"],
            "image_model_id": body["image_model_id"],
            "note": "test publish",
            "expected_revision": initial_rev,
        },
    )
    assert r.status_code == 200, r.text
    new_body = r.json()
    assert new_body["current_version_seq"] > initial_seq

    # 回滚到 initial_seq
    r = await admin_client.post(
        "/api/admin/model-config/rollback",
        json={"target_seq": initial_seq, "expected_revision": new_body["revision"]},
    )
    assert r.status_code == 200, r.text
    rb = r.json()
    assert rb["current_version_seq"] > new_body["current_version_seq"]


async def test_publish_with_stale_revision_returns_409(admin_client):
    r = await admin_client.get("/api/admin/model-config/current")
    body = r.json()

    stale_rev = body["revision"] - 1
    r = await admin_client.post(
        "/api/admin/model-config/publish",
        json={
            "text_model_id": body["text_model_id"],
            "image_model_id": body["image_model_id"],
            "note": "stale",
            "expected_revision": stale_rev,
        },
    )
    assert r.status_code == 409