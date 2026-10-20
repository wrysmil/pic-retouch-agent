_FIELD_LABELS = {
    "username": "用户名",
    "password": "密码",
    "new_password": "新密码",
    "prompt": "提示词",
    "title": "标题",
    "role": "角色",
    "count": "数量",
    "formats": "导出格式",
    "asset_ids": "素材",
    "operations": "操作",
}


def localize_validation_errors(errors: list[dict[str, object]]) -> list[dict[str, object]]:
    """把 Pydantic 的常见英文校验信息转换为面向用户的中文。"""
    localized: list[dict[str, object]] = []
    for error in errors:
        item = {key: value for key, value in error.items() if key != "ctx"}
        item["msg"] = _message(error)
        localized.append(item)
    return localized


def _message(error: dict[str, object]) -> str:
    loc = error.get("loc") or ()
    field = str(loc[-1]) if loc else "输入内容"
    label = _FIELD_LABELS.get(field, field.replace("_", " "))
    kind = str(error.get("type", ""))
    ctx = error.get("ctx") or {}
    if not isinstance(ctx, dict):
        ctx = {}

    if kind == "missing":
        return f"{label}不能为空"
    if kind in {"string_too_short", "too_short"}:
        minimum = ctx.get("min_length", "规定")
        return f"{label}至少需要 {minimum} 个字符"
    if kind in {"string_too_long", "too_long"}:
        maximum = ctx.get("max_length", "规定")
        return f"{label}最多允许 {maximum} 个字符"
    if kind == "greater_than_equal":
        return f"{label}不能小于 {ctx.get('ge')}"
    if kind == "less_than_equal":
        return f"{label}不能大于 {ctx.get('le')}"
    if kind in {"string_pattern_mismatch", "enum", "literal_error"}:
        return f"{label}取值或格式不正确"
    if kind.startswith("value_error"):
        message = str(error.get("msg", "输入内容不符合要求"))
        return message.removeprefix("Value error, ")
    if kind.endswith("_parsing") or kind.endswith("_type"):
        return f"{label}类型或格式不正确"
    return f"{label}不符合要求"
