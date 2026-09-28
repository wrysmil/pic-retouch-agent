# 需求文档

> 项目：pic-retouch-agent（AI 修图智能体）
> 范围：仓库当前未提交的全部代码与配置
> 日期：2026-09-21

## 1. 项目背景

面向电商与营销场景的图片修图 Agent。用户通过一句话或上传图片，自动串联文生图、抠图、局部修改、批量处理与多平台导出。

典型使用流程：

1. 一句话生成商品主图（文生图）
2. 系统一次性生成多张候选图供挑选
3. 选中后在画布上继续编辑（抠图、调色、文字、贴纸）
4. 一次性导出多平台尺寸的物料

## 2. 目标用户

| 角色 | 场景 |
|---|---|
| 电商商家 | 快速产出商品主图、详情页配图、促销活动图 |
| 营销/运营 | 制作小红书、抖音、淘宝等不同平台规格的物料 |

## 3. 业务功能需求（按里程碑）

### 3.1 S3 — 创作 + 候选

- 文本生成图片：用户输入描述，返回候选图
- 一次生成 N 张候选图，供用户挑选
- 后端 LangGraph 工作流串联"规划 → 出图 → 候选筛选"
- 接入图像生成模型：`qwen-image-3.0-pro`（生产）/ mock（开发）
- 编辑模型：`qwen-image-edit-max`（生产）/ mock（开发）

### 3.2 S4 — 编辑

- 上传图片到 Konva 画布
- 抠图（rembg / u2net ONNX）
- 调色、滤镜
- 添加文字、贴纸
- 局部重绘（接图像编辑模型）

### 3.3 S10 — 导出物料

- 按平台尺寸导出（不同分辨率、宽高比）
- 模板化导出：一份原图 + 多平台尺寸配方，批量产出
- 导出物归档到 MinIO，签名 URL 时效 900s

### 3.4 S11 — 批量

- 一次上传多张图，触发批量任务
- 异步任务队列（arq + Redis）调度
- 任务状态机：pending → running → succeeded / failed
- 进度查询、结果下载
- 失败可重试

## 4. 非功能需求

| 编号 | 类别 | 描述 |
|---|---|---|
| NFR1 | 性能 | 单图创作端到端响应 < 30s（候选模式 N 张） |
| NFR2 | 可用性 | 图像生成 provider 可切换（`mock` / `dashscope`），缺密钥时降级 mock |
| NFR3 | 可观测 | API 调用、Agent 节点、CV 模型推理有结构化日志 |
| NFR4 | 安全 | JWT 鉴权，签名 URL 时效控制（已配置 `S3_URL_TTL=900`） |
| NFR5 | 可扩展 | 图像 provider 可插拔；模型版本可配置 |
| NFR6 | 部署 | 单镜像前后端同源，由 FastAPI 托管；本地开发走 Vite proxy |
| NFR7 | 可回滚 | 数据库迁移基于 Alembic 版本化 |

## 5. 技术约束

| 类别 | 选型 |
|---|---|
| Python | >= 3.13 |
| Web 框架 | FastAPI + Uvicorn |
| 配置 | pydantic-settings |
| 数据库 | PostgreSQL 17（SQLAlchemy 异步 + asyncpg + Alembic） |
| 缓存 / 队列 | Redis 7（arq） |
| 对象存储 | MinIO（boto3 SDK） |
| CV（可选 `cv` extra） | rembg、ONNX Runtime、OpenCV、rapidocr |
| Agent（可选 `agent` extra） | LangGraph、LangGraph Checkpoint、LangChain Core、LangChain OpenAI |
| 鉴权 | bcrypt + PyJWT |
| HTTP 客户端 | httpx |
| 前端框架 | React 19 + TypeScript ~6 |
| 前端构建 | Vite 8 |
| 样式 | Tailwind v4（`@theme` design tokens） |
| 路由 | react-router-dom v7 |
| 画布 | konva 10 + react-konva 19 |
| 状态 / 数据 | zustand 5 + @tanstack/react-query 5 |
| 代码检查 | oxlint |

## 6. 验收标准（当前阶段：脚手架）

- AC1 仓库结构与本需求 §5 技术栈一致
- AC2 后端能在 7302 端口启动，`GET /api/health` 返回 `{"api":"ok","database":"ok|error:..."}`
- AC3 前端能在 7301 端口启动，`/` 页能展示健康状态指示
- AC4 `docker compose up -d postgres redis minio` 三件套正常 Up
- AC5 Alembic 异步环境已配置（`migrations/env.py` + `Base.metadata`）
- AC6 前后端通过 Vite proxy 实现同源（`/api` 与 `/events` 代理至 7302）
- AC7 后端健康检查测试 `tests/test_health.py` 通过

## 7. 范围与非范围

**范围（本仓库内）**：

- S3/S4/S10/S11 功能实现
- 基础设施编排（docker-compose）
- CI/CD（待规划）

**非范围（不在本仓库内）**：

- 用户付费、计费、订单
- 多租户隔离
- 模型训练 / 微调
- 移动端 App
