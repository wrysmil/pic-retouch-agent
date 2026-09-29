import uuid

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import delete

from app.config import get_settings
from app.db import SessionFactory
from app.main import app
from app.models import User
from app.providers import get_image_provider
from app.storage import ensure_bucket

# 测试账号统一此前缀，清理时只删这些行，避免误清开发库里的真实用户
TEST_USER_PREFIX = "test_"


@pytest.fixture(scope="session", autouse=True)
def bucket():
    ensure_bucket()


@pytest.fixture(scope="session", autouse=True)
def mock_provider():
    """测试一律走占位图实现，不受本机 IMAGE_PROVIDER 配置影响，也不产生调用费用。"""
    settings = get_settings()
    original, settings.image_provider = settings.image_provider, "mock"
    # get_image_provider 带 lru_cache，改完配置必须清掉，否则仍拿到旧实例
    get_image_provider.cache_clear()
    yield
    settings.image_provider = original
    get_image_provider.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def corner_matting():
    """测试强制四角抠图，避免 rembg 下载模型拖慢测试。"""
    settings = get_settings()
    original, settings.matting_provider = settings.matting_provider, "corner"
    yield
    settings.matting_provider = original


@pytest.fixture(scope="session", autouse=True)
def skip_ocr():
    """测试关掉文字识别，拆层不应依赖 OCR 引擎是否装得上。"""
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


@pytest.fixture(autouse=True)
async def cleanup_users():
    yield
    async with SessionFactory() as session:
        await session.execute(delete(User).where(User.username.startswith(TEST_USER_PREFIX)))
        await session.commit()