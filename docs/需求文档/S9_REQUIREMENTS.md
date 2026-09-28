# S9 需求文档：编辑会话、画布骨架

> 项目：pic-retouch-agent（AI 修图智能体）
> 里程碑：S9 — 编辑会话与画布骨架
> 日期：2026-09-24
> 前置里程碑：S8（已完成，品牌 favicon）
> 后续里程碑：S10+（真实操作：拆层、选区、遮罩、重绘，由编辑记录驱动）

## 1. 背景与目标

目前产品已经打通「文生图 → 候选选图 → 素材库」链路（S7），上传与生成的图片都只是躺在素材库里。用户选中一张图后没有地方继续编辑：没有一个把「这张图 + 它的操作历史」绑定在一起的容器。

S9 建立**编辑会话**域：

1. **会话**：用一张图片作为"当前画布"，把多次操作累积成一份文档，历史素材与操作记录挂在本会话下。
2. **画布骨架**：可缩放平移的查看器，展示"画布文档"（当前图作为底图层），为后续拆层/选区/遮罩预留结构位置。
3. **图片墙**：同批生成的候选、之后切换得到的图像全部挂在会话内，随时切回，旧结果不覆盖。
4. **历史侧栏**：展示会话内发生的动作记录，供后续"撤销/回到某步"使用。

> 参考实现：`ai-picture-editor` 提交 `e2c84f5`（feat: 编辑会话、画布骨架）。本里程碑按其结构落地到本项目 S1–S8 的既有设施之上。

## 2. 用户与场景

| 角色 | 场景 |
|---|---|
| 创作者 | 在候选页挑一张进入编辑，得到带图像墙和图层列表的编辑工作台 |
| 创作者 | 编辑中想换当前图，点图片墙任意一张当前会话内图片即可切换，不会丢旧图 |
| 创作者 | 关闭页面后从历史会话列表回来，文档与图片墙仍在 |
| 创作者 | 通过会话侧栏回到创作页开启新的生成 |

## 3. 功能需求

### 3.1 编辑会话领域 F1

- **F1.1** 会话 `EditSession`：归属 user；`title`（≤80 字符）；`original_asset_id`（首个正片）；`current_asset_id`（当前画布图）；`revision`（修订号，从 1 起）；`document`（画布文档 JSON 权威）;`created_at` / `updated_at`。
- **F1.2** 会话图片墙 `SessionAsset`：`session_id` + `asset_id` 联合主键；`position` 显式序号，保证图片墙顺序稳定（同一事务多行时间戳相同，不靠时间排序）。
- **F1.3** 会话图片墙不覆盖任何已有结果：切换当前图只追加，不改旧行。
- **F1.4** 编辑记录 `EditHistory`：`session_id` + `seq` 连续递增（联合唯一）；记录 `action`（如 `create_session`、`switch_current`）、`params`、`result`；**只保留最近 20 条**（`HISTORY_LIMIT=20`），超出即清理最旧的，线性记录不做版本树。

### 3.2 画布文档结构 F2

- **F2.1** `document` 为 `LayerDocument`：`width`、`height`、`layers[]`。
- **F2.2** 每个 layer：`id`（底图固定为 `"base"`）、`kind`（`image` / `text` / `shape`，本里程碑只有 `image`）、`name`、`width`、`height`、`asset_id`、`transform`（`x`/`y` 相对画布左上、`scale_x`/`scale_y` 倍率、`rotation`）、`opacity`、`visible`、`locked`。
- **F2.3** 新建会话时以整张图建文档：单图 `base` 层，`locked=true`，元数据照抄 `asset`。

### 3.3 后端 API F3

- **F3.1** `POST /api/sessions`：入参 `current_asset_id`（必填）、`asset_ids`（同批进图片墙的候选，≤12）、`title`（可选）。校验素材属于当前用户（否则 404）。返回 `SessionDetailOut`。当前图进入画布，其余仅进图片墙备选。写入创建历史。
- **F3.2** `GET /api/sessions`：当前用户会话列表，按 `updated_at` 降序，`?limit=`（1–200，默认 50）。
- **F3.3** `GET /api/sessions/{id}`：会话详情（文档 + 图片墙 assets）。
- **F3.4** `PATCH /api/sessions/{id}`：可 `title` 重命名、`current_asset_id` 切换当前图。切换图时 `revision+1`，文档重建为该图，图片墙追加上新图，写切换历史。
- **F3.5** `GET /api/sessions/{id}/history`：编辑记录列表，`seq` 降序。
- **F3.6** 越权约束：所有接口都按 `user_id` 过滤，未登录 401，他人会话/素材 404。

### 3.4 编辑器界面 F4

- **F4.1** 路由 `/editor` 与 `/editor/:sessionId`：无 `sessionId` 显示空态引导，有则加载工作台。
- **F4.2** 顶部工具栏：可重命名的标题（失焦/回车提交）、画布尺寸与修订号、缩放控件（缩小 / 百分比 / 放大 / 适应）、图层面板开关。
- **F4.3** 画布 `CanvasStage`：以 Konva Stage 渲染，监听容器尺寸，支持按锚点缩放（滚轮）与拖拽平移，画纸白底、深色投影自适应按文档尺寸 fit。
- **F4.4** 图片墙 `ImageWall`：横向滚动，展示会话内全部 assets（含未采用候选），当前图高亮，点击切换当前图。
- **F4.5** 图层面板 `LayerPanel`：右侧抽屉，含图层列表、当前图属性（画布/修订号/格式/体积/透明通道）、编辑记录（动作 + 时间，`create_session`/`switch_current` 中文标签）。
- **F4.6** 会话侧栏 `SessionSidebar`：左侧列出历史会话（标题 + 更新时间），「新对话」跳转创作页，当前会话高亮。

### 3.5 创作与候选页接线 F5

- **F5.1** 创作页：上传图片成功、点选历史素材后，直接创建会话并进入编辑页（`/editor/{sessionId}`）。
- **F5.2** 候选页：选一张 → 创建会话，`current_asset_id` 为选中图，`asset_ids` 为整批候选，`title` 用提示词兜底；成功跳转编辑页。未选中禁用按钮。

## 4. 非功能需求

| 编号 | 类别 | 描述 |
|---|---|---|
| NFR1 | 数据不变性 | 会话内图片墙只增不删，切换/操作不覆盖任何已有素材记录 |
| NFR2 | 隔离 | 会话、素材、编辑记录均按用户隔离，禁止跨用户访问 |
| NFR3 | 视图状态独立 | 画布倍率/位移是纯前端观察状态（`canvasView` store），不入库、不参与导出；图层变换另存于 `LayerDocument` |
| NFR4 | 修订语义 | `revision` 递增用于判定旧选区/遮罩失效，为 S10+ 的选区操作铺路 |
| NFR5 | 历史有界 | 编辑记录最多 20 条，防止无限膨胀 |
| NFR6 | 前端工程 | `tsc -b` + oxlint 通过；后端 pytest 通过 |

## 5. 验收标准

| 编号 | 描述 |
|---|---|
| AC1 | 从候选页挑一张"进入编辑"创建会话，进入 `/editor/{sessionId}`，画布显示该图底图，图片墙含整批候选 |
| AC2 | 从创作页上传图片 / 点历史素材同样进入编辑页并建会话 |
| AC3 | 点击图片墙另一张图，当前图切换、修订号 +1、文档重建为该图、新图进墙，历史新增 `switch_current` 记录 |
| AC4 | 修改标题失焦/回车后保存，会话列表标题同步 |
| AC5 | 工具栏缩放（缩小/放大/百分比/适应）与拖拽平移正常，滚轮以指针为锚点缩放不漂移 |
| AC6 | 无 `sessionId` 访问 `/editor` 显示空态引导，提供"去创作"按钮 |
| AC7 | 访问他人会话/素材返回 404，未登录返回 401 |
| AC8 | 会话详情 / 历史接口返回结构符合 F3，`document.layers[0].locked===true`，`revision` 从 1 起 |
| AC9 | `npm run build` + `npm run lint` 通过；`pytest` 全部通过（含新增 `test_sessions.py` 10 用例） |

## 6. 范围与非范围

**本里程碑范围**：

- 后端：`layers.py` 文档结构；`edit_sessions` / `session_assets` / `edit_history` 三表（Alembic 迁移）；`schemas/session.py`、`services/sessions.py`、`routers/sessions.py`；`runs`/`session` schema 与 API 接线
- 前端：`api/sessions.ts`、`hooks/useSessions.ts`、`stores/canvasView.ts`、编辑器五组件、`EditorPage`、创作页/候选页接线
- 路由：`/editor`、`/editor/:sessionId`

**本里程碑非范围**：

- 真实图像编辑操作（拆层、抠图、文字、遮罩、重绘）
- 撤销/重做、版本树
- 会话删除/分享
- `imagelayers` 之外的文本/形状图层编辑；图层增删、选中、拖拽变换
- 导出下载

## 7. 后续依赖

- S10+ 依赖本里程碑的 `document` 结构与 `EditHistory` 记录实现真实编辑动作。
- 选区/遮罩依赖 `revision` 判定失效：携带旧修订号的操作会被拒绝或要求刷新。