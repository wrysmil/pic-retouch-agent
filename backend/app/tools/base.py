from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ToolRun

# 工具执行函数的统一签名，登记表里所有工具都长这样。
#   AsyncSession  数据库连接，读写记录的抓手，由调用方一路透传
#   ToolRun       本次调用记录，带 user_id、session_id 和已校验的 params
# 两个参数都由统一外壳 execute() 传入；返回值是结果字典，外壳据此落库并推 SSE。
ToolHandler = Callable[[AsyncSession, ToolRun], Awaitable[dict]]


class UnknownTool(Exception):
    """工具未注册。"""


@dataclass(frozen=True)
class ToolSpec:
    """一个工具的完整定义，界面与 Agent 共用。

    params 同时用于服务端校验和生成模型的函数签名，两者不会漂移。
    handler 只关心业务结果，状态流转由统一的执行外壳负责。
    """

    name: str
    # 给用户展现的工具名称
    label: str
    description: str
    params: type[BaseModel]
    # 操作函数
    handler: ToolHandler
    needs_approval: bool = False
    # 只改 LayerDocument 的同步工具当场执行，像素工具仍走队列
    queued: bool = True
    '''
    session_required=False 的工具（生图那些）压根不碰画布，
    没有会话照样能跑，所以这项检查对它们是关掉的——由 _canvas() 工厂函数
    和各个 ToolSpec 字面量里的 session_required=True 决定，不是全局开关。
    '''
    session_required: bool = False
    # 素材 ID、随机种子这类参数应由服务端从上下文填入，不暴露给模型
    agent_hidden: tuple[str, ...] = field(default_factory=tuple)