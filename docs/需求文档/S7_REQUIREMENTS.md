# S7 需求文档：后端启动端口取自配置

> 项目：pic-retouch-agent（AI 修图智能体）
> 里程碑：S7 — 标准化启动入口
> 日期：2026-09-24
> 前置里程碑：S6（已完成）
> 后续里程碑：S8+（品牌 favicon）

## 1. 背景与目标

此前后端通过 `uvicorn app.main:app` 手动启动，端口写死在命令行参数里。开发/部署时端口必须手输、记错即连不上前端代理。

S7 新增标准的 `python -m app` 启动入口：

1. **端口单一来源**：监听端口从 `settings.api_port`（`.env` 默认 7302）读取，命令行不再写死。
2. **入口统一**：`python -m app` 成为受支持的标准启动方式，与 `python -m` 惯例对齐。

## 2. 用户与场景

| 角色 | 场景 |
|---|---|
| 后端开发者 | `python -m app` 一键起服务，改端口只动 `.env` 的 `API_PORT` |
| 部署 | 不同环境各配 `API_PORT`，代码零改动 |

## 3. 功能需求

### 3.1 启动入口 F1

- **F1.1** 新增 `backend/app/__main__.py`：`uvicorn.run("app.main:app", host="127.0.0.1", port=settings.api_port)`。
- **F1.2** 在 `backend/` 目录执行 `python -m app` 即可启动，监听端口来自配置。

## 4. 验收标准

| 编号 | 描述 |
|---|---|
| AC1 | `python -m app` 启动后，`127.0.0.1:7302/api/health` 返回 ok |
| AC2 | 把 `.env` 的 `API_PORT` 改为其它值后启动，端口随之变化 |
| AC3 | 既有测试 `pytest` 不受影响、仍全绿 |

## 5. 范围与非范围

**本里程碑范围**：`backend/app/__main__.py` 一份新文件。

**本里程碑非范围**：worker 启动方式变化、`uvicorn --reload` 开发热重载约定、前端 dev proxy 调整。

## 6. 后续依赖

- S8 继续叠加（纯前端，互不影响）。