"""登记 mock 连接与模型，并发布一个完全离线的运行版本。

只读写本地数据库与加密存储，**不发起任何厂商调用**，因此不产生费用。

登记两条连接：
- ``mock-image``    适配器 mock      → 生图 / 图编辑 / 超分走本地占位图
- ``mock-planner``  适配器 openai_compat → 文本规划走本地 mock 规划模型
  （scripts/mock_llm_server.py，默认 http://127.0.0.1:7300/v1）

本地地址需要白名单放行：把 .env 的 ALLOWED_PROVIDER_HOSTS 设成 ``allow-localhost``。

用法：
    python scripts/register_mock.py
    python scripts/register_mock.py --planner-url http://127.0.0.1:7300/v1

幂等：同名 slug 已存在时不重复创建，只补齐缺失项。
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db import SessionFactory
from app.models import (
    AdapterType,
    ModelConnection,
    ModelDefinition,
    ModelStatus,
    ModelType,
    User,
    UserRole,
)
from app.services import model_config
from app.services.provider_url import MOCK_BASE_URL, validate_connection_url

IMAGE_CONNECTION_SLUG = "mock-image"
PLANNER_CONNECTION_SLUG = "mock-planner"
IMAGE_MODEL_SLUG = "mock-image"
PLANNER_MODEL_SLUG = "mock-planner"
DEFAULT_PLANNER_URL = "http://127.0.0.1:7300/v1"


async def _admin_id(session) -> object:
    """取一个管理员作为审计主体；没有管理员时提示先跑 init_admin.py。"""
    admin = await session.scalar(select(User).where(User.role == UserRole.ADMIN))
    if admin is None:
        raise SystemExit(
            "库中还没有管理员账号，请先执行：python scripts/init_admin.py create <name> <password>"
        )
    return admin.id


async def _ensure_connection(
    session, actor_id, *, slug: str, vendor: str, adapter: AdapterType, name: str, url: str
) -> ModelConnection:
    existing = await session.scalar(select(ModelConnection).where(ModelConnection.slug == slug))
    if existing is not None:
        print(f"[=] 连接已存在：{slug}（不再改动其地址/密钥）")
        return existing

    conn = await model_config.create_connection(
        session,
        actor_id,
        slug=slug,
        vendor=vendor,
        adapter_type=adapter,
        display_name=name,
        base_url=url,
        api_key="mock",
        extra={},
    )
    await session.flush()
    print(f"[+] 已创建连接：{slug}（{adapter.value}）-> {url}")
    return conn


async def _ensure_model(
    session, actor_id, conn: ModelConnection, *, slug: str, model_type: ModelType, name: str
) -> ModelDefinition:
    existing = await session.scalar(select(ModelDefinition).where(ModelDefinition.slug == slug))
    if existing is not None:
        print(f"[=] 模型已存在：{slug}")
        return existing

    model = await model_config.create_model(
        session,
        actor_id,
        slug=slug,
        connection_id=conn.id,
        vendor_model_id=slug,
        display_name=name,
        model_type=model_type,
        param_schema={},
    )
    if model.status is not ModelStatus.ACTIVE:
        await model_config.activate_model(session, actor_id, model.id)
    print(f"[+] 已登记模型：{slug}（{model_type.value}，已启用）")
    return model


async def register(planner_url: str) -> int:
    # mock 生图连接不连厂商，地址与密钥都可留空，不受白名单约束；
    # 本地规划桩是真实地址（http），仍要过白名单，开发期需 ALLOWED_PROVIDER_HOSTS=allow-localhost
    try:
        validate_connection_url("mock", MOCK_BASE_URL)
        validate_connection_url("openai_compat", planner_url)
    except Exception as exc:  # ProviderUrlRejected
        print(f"Base URL 未通过白名单校验：{exc}")
        print("本地规划桩需要把 .env 的 ALLOWED_PROVIDER_HOSTS 设成 allow-localhost 后重试")
        return 1

    async with SessionFactory() as session:
        actor_id = await _admin_id(session)

        image_conn = await _ensure_connection(
            session,
            actor_id,
            slug=IMAGE_CONNECTION_SLUG,
            vendor="mock",
            adapter=AdapterType.MOCK,
            name="Mock 本地生图（占位图）",
            url=MOCK_BASE_URL,
        )
        planner_conn = await _ensure_connection(
            session,
            actor_id,
            slug=PLANNER_CONNECTION_SLUG,
            vendor="mock",
            adapter=AdapterType.OPENAI_COMPAT,
            name="Mock 本地规划模型（OpenAI 兼容桩）",
            url=planner_url,
        )
        await session.commit()

        image_model = await _ensure_model(
            session,
            actor_id,
            image_conn,
            slug=IMAGE_MODEL_SLUG,
            model_type=ModelType.IMAGE,
            name="Mock 生图模型（本地占位图）",
        )
        planner_model = await _ensure_model(
            session,
            actor_id,
            planner_conn,
            slug=PLANNER_MODEL_SLUG,
            model_type=ModelType.TEXT,
            name="Mock 规划模型（本地桩）",
        )
        await session.commit()

        # 同一类型只允许一个启用：把 mock 模型提到启用位，原先的真实模型自动停用
        for model in (image_model, planner_model):
            await session.refresh(model)
            if model.status is not ModelStatus.ACTIVE:
                await model_config.activate_model(session, actor_id, model.id)
        await session.commit()

        state = await model_config.get_state(session)
        version = await model_config.publish_version(
            session,
            actor_id,
            text_model_id=planner_model.id,
            image_model_id=image_model.id,
            note="mock 模式：本地占位图 + 本地规划模型桩",
            expected_revision=state.revision,
        )
        await session.commit()
        print(
            f"\n[+] 已发布运行版本 v{version.version_seq}："
            f"文本={planner_model.display_name}，生图={image_model.display_name}"
        )
        print("所有厂商调用都被本地桩接管，不产生任何费用。")
        print("注意：原先启用的真实模型已被自动停用，需要时在后台重新启用即可。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="登记 mock 连接与模型并发布运行版本")
    parser.add_argument(
        "--planner-url",
        default=DEFAULT_PLANNER_URL,
        help=f"本地 mock 规划模型的 base URL，默认 {DEFAULT_PLANNER_URL}",
    )
    args = parser.parse_args()
    return asyncio.run(register(args.planner_url))


if __name__ == "__main__":
    raise SystemExit(main())
