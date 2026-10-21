"""工具计次规则：只回答「这次提交预计消耗几个 AI 图片单元」。

纯函数，不读数据库、不看用户余额。金额/次数必须由后端按已校验参数计算，
浏览器与规划模型都不能自报。
"""

# 批量里真正调用外部图片模型的操作；其余为本地像素处理，不计次
AI_BATCH_TOOLS = {"replace_background", "expand_canvas", "upscale_image"}


def zero(_: dict) -> int:
    return 0


def one(_: dict) -> int:
    return 1


def count_of(params: dict) -> int:
    """按候选张数计次，缺省为 1，避免参数异常时白送次数。"""
    try:
        return max(1, int(params.get("count", 1)))
    except (TypeError, ValueError):
        return 1


def batch_units(params: dict) -> int:
    """把批量任务展开成稳定的 AI 处理单元。

    逐素材推进操作链：本地投放尺寸会扩成多个画幅，后续若再接 AI 操作，
    每个画幅各算一个单元；AI 操作结算后仍是一张图，不叠加。
    """

    assets = params.get("asset_ids") or []
    operations = params.get("operations") or []
    if not assets or not operations:
        return 0

    per_asset = 0
    frames = 1
    for operation in operations:
        tool = operation.get("tool")
        if tool in AI_BATCH_TOOLS:
            per_asset += frames
            frames = 1
        elif tool == "prepare_delivery_sizes":
            ratios = (operation.get("params") or {}).get("ratios") or []
            frames = max(1, len(ratios))
        # 去背景、调色等本地操作不改变张数，也不计次
    return per_asset * len(assets)
