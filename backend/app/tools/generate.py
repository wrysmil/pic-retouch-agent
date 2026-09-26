from app.schemas.run import GenerateIn
from app.services import generation
from app.tools.base import ToolSpec

GENERATE_IMAGE = ToolSpec(
    name="generate_image",
    label="生成图片",
    description="根据文字描述从零生成图片候选。",
    params=GenerateIn,
    handler=generation.execute,
    # 种子与参考图由用户界面上显式传入，不需要模型代为推断
    agent_hidden=("seed", "reference_asset_ids"),
)