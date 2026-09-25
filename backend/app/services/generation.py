"""
文生图执行服务层。

提供图片生成任务的执行逻辑，包括调用 AI 模型、保存结果等。
该模块由 Worker 进程调用，不处理 HTTP 请求。
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.models.asset import AssetKind, AssetSource
from app.models.tool_run import RunStatus, ToolRun
from app.providers import GenerateRequest, ProviderError, get_image_provider
from app.ratios import Ratio, size_of
from app.services import assets, runs

# 工具标识常量
TOOL = "generate_image"

logger = logging.getLogger(__name__)


async def _references(session: AsyncSession, run: ToolRun) -> list[bytes]:
    """
    获取参考图片的二进制数据。

    - **session**: 数据库会话
    - **run**: 任务记录（包含 reference_asset_ids 参数）
    - **返回**: 参考图片的二进制数据列表
    - **抛出**: ProviderError 参考图不存在
    """
    result: list[bytes] = []
    for raw in run.params.get("reference_asset_ids") or []:
        asset = await assets.get_for_user(session, run.user_id, uuid.UUID(raw))
        if asset is None:
            raise ProviderError("参考图不存在")
        result.append(await storage.get(asset.storage_key))
    return result


async def execute(session: AsyncSession, run: ToolRun) -> None:
    """
    执行文生图任务。

    流程：
    1. 调用 runs.start 标记任务开始（status=running, progress=5）
    2. 从任务参数中提取生成参数（prompt、ratio、count 等）
    3. 如有参考图，从对象存储读取并传给模型
    4. 调用 AI 模型生成图片（通过 provider）
    5. 将生成的图片保存到对象存储，转换为素材记录
    6. 调用 runs.finish 标记任务完成（status=completed, result=asset_ids）

    - **session**: 数据库会话
    - **run**: 任务记录（从 runs.create 创建，status=pending）
    """
    # 定义进度回调函数，供 AI provider 在生成过程中调用
    # 闭包特性：可以直接访问外层的 session 和 run 变量
    async def on_progress(progress: int, stage: str) -> None:
        """
        进度回调函数。

        - **progress**: 进度百分比（0-100）
        - **stage**: 当前阶段描述（如 "正在加载模型"、"正在生成"）
        """
        await runs.report(session, run, progress, stage)

    try:
        # 1. 标记任务开始执行
        await runs.start(session, run)

        # 2. 解析生成参数
        width, height = size_of(Ratio(run.params["ratio"]))  # 将比例转为具体像素尺寸

        # 3. 构建生成请求
        request = GenerateRequest(
            prompt=run.params["prompt"],           # 图片描述文本
            width=width,                            # 输出宽度
            height=height,                          # 输出高度
            count=run.params["count"],              # 生成数量
            negative_prompt=run.params.get("negative_prompt"),  # 负面提示词
            seed=run.params.get("seed"),            # 随机种子
            references=await _references(session, run),  # 参考图片二进制数据
        )

        # 4. 调用 AI 模型生成图片
        # provider 通过 on_progress 回调报告进度
        images = await get_image_provider().generate(request, on_progress)

        # 5. 将生成的图片保存为素材
        """
│  AI 返回的 images (原始数据)                               │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                    │
│  │ data │ │ data │ │ data │ │ data │                    │
│  └──────┘ └──────┘ └──────┘ └──────┘                    │
│        │        │        │        │                       │
│        ▼        ▼        ▼        ▼                       │
│  ┌─────────────────────────────────────┐                  │
│  │  assets.create_from_bytes()         │                  │
│  │  1. 上传到对象存储（OSS/S3）         │                  │
│  │  2. 写入数据库元信息                 │                  │
│  │  3. 返回 Asset 记录                 │                  │
│  └─────────────────────────────────────┘                  │
│        │        │        │        │                       │
│        ▼        ▼        ▼        ▼                       │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                    │
│  │asset1│ │asset2│ │asset3│ │asset4│  ← 可以访问的素材 │
│  └──────┘ └──────┘ └──────┘ └──────┘                    │
└─────────────────────────────────────────────────────────────┘
        """

        await runs.report(session, run, 90, "保存候选图")
        created = [
            await assets.create_from_bytes(
                session,
                run.user_id,
                data,
                AssetKind.GENERATED,    # 标记为生成图
                AssetSource.GENERATE,   # 来源为生成
            )
            for data in images
        ]

    except ProviderError as exc:
        # AI provider 返回的业务错误（如参考图不存在）
        await runs.finish(session, run, status=RunStatus.FAILED, error=str(exc))
        return

    except Exception:
        # 其他未预期的异常
        logger.exception("生成任务异常 run_id=%s", run.id)
        await session.rollback()  # 回滚事务，撤销未提交的变更
        await runs.finish(session, run, status=RunStatus.FAILED, error="生成失败，请重试")
        return

    # 6. 标记任务完成，返回生成的素材 ID 列表
    await runs.finish(
        session,
        run,
        status=RunStatus.SUCCEEDED,
        result={"asset_ids": [str(asset.id) for asset in created]},
    )