# 实现文档

> 项目：pic-retouch-agent
> 范围：当前未提交的全部文件
> 日期：2026-09-21

## 1. 仓库状态

- 仅一次 `Initial commit`（104b76d），提交内容为空
- 当前所有源代码与配置均为未跟踪状态（`git status` 列出 7 项根目录条目 + backend/ + frontend/）
- 阶段：脚手架，业务逻辑多为占位

## 2. 顶层目录

```
.
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── README.md                 # 仅一行标题，待补充
├── backend/                  # FastAPI + Python 3.13
├── docker-compose.yml
├── docs/                     # 项目文档（被 .gitignore 排除，不入库）
└── frontend/                 # React 19 + Vite 8
```

## 3. 后端（[backend/](backend/)）

### 3.1 应用骨架

| 文件 | 职责 |
|---|---|
| [app/main.py](backend/app/main.py) | FastAPI 入口。`/api` 前缀的 APIRouter；生产环境挂载前端 `dist` |
| [app/config.py](backend/app/config.py) | pydantic-settings，从仓库根 `.env` 读取配置；`frontend_dist` 路径属性 |
| [app/db.py](backend/app/db.py) | SQLAlchemy 异步引擎、`SessionFactory`、`SessionDep` 依赖注入 |
| [app/routers/health.py](backend/app/routers/health.py) | `GET /api/health`，探测数据库连通性，错误降级为 `error: <异常类名>` |
| [app/worker.py](backend/app/worker.py) | arq Worker 入口，从 `app.tasks.TASKS` 注册函数 |
| [app/tasks/__init__.py](backend/app/tasks/__init__.py) | 集中注册异步任务（当前仅 `ping`） |
| [app/tasks/ping.py](backend/app/tasks/ping.py) | 占位异步任务 |
| [app/models/__init__.py](backend/app/models/__init__.py) | ORM 模型包入口（空，待实现） |
| [migrations/env.py](backend/migrations/env.py) | Alembic 异步环境，连接串来自 `get_settings().database_url` |

### 3.2 测试

| 文件 | 职责 |
|---|---|
| [tests/test_health.py](backend/tests/test_health.py) | `/api/health` 集成测试，通过 `ASGITransport` 走内存栈，不依赖真实数据库 |

### 3.3 依赖（[pyproject.toml](backend/pyproject.toml)）

- **核心**：fastapi、uvicorn[standard]、pydantic-settings、sqlalchemy[asyncio]、asyncpg、alembic、arq、redis、boto3、pillow、python-multipart、bcrypt、pyjwt、httpx
- **可选 `cv`**：rembg、onnxruntime、opencv-python-headless、rapidocr-onnxruntime
- **可选 `agent`**：langgraph、langgraph-checkpoint-postgres、langchain-core、langchain-openai
- **dev**：pytest、pytest-asyncio、ruff（line-length=100）

## 4. 前端（[frontend/](frontend/)）

### 4.1 入口与路由

| 文件 | 职责 |
|---|---|
| [src/main.tsx](frontend/src/main.tsx) | React 19 根，注入 `QueryClient`（retry=1, refetchOnWindowFocus=false）与 `StrictMode` |
| [src/App.tsx](frontend/src/App.tsx) | react-router v7 路由表（详见 §4.2） |
| [src/index.css](frontend/src/index.css) | Tailwind v4 + `@theme` 设计 token（颜色 / 圆角 / 阴影） |

### 4.2 路由表（[App.tsx](frontend/src/App.tsx)）

| 路径 | 组件 | 备注 |
|---|---|---|
| `/` | LandingPage | 已实现，含健康状态指示 |
| `/create` | PlaceholderPage | S3 待实现 |
| `/editor` | PlaceholderPage | S4 待实现 |
| `/batch` | PlaceholderPage | S11 待实现 |
| `/candidates` | PlaceholderPage | S3 待实现 |
| `/marketing` | PlaceholderPage | S10 待实现 |
| `*` | 重定向到 `/` | — |

工作台路由（`/create` `/editor` `/batch`）共用 [WorkbenchLayout.tsx](frontend/src/layouts/WorkbenchLayout.tsx) 外壳（左侧导航默认收起为图标，悬停展开文字）。`/candidates` 与 `/marketing` 为独立占位页。

### 4.3 共享组件

| 文件 | 职责 |
|---|---|
| [src/layouts/WorkbenchLayout.tsx](frontend/src/layouts/WorkbenchLayout.tsx) | 工作台外壳：左侧导航 + `<Outlet />` |
| [src/pages/LandingPage.tsx](frontend/src/pages/LandingPage.tsx) | 首页：文案 + CTA + 健康状态指示（绿/红圆点） |
| [src/pages/PlaceholderPage.tsx](frontend/src/pages/PlaceholderPage.tsx) | 占位页，接收 `title` 与 `hint` 两个 prop |
| [src/api/client.ts](frontend/src/api/client.ts) | fetch 封装，统一 `/api` 前缀、错误抛出 `ApiError`，提供 `get/post/patch/delete` |

### 4.4 构建配置

- [vite.config.ts](frontend/vite.config.ts)：端口 7301（`strictPort`），`/api` 与 `/events` 代理至 `http://localhost:7302`，`@` 别名指向 `src/`
- [tsconfig.app.json](frontend/tsconfig.app.json) / [tsconfig.node.json](frontend/tsconfig.node.json) / [tsconfig.json](frontend/tsconfig.json)
- [.oxlintrc.json](frontend/.oxlintrc.json)
- [package.json](frontend/package.json)：依赖见 §5 需求 §5 技术约束

## 5. 基础设施

### 5.1 Docker Compose（[docker-compose.yml](docker-compose.yml)）

| 服务 | 镜像 | 端口 | profile |
|---|---|---|---|
| postgres | postgres:17-alpine | 7311:5432 | default |
| redis | redis:7-alpine | 7312:6379 | default |
| minio | quay.io/minio/minio:latest | 7313:9000（S3）/7314:9001（控制台） | default |
| app | 自建 | 7302:7302 | deploy |
| worker | 自建 | — | deploy |

凭证：`retouch` / `retouch_dev`（postgres 用户/库、minio root）。`cv_models` 卷用于在镜像间共享 u2net 模型。

### 5.2 Dockerfile（[Dockerfile](Dockerfile)）

多阶段构建：

1. `node:22-alpine`：`npm ci` + `npm run build`，产物 `/build/dist`
2. `python:3.13-slim`：通过 `uv`（来自 `ghcr.io/astral-sh/uv`）以 `uv sync --frozen --all-extras --no-dev` 装依赖
3. 前端产物拷入 `/app/frontend/dist`，由后端同源托管

### 5.3 环境变量（[.env.example](.env.example)）

应用配置：`APP_ENV`、`API_PORT`、`DATABASE_URL`、`REDIS_URL`、`S3_*`、`JWT_*`、`IMAGE_PROVIDER`（mock/dashscope）、`DASHSCOPE_API_KEY`、`TEXT_TO_IMAGE_MODEL`、`IMAGE_EDIT_MODEL`、`PLANNER_MODEL`。

### 5.4 Git 排除（[.gitignore](.gitignore)）

敏感信息（`.env`、`.pem`、`.key`）+ `docs/` + Python / Node 编译产物 + `.idea` / `.vscode` + 运行时数据。

## 6. 完成度矩阵

| 模块 | 状态 |
|---|---|
| 后端骨架（config / db / main / worker / health） | ✓ 完成 |
| 前端骨架（路由 / 布局 / Landing / API client） | ✓ 完成 |
| 设计系统（颜色 token、圆角、阴影） | ✓ 完成 |
| 基础设施编排（docker-compose 三件套） | ✓ 完成 |
| 前后端同源构建（Dockerfile 多阶段） | ✓ 完成 |
| `/api/health` 端点 + 集成测试 | ✓ 完成 |
| Alembic 异步环境 | ✓ 配置完成（无版本文件） |
| ORM 模型 | × 未开始 |
| Alembic 迁移版本 | × 未生成 |
| `/create` 文生图路由 + LangGraph | × 未开始 |
| `/candidates` 候选筛选 | × 未开始 |
| `/editor` Konva 画布编辑器 | × 未开始 |
| `/batch` 批量任务调度 | × 未开始 |
| `/marketing` 物料导出 | × 未开始 |
| CV 模型接入（rembg / OCR） | × 仅声明依赖 |
| README | × 仅一行标题 |

## 7. 已知问题

- **MinIO healthcheck 不可用**：[docker-compose.yml:46-50](docker-compose.yml#L46-L50) 用 `mc ready local`，但 `quay.io/minio/minio` 镜像不含 `mc` 客户端，容器恒为 `unhealthy`。本地开发不影响；deploy profile 下 `depends_on: condition: service_healthy` 会卡住
- **README 空**：仅一行标题，新成员无上手指引
- **docs/ 被 .gitignore 排除**：本目录文档不随仓库分发，需手动添加或调整 `.gitignore`
- **Alembic 迁移版本未生成**：ORM 模型尚未实现，`autogenerate` 无目标
- **测试覆盖率为零**：除 `test_health.py` 外无任何测试

## 8. 验证步骤

```bash
# 1. 准备 .env
cp .env.example .env

# 2. 拉起基础设施
docker compose up -d postgres redis minio

# 3. 安装后端依赖并启动
cd backend
uv sync --all-extras
uv run uvicorn app.main:app --reload --port 7302

# 4. 健康检查
curl http://localhost:7302/api/health
# 期望 {"api":"ok","database":"ok|error:..."}

# 5. 安装前端依赖并启动
cd ../frontend
npm install
npm run dev

# 6. 访问首页
# 浏览器打开 http://localhost:7301，观察健康状态指示
```

## 9. 后续路线图（按里程碑）

1. **S3 创作 + 候选**：`/create` `/candidates` 路由 + LangGraph 工作流 + mock provider 出占位图
2. **S4 编辑**：Konva 画布 + rembg 抠图 + 文字 / 贴纸 + 局部重绘
3. **S10 物料导出**：模板系统 + 多平台尺寸配方
4. **S11 批量**：arq 任务 + 状态机 + MinIO 状态文件 + 进度查询
5. **横切**：ORM 模型、Alembic 迁移、README、CI、单元测试覆盖、修复 MinIO healthcheck
