# S2 实现文档：账号密码注册登录、落地页

> 项目：pic-retouch-agent
> 里程碑：S2
> 日期：2026-09-22

## 1. 仓库状态变化

| 提交 | 内容 |
|---|---|
| S1（已存在） | 脚手架 + 基础设施 + `/api/health` + LandingPage（带健康指示） |
| **S2（本里程碑）** | 注册 / 登录 / 登出 / 当前用户四条 API + `users` 表 + `require_auth` 守卫 + 工作台退出入口 + 落地页改造为产品页 |

未引入任何新第三方依赖；既有 `bcrypt`、`pyjwt`、`@tanstack/react-query` 即足够支撑本里程碑。

## 2. 后端实现

### 2.1 新增文件

| 文件 | 职责 |
|---|---|
| [app/security.py](backend/app/security.py) | 密码哈希（bcrypt）、JWT 签发 / 解析、`SESSION_COOKIE` 常量 |
| [app/models/base.py](backend/app/models/base.py) | `UUIDBase` 抽象类：UUID 主键 + `created_at`，供后续模型复用 |
| [app/models/user.py](backend/app/models/user.py) | `User` ORM 模型：`username` 唯一索引、`password_hash` |
| [app/schemas/auth.py](backend/app/schemas/auth.py) | `Credentials`（含 username 字符集校验）、`UserOut` |
| [app/services/auth.py](backend/app/services/auth.py) | `register` / `authenticate` / `get_by_id`，自定义异常 `UsernameTaken`、`InvalidCredentials` |
| [app/routers/auth.py](backend/app/routers/auth.py) | `/api/auth/register`、`/api/auth/login`、`/api/auth/logout`、`/api/auth/me` |
| [app/deps.py](backend/app/deps.py) | `current_user` 依赖（读 Cookie → 解析 token → DB 取 user），导出 `CurrentUser` 类型别名 |
| [app/schemas/__init__.py](backend/app/schemas/__init__.py) | 空包标识 |
| [app/services/__init__.py](backend/app/services/__init__.py) | 空包标识 |
| [migrations/versions/20260922_2136_users.py](backend/migrations/versions/20260922_2136_users.py) | `users` 表首次迁移 |
| [tests/conftest.py](backend/tests/conftest.py) | 共享 httpx AsyncClient fixture + 每个测试自动清空 `users` 表 |
| [tests/test_auth.py](backend/tests/test_auth.py) | 7 条集成测试：注册 / 重名 / 登录 / 错密 / 未登录访问 / 登出 / 校验 |

### 2.2 修改文件

| 文件 | 变更 |
|---|---|
| [app/config.py](backend/app/config.py) | `jwt_secret` 默认值由 `"dev-only-change-me"`（19 字节）改为 `"dev-only-secret-please-change-in-production"`（44 字节），满足 HS256 最小密钥长度 |
| [app/main.py](backend/app/main.py) | `from app.routers import auth, health` + `api.include_router(auth.router)` |
| [app/models/__init__.py](backend/app/models/__init__.py) | 导出 `User`，Alembic `autogenerate` 能识别 |
| [migrations/script.py.mako](backend/migrations/script.py.mako) | 移除冗余 docstring 与变量注释；与 SQLAlchemy 2 风格对齐 |
| [pyproject.toml](backend/pyproject.toml) | pytest asyncio 默认 fixture / 测试循环 scope 改为 `session`（共享 engine） |
| [.env.example](.env.example) | `JWT_SECRET` 默认值与 config 对齐，便于本地复刻 |
| [.env](.env) | 同上（本地文件） |

### 2.3 模块依赖图

```
routers/auth
  ├─ schemas/auth     ─ pydantic
  ├─ services/auth    ─ models.User, security.{hash_password, verify_password}
  ├─ security         ─ config.get_settings, jwt, bcrypt
  └─ deps             ─ db.SessionDep, models.User, services.auth, security.read_token

deps.current_user
  ├─ db.SessionDep
  ├─ security.read_token  ← SESSION_COOKIE 名 + JWT 解码
  └─ services.auth.get_by_id

services/auth.register
  └─ IntegrityError → UsernameTaken        ← 依赖 DB 唯一索引，不在应用层预查
```

### 2.4 关键决策与理由

| 决策 | 理由 |
|---|---|
| 用 `PgUUID(as_uuid=True)` 而非 `String(36)` | 原生 UUID 类型省空间、有索引性能、ORM 端直接是 `uuid.UUID`，无需手工解析 |
| 不在 `register` 中先 `SELECT` 再 `INSERT` | 并发场景下两次 SELECT 都会返回空，第二次 INSERT 才被唯一索引拒绝；直接依赖 `IntegrityError` 更稳 |
| `authenticate` 在用户不存在时与密码错误抛同一异常 | 防用户名枚举（攻击者无法通过响应差异判断用户是否存在） |
| JWT 仅含 `sub` + `exp` | 不存 username、role 等业务字段 —— 业务字段从 DB 实时读，避免令牌失同步 |
| `current_user` 直接 `raise 401` 而非返回 `Optional[User]` | 路由层强制要求鉴权，少一个 None 分支判断 |
| Cookie `secure=settings.is_production` | 本地开发走 http，强制 Secure 会导致 dev 登录不上；生产由部署方开启 |
| `httpx.AsyncClient` + `ASGITransport` 走 ASGI 内存栈 | 测试不启 uvicorn 进程，速度快；`SessionDep` 仍走真实 SQLAlchemy 引擎 |
| pytest asyncio session 共享事件循环 | `app.db` 在模块级创建 engine，每个测试新建 loop 会跨 loop 复用连接，导致 `RuntimeError` |

### 2.5 数据库迁移

文件：[backend/migrations/versions/20260922_2136_users.py](backend/migrations/versions/20260922_2136_users.py)

```python
def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
```

应用方式：`docker compose up -d postgres && cd backend && uv run alembic upgrade head`。

## 3. 前端实现

### 3.1 新增文件

| 文件 | 职责 |
|---|---|
| [src/api/auth.ts](frontend/src/api/auth.ts) | 封装 `register / login / logout / me` 四个 API；导出 `User`、`Credentials` 类型 |
| [src/hooks/useAuth.ts](frontend/src/hooks/useAuth.ts) | `useCurrentUser()` 缓存当前用户；`useAuthActions()` 暴露 login / register / logout mutation；`errorMessage()` 统一错误展示文案 |
| [src/layouts/RequireAuth.tsx](frontend/src/layouts/RequireAuth.tsx) | 路由守卫：未登录重定向 `/auth`，加载中显示"加载中…" |
| [src/pages/AuthPage.tsx](frontend/src/pages/AuthPage.tsx) | 登录 / 注册双模页面，通过 `?mode=register\|login` 切换 |

### 3.2 修改文件

| 文件 | 变更 |
|---|---|
| [src/App.tsx](frontend/src/App.tsx) | 增加 `/auth` 路由；工作台路由统一包在 `<RequireAuth>` 内；`/candidates`、`/marketing` 也纳入守卫 |
| [src/api/client.ts](frontend/src/api/client.ts) | `request()` 增加 `formatDetail()`：统一处理 FastAPI 错误体。字符串 `detail`（401/409）原样透传；数组 `detail`（422 校验错误）取每项 `msg` 用「；」拼接，避免 `[object Object]` 乱码 |
| [src/layouts/WorkbenchLayout.tsx](frontend/src/layouts/WorkbenchLayout.tsx) | 底部新增"退出登录"按钮（带当前用户首字母头像 + 悬停展开文字） |
| [src/pages/LandingPage.tsx](frontend/src/pages/LandingPage.tsx) | 重写为产品介绍页：标题 / 副标题 / 四张能力卡 / 按登录态切换的 CTA；移除健康状态指示 |
| [vite.config.ts](frontend/vite.config.ts) | `server.host: '127.0.0.1'`，避免 Vite 默认只监听 `::1` 导致 IPv4 回环被拒 |

### 3.3 路由表（更新后）

| 路径 | 组件 | 守卫 |
|---|---|---|
| `/` | LandingPage | 无 |
| `/auth` | AuthPage | 已登录自动跳 `/create` |
| `/create` | PlaceholderPage | RequireAuth |
| `/editor` | PlaceholderPage | RequireAuth |
| `/batch` | PlaceholderPage | RequireAuth |
| `/candidates` | PlaceholderPage | RequireAuth |
| `/marketing` | PlaceholderPage | RequireAuth |
| `*` | 重定向到 `/` | — |

### 3.4 关键决策与理由

| 决策 | 理由 |
|---|---|
| `useCurrentUser` 不在 401 时抛错 | 未登录是合法状态，用 `user: User \| null` 表达即可；`throwOnError: false` |
| `useCurrentUser` 设置 `staleTime: Infinity` | 会话状态以服务端 Cookie 为准，前端不主动重查；切换账号登出时由 `logout.mutate.onSuccess` 触发 `queryClient.clear()` 主动失效 |
| `login/register.mutate.onSuccess` 写入 `['auth', 'me']` 缓存 | 注册 / 登录成功立即拿到 user，无需再调 `/me` |
| `logout.mutate.onSuccess` 清空整个缓存 | 登出后所有用户态数据（候选图、编辑态）都应失效；最小成本是 `clear()` |
| AuthPage 用 URL `?mode=` 切换模式 | 链接可分享、可收藏；刷新页面不丢状态 |
| RequireAuth 在加载中显示"加载中…" | 避免已登录用户访问工作台时先闪一下 `/auth` 再跳回 |
| 工作台退出按钮 hover 才显示"退出登录"文字 | 与顶部 NavLink 一致的"图标 + 悬停展开"交互；首字母头像额外承担"当前是谁"的指示 |
| LandingPage 不再展示健康状态 | 健康指示面向开发态；面向买家的产品页不放 |
| Vite `host: '127.0.0.1'` | 默认 `localhost` 在 Windows 上偶发只解析到 `::1`（IPv6 回环），IPv4 直连 127.0.0.1 被拒 |

### 3.5 状态管理

| 状态 | 位置 | 来源 |
|---|---|---|
| 当前用户 | react-query `['auth', 'me']` | `GET /api/auth/me` |
| 登录 / 注册 mutation | react-query mutation | `useAuthActions` |
| 工作台本地态（待办，未来的 S3+ 引入） | zustand | 不在 S2 范围 |

## 4. 设计令牌复用

落地页与 AuthPage 完全沿用 S1 的 `@theme` 设计令牌：

- 颜色：`text-ink` / `text-muted` / `text-faint` / `border-line` / `bg-paper` / `bg-ink` / `bg-soft` / `text-brand-strong`
- 圆角：`rounded-[12px]`（控件）、`rounded-[18px]`（卡片）
- 阴影：能力卡 hover 用 `--shadow-card`

未新增任何颜色或圆角变量。

## 5. 完成度矩阵（S2 增量）

| 模块 | 状态 |
|---|---|
| `app/security.py`（bcrypt + JWT） | ✓ 完成 |
| `app/models/base.py` / `user.py` | ✓ 完成 |
| `app/schemas/auth.py` | ✓ 完成 |
| `app/services/auth.py` | ✓ 完成 |
| `app/routers/auth.py`（register / login / logout / me） | ✓ 完成 |
| `app/deps.py`（current_user） | ✓ 完成 |
| `users` 表 Alembic 迁移 | ✓ 完成 |
| `tests/conftest.py` + `tests/test_auth.py` | ✓ 完成（7 用例） |
| `pyproject.toml` pytest asyncio session scope | ✓ 完成 |
| 前端 `api/auth.ts` | ✓ 完成 |
| 前端 `hooks/useAuth.ts` | ✓ 完成 |
| 前端 `RequireAuth` 守卫 | ✓ 完成 |
| 前端 `AuthPage`（登录 / 注册双模） | ✓ 完成 |
| 前端 `LandingPage` 改造 | ✓ 完成 |
| 工作台退出按钮 | ✓ 完成 |
| `vite.config.ts` 绑定 IPv4 | ✓ 完成 |

## 6. 已知问题 / 后续清理

| 编号 | 描述 | 归属 |
|---|---|---|
| K1 | `JWT_SECRET` 默认值仍是占位串，生产部署必须替换 | 部署文档（待写） |
| K2 | 无密码强度策略（仅 6 位字符数下限） | 后续账号安全里程碑 |
| K3 | 无登录失败限流；本地开发无影响，生产建议加 IP 级 rate limit | S2 后续安全迭代 |
| K4 | 暂无"记住我"开关；TTL 写死 24 小时 | S2 后续 |
| K5 | `tests/conftest.py` 假设 PostgreSQL 已启动且能清空 `users` 表；本地未起 DB 时 `pytest backend/tests/test_auth.py` 会失败 | 已有：`test_health.py` 同等依赖 |

## 7. 验证步骤

```bash
# 1. 应用数据库迁移
docker compose up -d postgres
cd backend && uv run alembic upgrade head

# 2. 启动后端
uv run uvicorn app.main:app --reload --port 7302

# 3. 启动前端
cd ../frontend && npm run dev

# 4. 手工验证
# 浏览器打开 http://localhost:7301
# → 落地页展示产品介绍；右上角"登录"
# → 点击"免费开始" → /auth?mode=register
# → 输入 u_test / secret123 提交 → 跳到 /create
# → 浏览器 DevTools Application → Cookies → 看到 session
# → 工作台底部"退出登录" → 回到 /，右上角变回"登录"

# 5. 接口验证
curl -i -X POST http://localhost:7302/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo","password":"secret123"}'
# 期望 201 + Set-Cookie: session=...

curl -i -X GET http://localhost:7302/api/auth/me \
  --cookie 'session=<上一步返回值>'
# 期望 200 {"id":"...","username":"demo"}

# 6. 测试
cd backend && uv run pytest tests/test_auth.py tests/test_health.py -v
# 期望全部通过
```

## 8. 后续路线图（S3 起）

1. **S3 创作 + 候选**：`/create` 文生图路由接入 LangGraph 工作流；`User.id` 作为图片归档前缀 `users/{user_id}/sessions/{session_id}/...`
2. **S4 编辑**：Konva 画布上的所有改动通过 `current_user` 权限校验
3. **S10 物料导出**：导出记录关联用户
4. **S11 批量任务**：arq 任务携带 `user_id`，结果按用户归档
5. **横切**：账号安全（密码强度、限流、改密）、邮箱验证、第三方登录、角色 / 权限