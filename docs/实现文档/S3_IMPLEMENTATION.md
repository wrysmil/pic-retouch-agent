# S3 实现文档：素材上传、对象存储

> 项目：pic-retouch-agent
> 里程碑：S3
> 日期：2026-09-23

## 1. 仓库状态变化

| 提交 | 内容 |
|---|---|
| S1/（已存在） | 脚手架 + 基础设施 + `/api/health` |
| S2（已存在） | 注册 / 登录 / 登出 / me 四条 API + `users` 表 + 落地页改造 |
| **S3（本里程碑）** | 素材上传 / 列表 / 详情三条 API + `assets` 表 + MinIO 对象存储封装 + `/create` 创作页替换占位页 |

新增依赖 `boto3`、`Pillow`、`python-multipart`（后端）。无新增 npm 依赖。

## 2. 后端实现

### 2.1 新增文件

| 文件 | 职责 |
|---|---|
| [app/storage.py](backend/app/storage.py) | S3 兼容对象存储封装：惰性客户端、`ensure_bucket`、`put` / `get` / `delete`、`signed_url` |
| [app/services/images.py](backend/app/services/images.py) | PIL 图片校验 + 元信息提取：`probe(data) -> ImageMeta`，异常 `ImageRejected` |
| [app/services/assets.py](backend/app/services/assets.py) | `create_from_bytes`（写入对象存储 + 落库）、`list_for_user`、`get_for_user`（按 user_id 隔离） |
| [app/models/asset.py](backend/app/models/asset.py) | `Asset` ORM + `AssetKind` / `AssetSource` 两个 `StrEnum` |
| [app/schemas/asset.py](backend/app/schemas/asset.py) | `AssetOut`（含签名 URL，`AssetOut.of(asset)` 工厂） |
| [app/routers/assets.py](backend/app/routers/assets.py) | `POST /api/assets`、`GET /api/assets`、`GET /api/assets/{id}` |
| [migrations/versions/20260923_assets.py](backend/migrations/versions/20260923_assets.py) | `assets` 表迁移（依赖 `users`） |
| [tests/test_assets.py](backend/tests/test_assets.py) | 8 条集成测试（见 §2.6） |

### 2.2 修改文件

| 文件 | 变更 |
|---|---|
| [pyproject.toml](backend/pyproject.toml) | dependencies 增加 `boto3`、`pillow`、`python-multipart` |
| [app/main.py](backend/app/main.py) | 引入 `lifespan`：启动时 `asyncio.to_thread(storage.ensure_bucket)`；注册 `assets.router` |
| [app/routers/health.py](backend/app/routers/health.py) | 健康检查并行探测数据库 + 对象存储，返回 `{"api", "database", "storage"}` |
| [app/models/__init__.py](backend/app/models/__init__.py) | 导出 `Asset`，供 Alembic autogenerate 发现 |
| [tests/conftest.py](backend/tests/conftest.py) | session 级 `bucket` fixture：确保测试桶存在 |
| [tests/test_health.py](backend/tests/test_health.py) | 期望补 `storage: "ok"` |
| [.env.example](.env.example) | 已有 S3 四件套 + `S3_URL_TTL`，无改动 |

### 2.3 模块依赖图

```
storage
  ├─ config.get_settings ─ s3_endpoint / s3_access_key / s3_secret_key / s3_bucket / s3_url_ttl
  └─ boto3.client("s3") ─ endpoint_url=MinIO, signature s3v4

services/images.probe(data) -> ImageMeta
  └─ PIL.Image ─ 尺寸 / 模式 / 格式 / 完整解码（截断即拒）

services/assets.create_from_bytes
  ├─ services/images.probe          ← 校验 + 元信息
  ├─ storage.put                    ← 写 `users/{user_id}/{asset_id}.{ext}`
  └─ models.Asset + session.commit

routers/assets
  ├─ deps.CurrentUser       ← 登录态
  ├─ services.images.probe  → ImageRejected → HTTP 422/413
  └─ services.assets        → AssetOut.of(storage.signed_url)

main.lifespan → storage.ensure_bucket（启动时建桶，幂等）
health → asyncio.gather(db probe, storage.ensure_bucket)
```

### 2.4 关键决策与理由

| 决策 | 理由 |
|---|---|
| 格式以 PIL 解码结果为准，不采信 Content-Type / 扩展名 | 客户端声明不可信；伪装扩展名的 JP/Png 会被如实按 JPEG 归档，校验逻辑单一、可测 |
| `storage.py` 用 `asyncio.to_thread` 包 S3 同步调用 | boto3 是阻塞同步库；放入线程池避免卡住事件循环，后续 worker 复用同一封装 |
| 存储 key：`users/{user_id}/{asset_id}.{ext}` | S2 文档预告的隔离前缀；`asset_id` 为唯一键，天然防重名覆盖 |
| 桶探针用 `storage.ensure_bucket`（head 失败则 create） | 幂等且兼作健康检查；MinIO 未就绪时 head 抛 `ClientError` → 报 error |
| `get_for_user` 用 `id + user_id` 联合条件 | 越权访问落到"行不存在"，对外统一 404，不泄露资源存在性 |
| `Url Out`：`storage.signed_url` 用短时签名（900s） | 对象存储不公开、不公读；前端 `<img>` 直接加载签名 URL，无需代理层 |
| `ImageRejected` 不携带 HTTP 状态 | service 层只表达"此图不可用"；具体映射（413/422）由路由层决定 |
| `MAX_PIXELS=50_000_000` + `image.load()` 全解码 | 防 DecompressionBomb（PIL 默认阈值会炸大图）；触发完整解码以暴露截断/损坏数据 |
| `kind` / `source` 用 `VARCHAR(16)` + ORM `StrEnum` | 不建原生 ENUM：Alembic 简单、未来可加枚举值；ORM 层类型安全仍在 |
| health 探测数据库 + 存储用 `asyncio.gather` | 并行探测，互不阻塞；任一失败只降级该字段，不影响整页 200 |

### 2.5 数据库迁移

文件：[backend/migrations/versions/20260923_assets.py](backend/migrations/versions/20260923_assets.py)，`down_revision = "fc1d3a92f7ec"`（S2 的 users 迁移）。

```python
def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("image_format", sa.String(length=8), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("has_alpha", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(op.f("ix_assets_user_id"), "assets", ["user_id"], unique=False)

def downgrade() -> None:
    op.drop_index(op.f("ix_assets_user_id"), table_name="assets")
    op.drop_table("assets")
```

应用方式：`cd backend && uv run alembic upgrade head`。

### 2.6 测试用例

| 用例 | 断言 |
|---|---|
| 上传 320×200 PNG | 201；`width/height/image_format/kind` 正确；`url` 含 `X-Amz-Signature` |
| RGBA 上传 | `has_alpha=true` |
| 损坏字节流 | 422 |
| GIF | 422（白名单外） |
| JPEG 伪装成 `a.png` | `image_format=JPEG` |
| 未登录上传 | 401 |
| 越权隔离：用户乙读甲的 asset | 详情 404；列表为空 |
| `probe(16×16)` | 抛 `ImageRejected` |

`conftest.py` 增加 session 级 `bucket` fixture（`ensure_bucket()`），并保留按测试清空 `users` 的 `cleanup_users`（assets 联级清理无需单独写）。

### 2.7 健康检查

```python
database, object_storage = await asyncio.gather(
    _probe(session.execute(text("select 1"))),
    _probe(asyncio.to_thread(storage.ensure_bucket)),
)
return {"api": "ok", "database": database, "storage": object_storage}
```

## 3. 前端实现

### 3.1 新增文件

| 文件 | 职责 |
|---|---|
| [src/api/assets.ts](frontend/src/api/assets.ts) | `upload(file)` / `list(limit)`；`Asset` 类型、`MAX_UPLOAD_BYTES`、`ACCEPTED_TYPES` |
| [src/hooks/useAssets.ts](frontend/src/hooks/useAssets.ts) | `checkFile()` 前置校验；`useAssets()` 列表查询；`useUploadAsset()` 上传 mutation（成功 invalidate 列表） |
| [src/lib/format.ts](frontend/src/lib/format.ts) | `formatBytes`（B/KB/MB）、`formatDateTime`（zh-CN 月/日 时:分） |
| [src/components/ImageDropzone.tsx](frontend/src/components/ImageDropzone.tsx) | 拖拽/点击选图；前置校验；拖拽态高亮；错误文案 |
| [src/components/AssetCard.tsx](frontend/src/components/AssetCard.tsx) | 素材卡片：图 + 透明底角标 + 元信息 |
| [src/pages/CreatePage.tsx](frontend/src/pages/CreatePage.tsx) | 创作页：上传区 + 历史素材网格；替换 S3 占位页 |

### 3.2 修改文件

| 文件 | 变更 |
|---|---|
| [src/App.tsx](frontend/src/App.tsx) | `/create` 由 `PlaceholderPage` 换成 `CreatePage` |

上传走原生 `fetch`（FormData，不设 `Content-Type`），复用 `ApiError` 解析错误 `detail`；列表复用 react-query `['assets']` 键。

### 3.3 关键决策与理由

| 决策 | 理由 |
|---|---|
| 上传不经过 `api.client.ts` 的 `request()` | 后者强制 `Content-Type: application/json`；FormData 需让浏览器自填 boundary |
| 前端 `checkFile` 先挡类型与体积 | 白跑网络请求成本高；大文件 / 错类型立即提示 |
| 上传 mutation `onSuccess` 做 `invalidateQueries(['assets'])` | 列表自动刷新，新素材自然到最前；不手工 splice 列表 |
| 卡片 `<img>` 直接引用签名 URL | 无需后端代理；URL 15 分钟过期，作为轻量缓存也够卡片展示 |
| `ACCEPTED_TYPES` 与后端白名单一致 | 单一事实在前端校验处，减少前后端不一致 |
| CreatePage 空态展示"还没有素材" | 首次访问不空白，引导上传 |

## 4. 完成度矩阵（S3 增量）

| 模块 | 状态 |
|---|---|
| `app/storage.py`（bucket / put / get / delete / signed_url） | ✓ 完成 |
| `app/services/images.py`（probe + 校验） | ✓ 完成 |
| `app/services/assets.py` | ✓ 完成 |
| `app/models/asset.py` + 导出 | ✓ 完成 |
| `app/schemas/asset.py` | ✓ 完成 |
| `app/routers/assets.py` 三条 API | ✓ 完成 |
| `main.lifespan` 建桶 + 注册路由 | ✓ 完成 |
| `health` 增加 storage 探针 | ✓ 完成 |
| `assets` 表迁移 | ✓ 完成 |
| `tests/test_assets.py`（8 用例）+ conftest bucket | ✓ 完成 |
| 前端 `api/assets.ts` / `hooks/useAssets.ts` | ✓ 完成 |
| 前端 `ImageDropzone` / `AssetCard` / `CreatePage` | ✓ 完成 |
| `App.tsx` 路由替换 | ✓ 完成 |

## 5. 验证步骤

```bash
# 1. 应用迁移
cd backend && uv run alembic upgrade head

# 2. 测试
uv run pytest tests/test_assets.py tests/test_health.py -v

# 3. 手工验证（前后端各自起 dev）
# /create → 拖入一张 PNG → 上传成功，卡片出现在网格顶部
# 上传损坏文件 → 错误提示，列表不变
# 刷新 → 素材仍在（签名 URL 重新签发）
```

## 6. 已知问题 / 后续清理

| 编号 | 描述 | 归属 |
|---|---|---|
| K1 | `Bucket` 未做版本控制 / 生命周期清理，长期使用会堆积 | 对象存储运维里程碑 |
| K2 | 无删除素材 API（对象与 DB 行都留着） | 后续（编辑/批量完成后） |
| K3 | 列表无分页游标，`limit` 上限 200 即上限 | 素材量大时再加 |
| K4 | 未做上传限流；本地开发无影响 | 生产安全迭代 |
| K5 | 测试依赖 MinIO 已启动；未启动时 `test_assets.py` 失败 | 同 `test_auth.py` 对 postgres 的依赖 |

## 7. 后续路线图

1. **S3 后半 / S4**：文生图链路（`ImageProvider` mock/dashscope）把生成图写入 `assets`（`kind=generated`、`source=generate`）
2. **S4 编辑**：编辑会话输入 = `assets` 中 `kind=original` 的记录；主体/背景/遮罩等 `kind` 落地
3. **S10 导出**：物料包作为 `kind=export` 走同一存储封装
4. **S11 批量**：arq worker 复用 `storage` 的线程封装写入结果