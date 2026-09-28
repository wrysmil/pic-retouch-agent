# S3 需求文档：素材上传、对象存储

> 项目：pic-retouch-agent（AI 修图智能体）
> 里程碑：S3 — 素材上传 + 对象存储
> 日期：2026-09-23
> 前置里程碑：S1（脚手架 / 基础设施）、S2（账号体系 + 落地页，已完成）
> 后续里程碑：S4（编辑）、S10（物料导出）、S11（批量）

## 1. 背景与目标

S2 完成后，用户已经能注册、登录，工作台 `/create` 也收回到登录态。但 `/create` 还是一个占位页，用户没有任何方式把商品图放进系统，对象存储（MinIO/S3）也尚未被任何业务代码使用。

S3 打通第一条素材链路：用户把图片上传到系统，系统校验图片合法性、提取元信息、写入对象存储并落库。之后的所有里程碑（文生图、编辑、导出）都基于这条素材库。

**为什么这一里程碑独立**：素材是所有下游操作的输入与产出容器。先建立「上传 → 校验 → 物理存储 → 元数据归档 → 列表/归属读取」的闭环，并定下 `users/{user_id}/...` 的存储前缀、`assets` 表的归属模型，S4 起的生成图、编辑产物、导出物料才能按同一套规则落位。

## 2. 用户与场景

| 角色 | 场景 |
|---|---|
| 登录用户 | 在 `/create` 拖入或点选一张商品图 → 上传 → 出现在"历史素材"网格 |
| 登录用户 | 刷新页面后，历史素材仍在（从对象存储读取签名 URL 展示） |
| 用户 A | 只能看到自己的素材；不能读取他人素材 |
| 拍图用户 | 上传超过 20 MB 的图片 → 前端直接拦截，不发起网络请求 |
| 误操作用户 | 上传非图片 / 损坏图片 → 得到明确的错误提示，素材列表不受影响 |

## 3. 功能需求

### 3.1 上传 F1

- **F1.1** 登录用户在 `/create` 的拖拽区（点击或拖入）选择 `image/jpeg` / `image/png` / `image/webp` 单张图片
- **F1.2** 前端前置校验：类型必须在白名单内；体积不超过 `20 MB`。不合规直接提示，不发请求
- **F1.3** `POST /api/assets`（multipart/form-data，字段名 `file`）上传成功返回 `201`，响应体为素材对象（见 §5）
- **F1.4** 上传成功后，历史素材网格自动刷新，新素材出现在最前
- **F1.5** 上传进行中，拖拽区显示"上传中…"并禁用，防止重复提交

### 3.2 图片校验 F2

服务端以下述规则校验，格式**以实际解码结果为准，不采信文件扩展名**：

- **F2.1** 空文件 → 拒绝
- **F2.2** 文件超过 `20 MB` → `413 文件超过 20 MB 上限`
- **F2.3** 无法解码或解码后数据损坏（截断 / 畸形）→ `422 文件已损坏或不是受支持的图片`
- **F2.4** 解码出的格式不在 JPG/PNG/WebP 白名单 → `422 仅支持 JPG、PNG 与 WebP`
- **F2.5** 最短边小于 `32` 像素 → `422 图片过小，最短边需不小于 32 像素`
- **F2.6** 像素总量超过 `50_000_000`（防 DecompressionBomb）→ `422 图片像素总量过大`
- **F2.7** 伪装扩展名（PNG 内容叫 `a.jpg`，或 JPEG 内容叫 `a.png`）— 按解码出的真实格式记录，不拒绝。这是"格式以解码为准"的必然推论，也是极佳的反诈校验

### 3.3 元信息提取 F3

服务端从图片解码结果提取并落库：

- **F3.1** `image_format`：JPEG / PNG / WEBP（解码结果）
- **F3.2** `width`、`height`：像素尺寸
- **F3.3** `size_bytes`：原始字节数
- **F3.4** `has_alpha`：像素模式含透明通道（RGBA/LA/PA 或含 transparency 信息）

### 3.4 素材列表 F4

- **F4.1** `GET /api/assets` 返回当前用户全部素材，按 `created_at` 倒序
- **F4.2** `limit` 查询参数：`1–200`，默认 `50`
- **F4.3** 每项含 `url`——**短时签名 URL**（默认 15 分钟），前端 `<img>` 直接引用
- **F4.4** 未登录访问 → `401 未登录或会话已过期`

### 3.5 素材详情 F5

- **F5.1** `GET /api/assets/{asset_id}` 返回单个素材对象
- **F5.2** 素材不存在，或**不属于当前用户** → `404 素材不存在`（不区分，防越权探测）
- **F5.3** 越权读取他人素材 → 同样 `404`

### 3.6 素材卡片展示 F6

- **F6.1** 卡片头：素材图（`object-contain`，透明底可用）
- **F6.2** `has_alpha` 为真的卡片叠「透明底」角标
- **F6.3** 卡片体：`宽 × 高`、`格式 · 大小`、`上传时间（月/日 时:分）`
- **F6.4** 网格布局：移动端 2 列、平板 3 列、桌面 4 列

## 4. 非功能需求

| 编号 | 类别 | 描述 |
|---|---|---|
| NFR1 | 安全 | 素材按 `user_id` 隔离：对象存储 key 前缀 `users/{user_id}/...`；DB 查询始终带 `user_id` 条件；详情接口越权返回 404 |
| NFR2 | 安全 | 元数据不依赖客户端声明（Content-Type、扩展名均不可信），以 PIL 实际解码结果为准 |
| NFR3 | 安全 | `POST /api/assets` 需要登录（`CurrentUser` 依赖） |
| NFR4 | 性能 | 上传 → 返回 < 500ms（本地 MinIO）；对象读写通过 `asyncio.to_thread` 不阻塞事件循环 |
| NFR5 | 成本 | 对象存储 URL 采用短时签名（默认 900s），不公开桶策略、不做永久公读 |
| NFR6 | 健壮 | `assets` 表 `storage_key` 唯一；`user_id` 外键 `ondelete=CASCADE`（删用户连带清素材） |
| NFR7 | 可测 | 上传成功 / 损坏 / 非白名单 / 伪装扩展名 / 空文件 / 未登录 / 越权隔离 / 最小边长 共 8 条核心用例 |
| NFR8 | 一致 | 后端沿用 `SessionDep` + `CurrentUser` 依赖风格；前端沿用 react-query 缓存 + mutation 模式 |

## 5. API 设计

| 方法 | 路径 | 鉴权 | 成功响应 | 失败响应 |
|---|---|---|---|---|
| POST | `/api/assets` | Cookie | 201 素材对象 | 401 未登录 / 413 超 20MB / 422 校验不通过 |
| GET | `/api/assets` | Cookie | 200 素材对象数组 | 401 |
| GET | `/api/assets/{asset_id}` | Cookie | 200 素材对象 | 401 / 404 不存在或越权 |

素材对象结构：

```json
{
  "id": "uuid",
  "kind": "original",
  "source": "upload",
  "image_format": "PNG",
  "width": 320,
  "height": 200,
  "size_bytes": 12345,
  "has_alpha": false,
  "created_at": "2026-09-23T12:00:00Z",
  "url": "http://localhost:7313/retouch/users/...?...X-Amz-Signature=..."
}
```

错误响应体遵循 FastAPI 默认 `{detail: "<message>"}`（本里程碑 `kind` 恒为 `original`、`source` 恒为 `upload`，字段为后续里程碑预置）。

## 6. 数据模型

新增 `assets` 表（第二个 Alembic 迁移，依赖 `users` 表）：

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | UUID | PK | 默认 `uuid.uuid4()` |
| user_id | UUID | NOT NULL, FK→users.id, ON DELETE CASCADE, INDEX | 归属用户 |
| kind | VARCHAR(16) | NOT NULL | `original` / `generated` / `subject` / `background` / `mask` / `marketing` / `export` |
| source | VARCHAR(16) | NOT NULL | `upload` / `generate` / `tool` |
| storage_key | VARCHAR(255) | NOT NULL, UNIQUE | 对象存储 key，`users/{user_id}/{asset_id}.{ext}` |
| image_format | VARCHAR(8) | NOT NULL | JPEG / PNG / WEBP |
| width | INTEGER | NOT NULL | 像素宽 |
| height | INTEGER | NOT NULL | 像素高 |
| size_bytes | INTEGER | NOT NULL | 字节数 |
| has_alpha | BOOLEAN | NOT NULL | 是否有透明通道 |
| created_at | TIMESTAMP | NOT NULL, server default `now()` | 创建时间 |

`kind` / `source` 用 `String(16)` 而非原生 ENUM：Alembic 生成更简单、演进更灵活（枚举只出现在 ORM 层，用 `StrEnum` 约束）。

## 7. 技术约束

**本里程碑新增依赖**（对齐参考实现的声明）：

| 类别 | 选型 |
|---|---|
| 对象存储客户端 | `boto3`（S3 兼容 API，指向 MinIO） |
| 图片解码 / 校验 | `Pillow`（PIL） |
| 上传解析 | `python-multipart`（FastAPI 表单依赖） |

后端：FastAPI + SQLAlchemy 异步 + Alembic（既有）。
前端：React 19 + react-query + Tailwind v4（既有），无新增 npm 依赖。

## 8. 验收标准

| 编号 | 描述 |
|---|---|
| AC1 | `POST /api/assets` 上传 320×200 PNG，返回 201；响应含 `width=320`、`height=200`、`image_format=PNG`、`kind=original`；`url` 含 `X-Amz-Signature` |
| AC2 | RGBA 图片响应 `has_alpha=true`；RGB 图片 `has_alpha=false` |
| AC3 | 上传损坏字节流返回 422 |
| AC4 | 上传 GIF 返回 422（仅 JPG/PNG/WebP） |
| AC5 | JPEG 内容伪装成 `a.png` 上传，响应 `image_format=JPEG`（以解码为准） |
| AC6 | 未登录上传返回 401 |
| AC7 | 用户乙 GET 用户甲的 `asset_id` 返回 404；`GET /api/assets` 不含甲的素材 |
| AC8 | `probe()` 对 16×16 图片抛 `ImageRejected` |
| AC9 | 对象存储内存在 `users/{user_id}/{asset_id}.png` 键，且 `GET /api/assets` 返回的签名 URL 可直接访问 |
| AC10 | 前端 `/create`：上传成功 → 历史素材网格顶部出现新卡片；上传损坏文件 → 页面显示错误文案；刷新后素材仍在 |
| AC11 | `pytest backend/tests/test_assets.py` 全部通过；`pytest backend/tests/test_health.py` 通过（健康检查多一项 `storage: ok`） |

## 9. 范围与非范围

**本里程碑范围**：

- 上传 / 列表 / 详情 三条 API
- `assets` 表 + Alembic 迁移
- 图片校验与元信息提取（PIL）
- 对象存储封装：bucket 确保、put/get/delete、签名 URL（`storage.py`）
- 健康检查增加对象存储探针
- 前端：`/create` 创作页替换占位页（拖拽上传 + 历史素材网格）

**本里程碑非范围（留给后续里程碑）**：

- 文生图、候选选图（S3 后续 / 参考实现 S4+）
- 删除素材、重命名、打标签
- 素材编辑（主体/背景/遮罩/营销图等 `kind` 的产物写入）
- 分页 / 游标（列表先固定 `limit`）
- 断点续传、分片上传、秒传（大文件通路）
- 对象存储的访问日志、生命周期（过期清理）

## 10. 后续依赖

- **S4 编辑**：编辑会话的输入出自 `assets`（`kind=original`），产物写回 `assets`（`kind=generated` 等）
- **S10 物料导出**：导出文件作为 `kind=export` 素材归档，URL 走同一条签名通道
- **S11 批量任务**：arq 任务处理结果按 `user_id` 写入对象存储，`storage.py` 的 `asyncio.to_thread` 封装可直接复用