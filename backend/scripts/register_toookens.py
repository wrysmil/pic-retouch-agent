"""登记 Toookens 生图连接与 qwen-image 模型，并按需发布运行版本。

只读写本地数据库与加密存储，**不发起任何厂商调用**，因此不产生费用。
真实连通性请在后台「模型配置 → 连通性测试」按需触发。

用法：
    # 只登记连接与模型（qwen-image-3.0 启用，qwen-image-2.0 停用备用）
    python scripts/register_toookens.py

    # 同时发布运行版本：需要已有一个启用的文本模型
    python scripts/register_toookens.py --text-model-slug qwen-plus

    # 保存连接时使用的密钥默认读 .env 的 TOOOKENS_API_KEY
    python scripts/register_toookens.py --api-key <key> --base-url https://api.toookens.com/v1

幂等：同名 slug 已存在时不重复创建，只补齐缺失项。
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.config import get_settings
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
from app.services.provider_url import validate_provider_url

CONNECTION_SLUG = "toookens-main"
DEFAULT_BASE_URL = "https://api.toookens.com/v1"

# 能力描述写入 ModelDefinition.param_schema，运行时由 providers/toookens.py 读取。
# 数值来自 toookens 模型详情接口的 image_size_capabilities / supported_operation_modes，
# 改厂商配置时同步更新这里即可，不必改适配器代码。
MODELS: list[dict] = [
    {
        "slug": "qwen-image-3.0",
        "vendor_model_id": "qwen-image-3.0",
        "display_name": "通义千问 Qwen-Image-3.0（Toookens）",
        "status": ModelStatus.ACTIVE,
        "param_schema": {
            "default_size": "auto",
            "supported_sizes": ["1024x1024", "1536x1024", "1024x1536", "2048x2048"],
            "supports_custom_size": True,
            "custom_size_constraints": {
                "minimum_pixels": 262144,
                "maximum_pixels": 4194304,
                "aspect_ratio_min": 0.125,
                "aspect_ratio_max": 8.0,
            },
            "supported_operation_modes": [
                "text_to_image",
                "image_to_image",
                "multi_reference_image",
            ],
            "supports_multi_reference_image": True,
        },
    },
    {
        "slug": "qwen-image-2.0",
        "vendor_model_id": "qwen-image-2.0",
        "display_name": "通义千问 Qwen-Image-2.0（Toookens）",
        "status": ModelStatus.DISABLED,
        "param_schema": {
            "default_size": "1024x1024",
            "supported_sizes": ["1024x1024"],
            "supports_custom_size": False,
            "supported_operation_modes": ["text_to_image", "image_to_image"],
            "supports_multi_reference_image": False,
        },
    },
]


async def _admin_id(session) -> "object":
    """取一个管理员作为审计主体；没有管理员时提示先跑 init_admin.py。"""
    admin = await session.scalar(select(User).where(User.role == UserRole.ADMIN))
    if admin is None:
        raise SystemExit(
            "库中还没有管理员账号，请先执行：python scripts/init_admin.py create <name> <password>"
        )
    return admin.id


async def _ensure_connection(
    session, actor_id, *, slug: str, base_url: str, api_key: str
) -> ModelConnection:
    existing = await session.scalar(select(ModelConnection).where(ModelConnection.slug == slug))
    if existing is not None:
        print(f"[=] 连接已存在：{slug}（不再改动其地址/密钥，如需换密钥请在后台新增连接版本）")
        return existing

    conn = await model_config.create_connection(
        session,
        actor_id,
        slug=slug,
        vendor="toookens",
        adapter_type=AdapterType.TOOOKENS,
        display_name="Toookens 生图（qwen-image）",
        base_url=base_url,
        api_key=api_key,
        extra={},
    )
    await session.flush()
    print(f"[+] 已创建连接：{slug} -> {base_url}")
    return conn


async def _ensure_model(session, actor_id, conn: ModelConnection, spec: dict) -> ModelDefinition:
    existing = await session.scalar(
        select(ModelDefinition).where(ModelDefinition.slug == spec["slug"])
    )
    if existing is not None:
        # 能力描述可能随厂商调整，这里补齐 schema，但不动启用状态
        if existing.param_schema != spec["param_schema"]:
            existing.param_schema = spec["param_schema"]
            print(f"[~] 已更新模型能力声明：{spec['slug']}")
        else:
            print(f"[=] 模型已存在：{spec['slug']}")
        return existing

    model = await model_config.create_model(
        session,
        actor_id,
        slug=spec["slug"],
        connection_id=conn.id,
        vendor_model_id=spec["vendor_model_id"],
        display_name=spec["display_name"],
        model_type=ModelType.IMAGE,
        param_schema=spec["param_schema"],
    )
    # create_model 在同类已有启用模型时会把新模型置为停用；这里按脚本声明收敛状态
    if spec["status"] is ModelStatus.ACTIVE and model.status is not ModelStatus.ACTIVE:
        await model_config.activate_model(session, actor_id, model.id)
    print(f"[+] 已登记模型：{spec['slug']}（{spec['status'].value}）")
    return model


async def register(*, api_key: str, base_url: str, text_model_slug: str | None) -> int:
    settings = get_settings()
    if not settings.secret_enc_key:
        print("缺少 SECRET_ENC_KEY，无法加密保存厂商密钥（见 .env.example）")
        return 1

    try:
        base_url = validate_provider_url(base_url)
    except Exception as exc:  # ProviderUrlRejected
        print(f"Base URL 未通过白名单校验：{exc}")
        print("请把 api.toookens.com 加入 ALLOWED_PROVIDER_HOSTS 后重试")
        return 1

    async with SessionFactory() as session:
        actor_id = await _admin_id(session)

        conn = await _ensure_connection(
            session, actor_id, slug=CONNECTION_SLUG, base_url=base_url, api_key=api_key
        )

        image_models: dict[str, ModelDefinition] = {}
        for spec in MODELS:
            image_models[spec["slug"]] = await _ensure_model(session, actor_id, conn, spec)

        await session.commit()

        target = image_models["qwen-image-3.0"]
        await session.refresh(target)
        print(
            f"\n生图槽位将使用：{target.display_name}"
            f"（vendor_model_id={target.vendor_model_id}）"
        )

        if text_model_slug is None:
            print(
                "未指定文本模型，跳过发布。可在后台「模型配置 → 运行版本」"
                "选择文本 + 生图模型后发布；\n"
                "或重跑：python scripts/register_toookens.py "
                "--text-model-slug <文本模型 slug>"
            )
            return 0

        text_model = await session.scalar(
            select(ModelDefinition).where(
                ModelDefinition.slug == text_model_slug,
                ModelDefinition.model_type == ModelType.TEXT,
            )
        )
        if text_model is None:
            print(f"找不到文本模型 slug={text_model_slug}，已登记连接与生图模型，但未发布运行版本")
            return 1

        # 同一类型只允许一个启用：确认生图槽位的模型处于启用态
        await session.refresh(target)
        if target.status is not ModelStatus.ACTIVE:
            await model_config.activate_model(session, actor_id, target.id)
            await session.commit()

        state = await model_config.get_state(session)
        version = await model_config.publish_version(
            session,
            actor_id,
            text_model_id=text_model.id,
            image_model_id=target.id,
            note="接入 Toookens qwen-image-3.0 生图",
            expected_revision=state.revision,
        )
        await session.commit()
        print(
            f"\n[+] 已发布运行版本 v{version.version_seq}："
            f"文本={text_model.display_name}，生图={target.display_name}"
        )
        print("新任务将使用该版本；连通性测试可在后台按需触发（会产生调用费用）。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="登记 Toookens 生图连接与 qwen-image 模型")
    parser.add_argument(
        "--api-key",
        default=None,
        help="Toookens API Key；默认读 .env 的 TOOOKENS_API_KEY",
    )
    parser.add_argument("--base-url", default=None, help=f"默认 {DEFAULT_BASE_URL}")
    parser.add_argument(
        "--text-model-slug",
        default=None,
        help="已登记的文本模型 slug；给了就直接发布运行版本",
    )
    args = parser.parse_args()

    settings = get_settings()
    api_key = (args.api_key or settings.toookens_api_key).strip()
    if not api_key:
        print("未提供 API Key：请设置 .env 的 TOOOKENS_API_KEY 或传 --api-key")
        return 1

    base_url = args.base_url or settings.toookens_base_url or DEFAULT_BASE_URL
    return asyncio.run(
        register(api_key=api_key, base_url=base_url, text_model_slug=args.text_model_slug)
    )


if __name__ == "__main__":
    sys.exit(main())
