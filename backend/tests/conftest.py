import uuid

import httpx
import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport
from sqlalchemy import delete, select

from app.config import get_settings
from app.db import SessionFactory
from app.main import app
from app.models import (
    AdminAuditLog,
    AdapterType,
    ModelConnection,
    ModelConnectionVersion,
    ModelDefinition,
    ModelType,
    RuntimeConfigState,
    RuntimeConfigVersion,
    User,
    UserRole,
)
from app.providers import MockImageProvider
from app.security import hash_password
from app.security_vault import encrypt_secret
from app.storage import ensure_bucket

# 测试账号统一此前缀，清理时只删这些行，避免误清开发库里的真实用户
TEST_USER_PREFIX = "test_"


async def _publish_mock_runtime() -> None:
    """清理旧的运行版本、连接、模型，并发布一份 Mock 运行配置。"""
    settings = get_settings()
    if not settings.secret_enc_key:
        # 测试期缺主密钥时随机生成，进程内有效
        settings.secret_enc_key = Fernet.generate_key().decode()

    async with SessionFactory() as session:
        await session.execute(delete(RuntimeConfigVersion))
        await session.execute(delete(RuntimeConfigState))
        await session.execute(delete(ModelDefinition))
        await session.execute(delete(ModelConnectionVersion))
        await session.execute(delete(ModelConnection))
        await session.commit()

        actor = await session.scalar(select(User).where(User.role == UserRole.ADMIN))
        if actor is None:
            actor = User(
                username="__test_runtime_admin",
                password_hash=hash_password("placeholder"),
                role=UserRole.ADMIN,
            )
            session.add(actor)
            await session.commit()
            await session.refresh(actor)

        conn = ModelConnection(
            slug="test-mock-conn",
            vendor="mock",
            adapter_type=AdapterType.MOCK,
            display_name="Test Mock Connection",
        )
        session.add(conn)
        await session.flush()
        conn_version = ModelConnectionVersion(
            connection_id=conn.id,
            version_seq=1,
            base_url="http://localhost/mock",
            encrypted_api_key=encrypt_secret("test-mock-key"),
            created_by=actor.id,
        )
        session.add(conn_version)
        await session.flush()
        conn.current_version_id = conn_version.id

        text_def = ModelDefinition(
            slug="test-mock-text",
            connection_id=conn.id,
            vendor_model_id="mock-text",
            display_name="Test Text",
            model_type=ModelType.TEXT,
        )
        image_def = ModelDefinition(
            slug="test-mock-image",
            connection_id=conn.id,
            vendor_model_id="mock-image",
            display_name="Test Image",
            model_type=ModelType.IMAGE,
        )
        session.add_all([text_def, image_def])
        await session.flush()

        from datetime import UTC, datetime

        version = RuntimeConfigVersion(
            version_seq=1,
            text_model_id=text_def.id,
            text_connection_version_id=conn_version.id,
            image_model_id=image_def.id,
            image_connection_version_id=conn_version.id,
            runtime_params={},
            test_summary={},
            note="test fixture",
            published_by=actor.id,
            published_at=datetime.now(UTC),
        )
        session.add(version)
        await session.flush()
        state = RuntimeConfigState(current_version_id=version.id, revision=1)
        session.add(state)
        await session.commit()


@pytest.fixture(scope="session", autouse=True)
def bucket():
    ensure_bucket()


@pytest.fixture(scope="session", autouse=True)
async def test_runtime_config():
    """session 级一次性发布 mock 运行配置。"""
    await _publish_mock_runtime()
    yield


@pytest.fixture(scope="session", autouse=True)
def corner_matting():
    settings = get_settings()
    original, settings.matting_provider = settings.matting_provider, "corner"
    yield
    settings.matting_provider = original


@pytest.fixture(scope="session", autouse=True)
def skip_ocr():
    settings = get_settings()
    original, settings.ocr_provider = settings.ocr_provider, "none"
    yield
    settings.ocr_provider = original


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def credentials() -> dict[str, str]:
    return {"username": f"{TEST_USER_PREFIX}{uuid.uuid4().hex[:10]}", "password": "secret123"}


@pytest.fixture
def other_credentials() -> dict[str, str]:
    return {"username": f"{TEST_USER_PREFIX}other-{uuid.uuid4().hex[:8]}", "password": "secret123"}


@pytest.fixture(autouse=True)
async def cleanup_users():
    yield
    async with SessionFactory() as session:
        await session.execute(delete(User).where(User.username.startswith(TEST_USER_PREFIX)))
        await session.execute(delete(AdminAuditLog).where(AdminAuditLog.target_kind == "user"))
        await session.commit()


__all__ = ["MockImageProvider"]