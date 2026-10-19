# AI 修图智能体

- [文生图链路](docs/generation.md)

## 依赖

- Python 3.13、[uv](https://docs.astral.sh/uv/)
- Node 22、npm
- Docker / Docker Compose

## 环境变量

```bash
cp .env.example .env
```

AI 模型（规划 / 文生图 / 图编辑）不再从环境变量读取：启动后登录后台「模型配置」，登记厂商连接与模型并发布运行版本，任务提交时会锁定该版本。生产环境必须替换 `JWT_SECRET`，并设置 `SECRET_ENC_KEY`（Fernet，32 字节）用于加密厂商密钥。

| 变量 | 说明 |
| --- | --- |
| `SECRET_ENC_KEY` | 加密后台登记的厂商 API Key；未设置时无法保存密钥 |
| `ALLOWED_PROVIDER_HOSTS` | 后台可登记的厂商 base URL 白名单；开发期本地放行填 `allow-localhost` |
| `MATTING_PROVIDER` | `auto` 优先 rembg，`corner` 仅四角抠图 |
| `OCR_PROVIDER` | `auto` 有 rapidocr 则拆文字层，`none` 跳过 |
| `S3_PUBLIC_ENDPOINT` | 浏览器访问签名 URL 的地址；空则与 `S3_ENDPOINT` 相同 |

端口：工作台 7301、管理后台 7303（**独立应用**，独立入口页与登录页）、API 7302、PostgreSQL 7311、Redis 7312、MinIO API 7313、MinIO Console 7314。

本地 CV 模型约 340 MB，缓存在 `~/.u2net`。容器部署时由 `cv_models` volume 挂载，app 与 worker 共用。

## 本地启动

```bash
docker compose up -d

cd backend && uv sync --all-extras && uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 7302

cd backend && uv run arq app.worker.WorkerSettings

cd frontend && npm install && npm run dev
cd frontend && npm run dev:admin
```

浏览器打开 http://127.0.0.1:7301 ，管理后台单独打开 http://127.0.0.1:7303 。

后台是独立的前端应用（`frontend/admin/` + `frontend/vite.admin.config.ts`），有自己的入口页、路由和登录页，只接受管理员账号；与工作台共用同一份 API、设计 token 和 node_modules。构建产物分别在 `frontend/dist` 与 `frontend/dist-admin`。生产部署用 `VITE_WORKBENCH_URL` 指定工作台地址，后台首页的「返回工作台」会用它。

停止中间件：`docker compose down`

## 部署

```bash
cp .env.example .env
docker compose --profile deploy up -d --build
docker compose --profile deploy exec app alembic upgrade head
```

访问 http://127.0.0.1:7302 。容器内数据库 / Redis / MinIO 地址由 compose 覆盖，无需改 `.env` 里的 localhost。

停止：`docker compose --profile deploy down`

## 测试与评测

```bash
cd backend && uv sync --all-extras --group dev && uv run pytest
cd frontend && npm install && npx tsc --noEmit

cd backend && uv run python -m app.eval app/eval/dataset
```

仓库自带一份无线耳机评测集（抠图、调色、交付尺寸）。自己加用例时按 `backend/app/eval/cases.example.json` 的格式准备 `cases.json` 和素材即可。
