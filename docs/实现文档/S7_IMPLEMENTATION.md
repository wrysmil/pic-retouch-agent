# S7 实现文档：后端启动端口取自配置

> 项目：pic-retouch-agent
> 里程碑：S7
> 日期：2026-09-24

## 1. 仓库状态变化

| 提交 | 内容 |
|---|---|
| S1–S6（已存在） | 脚手架 / 基础设施 / 账号体系 / 素材上传 / 品牌化 / 文生图链路 / 测试清理 |
| **S7（本里程碑）** | 新增 `python -m app` 启动入口，端口取自 `settings.api_port` |

一行改动文件（新增），零后端逻辑变化。

## 2. 变更详情

`backend/app/__main__.py`（新增）：

```python
import uvicorn

from app.config import get_settings

settings = get_settings()

uvicorn.run("app.main:app", host="127.0.0.1", port=settings.api_port)
```

Python 的 `-m` 会执行包的 `__main__` 子模块，因此直接在 `backend/` 下 `python -m app` 即启动。端口由 `Settings.api_port` 驱动（`.env` 默认 7302），命令行不再写死。

## 3. 验证

```bash
# 在 backend/ 目录
./.venv/Scripts/python.exe -m app &
curl http://127.0.0.1:7302/api/health   # {"api":"ok",...}
# 改 .env API_PORT=7303 后重启，curl http://127.0.0.1:7303/api/health 同样 ok
```

`pytest` 不受影响。

## 4. 后续清理

无遗留。仍保留 `uvicorn app.main:app` 作为等价的手动启动方式，两者共用同一 `app` 对象。