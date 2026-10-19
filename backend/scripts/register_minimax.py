"""登记 MiniMax 文本连接与 M 系列模型，并按需发布运行版本。

只读写本地数据库与加密存储，**不发起任何厂商调用**，因此不产生费用。
真实连通性请在后台「模型配置 → 连通性测试」按需触发。

用法：
    # 只登记连接与模型（MiniMax-M3.1-Flash 启用，MiniMax-M3 停用备用）
    python scripts/register_minimax.py

    # 同时发布运行版本：需要已有一个启用的生图模型
    python scripts/register_minimax.py --image-model-slug qwen-image-3.0

    # 保存连接时使用的密钥默认读 .env 的 MINIMAX_API_KEY
    python scripts/register_minimax.py --api-key <key> --base-url https://api.minimax.cn/v1

    # 思考深度默认 medium，可改成 low/medium/high/xhigh/max 后重跑（会更新能力声明）
    python scripts/register_minimax.py --reasoning-effort low

幂等：同名 slug 已存在时不重复创建，只补齐能力声明。
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
from app.services.model_runtime import _MINIMAX_REASONING_EFFORTS
from app.services.provider_url import validate_provider_url

CONNECTION_SLUG = "minimax-main"
DEFAULT_BASE_URL = "https://api.minimax.cn/v1"

# 规划用的默认思考深度。厂商对 M3.1-Flash 的默认档是 max：质量最好，但一轮规划
# 的思考 token 与耗时明显更高；交互式修图等的是工具调用，所以默认降到 medium。
DEFAULT_REASONING_EFFORT = "medium"

# param_schema 写入 ModelDefinition，运行时由 services/model_runtime.py 读取，
# 决定是否带上 reasoning_effort（reasoning_split 由 adapter 固定发送）。
MODELS: list[dict] = [
    {
        "slug": "MiniMax-M3.1-Flash",
        "vendor_model_id": "MiniMax-M3.1-Flash",
        "display_name": "MiniMax M3.1-Flash（规划）",
        "status": ModelStatus.ACTIVE,
        "effort_configurable": True,
    },
    {
        "slug": "MiniMax-M3",
        "vendor_model_id": "MiniMax-M3",
        "display_name": "MiniMax M3（备用）",
        "status": ModelStatus.DISABLED,
        # reasoning_effort 只对 M3.1-Flash 生效，M3 传了会被忽略
        "effort_configurable": False,
    },
]


def _schema_of(spec: dict, effort: str) -> dict:
    return {"reasoning_effort": effort} if spec["effort_configurable"] else {}


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
        vendor="minimax",
        adapter_type=AdapterType.MINIMAX,
        display_name="MiniMax 文本（M 系列）",
        base_url=base_url,
        api_key=api_key,
        extra={},
    )
    await session.flush()
    print(f"[+] 已创建连接：{slug} -> {base_url}")
    return conn


async def _ensure_model(
    session, actor_id, conn: ModelConnection, spec: dict, effort: str
) -> ModelDefinition:
    param_schema = _schema_of(spec, effort)
    existing = await session.scalar(
        select(ModelDefinition).where(ModelDefinition.slug == spec["slug"])
    )
    if existing is not None:
        # 思考深度可能被调整过，这里补齐 schema，但不动启用状态
        if existing.param_schema != param_schema:
            existing.param_schema = param_schema
            print(f"[~] 已更新模型参数声明：{spec['slug']} -> {param_schema}")
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
        model_type=ModelType.TEXT,
        param_schema=param_schema,
    )
    # create_model 在同类已有启用模型时会把新模型置为停用；这里按脚本声明收敛状态
    if spec["status"] is ModelStatus.ACTIVE and model.status is not ModelStatus.ACTIVE:
        await model_config.activate_model(session, actor_id, model.id)
    print(f"[+] 已登记模型：{spec['slug']}（{spec['status'].value}）{param_schema or ''}")
    return model


async def register(
    *, api_key: str, base_url: str, image_model_slug: str | None, effort: str
) -> int:
    settings = get_settings()
    if not settings.secret_enc_key:
        print("缺少 SECRET_ENC_KEY，无法加密保存厂商密钥（见 .env.example）")
        return 1

    try:
        base_url = validate_provider_url(base_url)
    except Exception as exc:  # ProviderUrlRejected
        print(f"Base URL 未通过白名单校验：{exc}")
        print("请把 api.minimax.cn 加入 ALLOWED_PROVIDER_HOSTS 后重试")
        return 1

    async with SessionFactory() as session:
        actor_id = await _admin_id(session)

        conn = await _ensure_connection(
            session, actor_id, slug=CONNECTION_SLUG, base_url=base_url, api_key=api_key
        )

        text_models: dict[str, ModelDefinition] = {}
        for spec in MODELS:
            text_models[spec["slug"]] = await _ensure_model(
                session, actor_id, conn, spec, effort
            )

        await session.commit()

        target = text_models["MiniMax-M3.1-Flash"]
        await session.refresh(target)
        print(
            f"\n文本槽位将使用：{target.display_name}"
            f"（vendor_model_id={target.vendor_model_id}，"
            f"reasoning_effort={target.param_schema.get('reasoning_effort', '厂商默认')}）"
        )

        if image_model_slug is None:
            print(
                "未指定生图模型，跳过发布。可在后台「模型配置 → 运行版本」"
                "选择文本 + 生图模型后发布；\n"
                "或重跑：python scripts/register_minimax.py "
                "--image-model-slug <生图模型 slug>"
            )
            return 0

        image_model = await session.scalar(
            select(ModelDefinition).where(
                ModelDefinition.slug == image_model_slug,
                ModelDefinition.model_type == ModelType.IMAGE,
            )
        )
        if image_model is None:
            print(f"找不到生图模型 slug={image_model_slug}，已登记连接与文本模型，但未发布运行版本")
            return 1

        # 文本与生图各自只允许一个启用：发布前把两个槽位都收敛到目标模型
        if target.status is not ModelStatus.ACTIVE:
            await model_config.activate_model(session, actor_id, target.id)
        if image_model.status is not ModelStatus.ACTIVE:
            await model_config.activate_model(session, actor_id, image_model.id)
        await session.commit()

        state = await model_config.get_state(session)
        version = await model_config.publish_version(
            session,
            actor_id,
            text_model_id=target.id,
            image_model_id=image_model.id,
            note="接入 MiniMax M3.1-Flash 文本规划",
            expected_revision=state.revision,
        )
        await session.commit()
        await session.refresh(image_model)
        print(
            f"\n[+] 已发布运行版本 v{version.version_seq}："
            f"文本={target.display_name}，生图={image_model.display_name}"
        )
        print("新任务将使用该版本；连通性测试可在后台按需触发（会产生调用费用）。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="登记 MiniMax 文本连接与 M 系列模型")
    parser.add_argument(
        "--api-key",
        default=None,
        help="MiniMax API Key；默认读 .env 的 MINIMAX_API_KEY",
    )
    parser.add_argument("--base-url", default=None, help=f"默认 {DEFAULT_BASE_URL}")
    parser.add_argument(
        "--image-model-slug",
        default=None,
        help="已登记的生图模型 slug；给了就直接发布运行版本",
    )
    parser.add_argument(
        "--reasoning-effort",
        default=DEFAULT_REASONING_EFFORT,
        choices=list(_MINIMAX_REASONING_EFFORTS),
        help=f"M3.1-Flash 的思考深度，默认 {DEFAULT_REASONING_EFFORT}（厂商默认是 max）",
    )
    args = parser.parse_args()

    settings = get_settings()
    api_key = (args.api_key or settings.minimax_api_key).strip()
    if not api_key:
        print("未提供 API Key：请设置 .env 的 MINIMAX_API_KEY 或传 --api-key")
        return 1

    base_url = args.base_url or settings.minimax_base_url or DEFAULT_BASE_URL
    return asyncio.run(
        register(
            api_key=api_key,
            base_url=base_url,
            image_model_slug=args.image_model_slug,
            effort=args.reasoning_effort,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
