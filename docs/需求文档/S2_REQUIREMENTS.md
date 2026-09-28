# S2 需求文档：账号密码注册登录、落地页

> 项目：pic-retouch-agent（AI 修图智能体）
> 里程碑：S2 — 账号体系 + 落地页
> 日期：2026-09-22
> 前置里程碑：S1（脚手架 / 基础设施，已完成）
> 后续里程碑：S3（创作 + 候选）、S4（编辑）、S10（物料导出）、S11（批量）

## 1. 背景与目标

S1 阶段仓库只搭好了后端骨架、前端骨架、数据库与对象存储，落地页仅是一行标题加一个开发态健康检查指示，且工作台路由 `/create`、`/editor`、`/batch` 对未登录用户也完全开放。

S2 引入最基础的账号体系：用户能注册、登录、登出，并通过 httpOnly Cookie 维持会话。同时把落地页改造为产品介绍 + 营销转化页，把工作台路由收回到登录用户。

**为什么这一里程碑独立**：账号体系是后续所有 S3/S4/S10/S11 的前提 —— 创作、编辑、批量任务、导出物料都必须挂在某个用户上，否则对象存储里的图片无法归属、无法做权限隔离。先打通最简的 username + password 闭环，下一里程碑再做完整 OAuth、邮箱验证等扩展。

## 2. 用户与场景

| 角色 | 场景 |
|---|---|
| 首次访问者 | 浏览落地页 → 看到产品介绍与能力清单 → 点击"免费开始"进入注册 |
| 新用户 | 注册后自动登录，直接进入工作台 |
| 回访用户 | 落地页右上角点"登录" → 输入凭证 → 进入工作台 |
| 工作台用户 | 工作台侧边栏底部点"退出登录" → 回到落地页 |

## 3. 功能需求

### 3.1 注册 F1

- **F1.1** 用户在 `/auth?mode=register` 输入 username 与 password 提交注册
- **F1.2** 同一 username 注册第二次，返回 `409 该用户名已被占用`
- **F1.3** 注册成功后自动建立会话，前端跳转到 `/create`
- **F1.4** 注册成功后服务端返回 `201 Created`，响应体为新用户对象 `{id, username}`，同时写入 `session` Cookie

### 3.2 登录 F2

- **F2.1** 用户在 `/auth?mode=login`（或 `/auth`）输入凭证提交
- **F2.2** 凭证正确，建立会话，前端跳转到 `/create`
- **F2.3** 凭证错误，返回 `401 用户名或密码错误`
- **F2.4** 登录成功后响应体为 `{id, username}`，同时写入 `session` Cookie

### 3.3 登出 F3

- **F3.1** 用户在工作台侧边栏底部点"退出登录"
- **F3.2** 服务端 `POST /api/auth/logout` 返回 `204`，清除 `session` Cookie
- **F3.3** 前端清空 react-query 缓存，跳回落地页 `/`

### 3.4 当前用户 F4

- **F4.1** `GET /api/auth/me` 携带 `session` Cookie → 返回 `{id, username}`
- **F4.2** 未携带 Cookie 或 Cookie 无效 → 返回 `401 未登录或会话已过期`
- **F4.3** 前端通过 `useCurrentUser` 缓存当前用户，作为路由守卫的判断依据

### 3.5 落地页 F5

- **F5.1** `/` 路由展示产品名（"AI 修图智能体"）、产品定位（一句话交付可上架商品物料）、一段说明、四张能力卡（一句话生成 / 主体级编辑 / 语义图层 / 物料包交付）
- **F5.2** 顶部右上角：未登录显示"登录"，已登录显示 `{用户名} · 进入工作台`
- **F5.3** 主 CTA：
  - 未登录时显示"免费开始"（→ `/auth?mode=register`）+ 次按钮"已有账号登录"（→ `/auth`）
  - 已登录时显示"进入工作台"（→ `/create`）
- **F5.4** 不再展示健康状态指示（健康状态属于开发态诊断，从面向买家的页面移除）

### 3.6 路由守卫 F6

- **F6.1** 未登录访问 `/create`、`/editor`、`/batch`、`/candidates`、`/marketing` → 自动重定向到 `/auth`
- **F6.2** 已登录访问 `/auth` → 自动重定向到 `/create`
- **F6.3** 守卫状态判断中显示"加载中…"，避免闪屏
- **F6.4** 工作台路由维持 `WorkbenchLayout` 外壳（左侧导航 + 退出登录按钮）

### 3.7 输入校验 F7

- **F7.1** username：`3–32` 字符；`strip` 后必须仅含字母、数字、下划线（`^[A-Za-z0-9_]+$`）
- **F7.2** password：`6–64` 字符
- **F7.3** 不满足校验时返回 `422`（pydantic / fastapi 默认行为），错误信息包含具体字段

## 4. 非功能需求

| 编号 | 类别 | 描述 |
|---|---|---|
| NFR1 | 安全 | 密码仅以 bcrypt 哈希持久化，明文密码不落库、不记日志、不进 JWT |
| NFR2 | 安全 | JWT 使用 HS256，密钥在 `.env` 中配置；默认密钥须 ≥ 32 字节（HS256 强制要求），生产环境由部署方替换 |
| NFR3 | 安全 | 会话通过 `HttpOnly + SameSite=Lax + path=/` 的 Cookie 传递；生产环境附 `Secure`；前端不持有令牌 |
| NFR4 | 安全 | Token 有效期由 `JWT_TTL_HOURS` 控制（默认 24 小时）；过期后 `GET /api/auth/me` 返回 401 |
| NFR5 | 性能 | 注册/登录端到端 < 300ms（不含网络往返）；bcrypt cost 默认值即可 |
| NFR6 | 可用性 | 注册/登录不依赖外部服务（无邮件、无短信、无第三方登录） |
| NFR7 | 可观测 | 注册失败、登录失败有日志；前端错误通过 `ApiError.message` 显示给用户 |
| NFR8 | 可测 | 注册/登录/登出/当前用户四条核心路径有集成测试 |
| NFR9 | 一致 | 后端使用 `Annotated[User, Depends(current_user)]` 风格，与项目既有的 `SessionDep` 风格保持一致 |
| NFR10 | 一致 | 前端状态以服务端 Cookie 为准，前端 react-query 缓存当前用户，登录成功写入缓存，登出清空缓存 |

## 5. API 设计

| 方法 | 路径 | 鉴权 | 成功响应 | 失败响应 |
|---|---|---|---|---|
| POST | `/api/auth/register` | 无 | 201 `{id, username}` + Set-Cookie session | 409 用户名被占 / 422 校验失败 |
| POST | `/api/auth/login` | 无 | 200 `{id, username}` + Set-Cookie session | 401 凭证错误 / 422 校验失败 |
| POST | `/api/auth/logout` | 无 | 204 + 清 Cookie | — |
| GET | `/api/auth/me` | Cookie | 200 `{id, username}` | 401 未登录 |

错误响应体均遵循 FastAPI 默认 `{detail: "<message>"}` 结构；前端 `ApiError` 已按此解析。

## 6. 数据模型

新增 `users` 表（首次 Alembic 迁移）：

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK | 默认值 `uuid.uuid4()` |
| username | VARCHAR(32) | UNIQUE, NOT NULL, INDEX | 登录名 |
| password_hash | VARCHAR(128) | NOT NULL | bcrypt 哈希 |
| created_at | TIMESTAMP | NOT NULL, server default `now()` | 创建时间 |

UUID 列使用 PostgreSQL `UUID` 原生类型；Python 端通过 SQLAlchemy `PgUUID(as_uuid=True)` 映射。

ORM 基类 `UUIDBase` 抽象出 `id` + `created_at`，供后续模型复用。

## 7. 安全设计

| 维度 | 选型 | 原因 |
|---|---|---|
| 密码 | bcrypt | 慢哈希、抗彩虹表；`bcrypt` 库为主流选择；与项目既已声明的依赖一致 |
| 会话令牌 | JWT (HS256) | 无状态，无需在服务端存储 session 表；与项目既已声明的 `pyjwt` 一致 |
| 令牌载荷 | `{sub: user_id, exp}` | 仅存用户 ID，不存敏感信息；过期由 JWT 库自动校验 |
| 令牌传递 | httpOnly Cookie | 防 XSS 读取；`SameSite=Lax` 防 CSRF（GET）；`path=/` 让所有路径都能看到 |
| 注册并发 | DB 唯一索引 + `IntegrityError` → 业务异常 | 不在应用层 SELECT 抢锁，依靠 DB 唯一性兜底 |
| 登录失败 | 用户存在性 / 密码错误统一报 `InvalidCredentials` | 防用户名枚举 |

## 8. 技术约束（继承自 S1）

| 类别 | 选型 |
|---|---|
| 后端 | FastAPI + SQLAlchemy 异步 + asyncpg + Alembic |
| 鉴权 | bcrypt + PyJWT（项目已声明） |
| 前端 | React 19 + react-router v7 + @tanstack/react-query + Tailwind v4 |
| 状态 | 全部依赖 react-query；不引入额外全局状态库（zustand 仅工作台内部用） |

无新增第三方依赖。

## 9. 验收标准

| 编号 | 描述 |
|---|---|
| AC1 | `POST /api/auth/register` 成功后响应 201 + Set-Cookie，且 `users` 表新增一行 |
| AC2 | `POST /api/auth/register` 同名第二次返回 409 |
| AC3 | `POST /api/auth/login` 凭证正确返回 200 + Set-Cookie；密码错误返回 401 |
| AC4 | `POST /api/auth/logout` 返回 204 且响应头 `Set-Cookie` 含过期标记 |
| AC5 | `GET /api/auth/me` 携带有效 Cookie 返回 200；未携带或无效返回 401 |
| AC6 | 未登录访问 `/create` 跳转到 `/auth`；已登录访问 `/auth` 跳转到 `/create` |
| AC7 | username `bad name!`（含空格与感叹号）注册返回 422 |
| AC8 | 工作台侧边栏底部显示"退出登录"，点击后回到 `/` 且 `/api/auth/me` 返回 401 |
| AC9 | 落地页：未登录显示"免费开始"+"已有账号登录"；已登录显示"{username} · 进入工作台" |
| AC10 | `pytest backend/tests/test_auth.py` 全部通过；`pytest backend/tests/test_health.py` 仍通过 |
| AC11 | `JWT_SECRET` 默认值 ≥ 32 字节；`HS256` 编码不抛 `RequiredKey字节长度不足` 异常 |

## 10. 范围与非范围

**本里程碑范围**：

- 注册 / 登录 / 登出 / 当前用户四条 API
- `users` 表 + Alembic 迁移
- 落地页改造为产品介绍页
- 工作台路由守卫 + 工作台退出登录入口
- bcrypt + JWT + httpOnly Cookie 会话方案

**本里程碑非范围（留给后续里程碑）**：

- 邮箱验证、找回密码、改密（需引入邮件服务）
- 第三方登录（OAuth / 微信 / Google）
- 多设备会话管理、Token 撤销列表
- 用户头像、昵称、个人资料页
- 角色 / 权限模型（普通用户 vs 管理员）
- API Token（用于程序化调用，复用同一 User 表但独立 Token 机制）

## 11. 后续依赖

S2 完成后，下列里程碑才有可挂载的"用户"概念：

- **S3 创作 + 候选**：`/create` 产出的图片按 `user_id` 归档到 MinIO，前缀 `users/{user_id}/...`
- **S4 编辑**：编辑会话与 User 关联；登录后只能编辑自己创建的图
- **S10 物料导出**：按 User 维度统计导出配额（未来按需扩展）
- **S11 批量任务**：arq 任务携带 `user_id`，任务结果按用户归档

当前 S2 不预判以上业务的存储结构（仅要求 `User.id` 为 UUID、唯一且稳定）。