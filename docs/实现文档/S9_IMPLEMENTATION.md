# S9 实现文档：编辑会话、画布骨架

> 项目：pic-retouch-agent
> 里程碑：S9
> 日期：2026-09-24
> 参考实现：`ai-picture-editor` 提交 `e2c84f5`（feat: 编辑会话、画布骨架）

## 1. 仓库状态变化

| 提交 | 内容 |
|---|---|
| S1–S8（已存在） | 脚手架 / 本地基础设施 / 账号体系 / 素材上传 / 品牌化 / 文生图链路 / 测试清理 / 启动入口 / favicon |
| **S9（本里程碑）** | 编辑会话域（三表 + REST API） + 画布骨架（Konva 查看器 + 工具栏 + 图片墙 + 图层侧栏 + 会话侧栏） |

后端 10 个变更 + 1 个迁移 + 1 个测试文件；前端 11 个新增/变更。新增依赖：无（`konva`/`react-konva`/`zustand` 已在 S7 引入）。

**对齐说明**：现有迁移链尾为 `9091f7ebd312`（S8 timestamptz），与参考项目新迁移的 `down_revision` 一致；本里程碑迁移直接复用参考 `3565fae4ae0f`（edit sessions），无需调整链头。

## 2. 后端

### 2.1 画布文档结构 `backend/app/layers.py`（新增）

```python
BASE_LAYER_ID = "base"

class LayerKind(enum.StrEnum):
    IMAGE = "image"   # 本里程碑只落 image
    TEXT = "text"
    SHAPE = "shape"

class Transform(BaseModel):
    x: float = 0; y: float = 0
    scale_x: float = 1; scale_y: float = 1
    rotation: float = 0

class Layer(BaseModel):
    id: str; kind: LayerKind; name: str
    width: int; height: int
    asset_id: uuid.UUID | None = None
    transform: Transform = Field(default_factory=Transform)
    opacity: float = 1; visible: bool = True; locked: bool = False

class LayerDocument(BaseModel):
    width: int; height: int
    layers: list[Layer] = Field(default_factory=list)

def document_of(asset: Asset) -> LayerDocument:
    """以整张图为底图建文档；底图锁定，S10 拆层后被主体/背景层取代。"""
```

缩放存储为**倍率**而非像素，与视图 scale 解耦：文档自描述，画布适配/倍率是纯前端观察状态。

### 2.2 模型 `backend/app/models/edit_session.py`、`edit_history.py`（新增）

- `EditSession(UUIDBase)`：表 `edit_sessions`。`user_id`(FK users, CASCADE, index)、`title`(String80)、`original_asset_id` / `current_asset_id`(FK assets, RESTRICT)、`revision:int default 1`、`document:JSONB default dict`、`updated_at`(TIMESTAMPTZ, onupdate=func.now())。
- `SessionAsset(Base)`：表 `session_assets`。`session_id`+`asset_id` 联合主键（各自 FK CASCADE），`position:int`。空会话存在（可随后追加）。
- `EditHistory(UUIDBase)`：表 `edit_history`。`(session_id, seq)` 联合唯一；`user_id`、`session_id`(FK CASCADE, index)、`seq:int`、`action:String(48)`、`params:JSONB`、`result:JSONB`。`HISTORY_LIMIT=20`。
- `models/__init__.py` 导出新模型（Alembic autogenerate 可见）。

### 2.3 Schema `backend/app/schemas/session.py`（新增）

- `SessionCreateIn`：`current_asset_id` 必填、`asset_ids:list[uuid]`（≤`MAX_WALL_ASSETS=12`）、`title` 可选。
- `SessionPatchIn`：`title` / `current_asset_id` 可选。
- `SessionOut`：`id/title/revision/original_asset_id/current_asset_id/created_at/updated_at`，`of()` 工厂。
- `SessionDetailOut(SessionOut)`：追加 `document:LayerDocument`（`model_validate`，坏 JSON 会被 pydantic 挡下）、`assets:list[AssetOut]`；`of_detail()` 工厂。
- `HistoryOut`：`seq/action/params/result/created_at`，`of()`。
- `routes/runs.ts`、`schemas/run.py` 补 `session_id` 可选字段（本次不落库，仅返回引用）。

### 2.4 服务层 `backend/app/services/sessions.py`（新增）

- `SessionNotFound` 异常；`normalize_title()`：折叠空白 → 截断 ≤80 → 空则 `未命名会话`。
- `create()`：建记录（文档初始化）、flush → `_attach([current, *wall])` → `_append_history("create_session")` → commit。
- `_attach()`：查询现有 `session_id` 的 asset 集合去重，从当前 `max(position)+1` 起连续排号，只增不改。
- `_append_history()`：`max(seq)+1`，随后 `delete(seq <= seq - HISTORY_LIMIT)`，保证最多 20 条。
- `get_for_user()` / `list_for_user()`（updated_at desc, limit≤50）/ `assets_of()`（join SessionAsset order by position）/ `history_of()`（seq desc）。
- `rename()`、`switch_current()`：同一图 `current_asset_id` 不变则 revision 不动；变则 `revision+=1`、`document` 重建为该图、`_attach([asset])`、写 `switch_current` 历史（result 含 revision）。

### 2.5 路由 `backend/app/routers/sessions.py`（新增）

- `router = APIRouter(prefix="/sessions")`，挂 `/api`。
- 复用 `assets.get_for_user` → 404「素材不存在」；`sessions.get_for_user` → 404「会话不存在」。
- `_detail()`：`assets_of` → `SessionDetailOut.of_detail`（懒加载 signed url）。
- 端点：`POST ""`(201)、`GET ""`、`GET "/{session_id}"`、`PATCH "/{session_id}"`（先 title 后 switch，均只处理出现字段）、`GET "/{session_id}/history"`。
- `main.py` 挂载 `sessions` router。

### 2.6 迁移 `backend/migrations/versions/20260924_s9_edit_sessions.py`（新增）

`revision="3565fae4ae0f"`、`down_revision="9091f7ebd312"`。参考项目原样（三表 + 索引 + 约束；`update_at` server_default now）；`updated_at` 的 `onupdate=func.now()` 由 ORM 层负责，迁移不依赖 DB trigger。

### 2.7 测试 `backend/tests/test_sessions.py`（新增，10 用例）

参考项目配套，覆盖：

| 用例 | 断言 |
|---|---|
| 新建会话首版 revision=1、标题规范化 | title 折叠、revision=1、original==current |
| 文档描述当前图为底图层 | width/height、单层 kind=image、locked=True、asset_id 正确 |
| 空标题兜底 | `未命名会话` |
| 未采用候选留在图片墙 | assets 顺序含 [current, *others] |
| 切换当前图修订号+1 | revision=2、文档尺寸更新、新图进墙 |
| 切换同一图 revision 不变 | 保持 1 |
| 历史记录创建与切换 | actions == [switch_current, create_session]（seq 降序） |
| 未知素材 404 | POST sessions 404 |
| 未登录 401 | GET sessions/session 均 401 |
| 会话按用户隔离 | 换号后他人会话 404、列表空 |

依赖 `tests/test_assets.py` 的 `make_image` / `upload_payload` 构造图片。

## 3. 前端

### 3.1 API 类型 `frontend/src/api/sessions.ts`（新增）

`LayerKind`/`Transform`/`Layer`/`LayerDocument`/`Session`/`SessionDetail`/`HistoryEntry`/`SessionCreateInput`/`SessionPatchInput`；`ACTION_LABELS = { create_session: '新建会话', switch_current: '切换当前图' }`；`sessionsApi.{create,list,get,patch,history}`。

### 3.2 React Query hooks `frontend/src/hooks/useSessions.ts`（新增）

- `useSessions()`：list，key `['sessions']`。
- `useSession(id)`：detail，key `['session', id]`，`enabled: Boolean(id)`。
- `useSessionHistory(id)`：history，key `[..., 'history']`。
- `useCreateSession()`：成功后 `setQueryData(detailKey, detail)` 提前命中 + invalidate list。
- `usePatchSession(id)`：成功后 update detail + invalidate list + history。

### 3.3 画布观察状态 `frontend/src/stores/canvasView.ts`（新增）

zustand store：`{scale, x, y, viewport}` + `setViewport / fit / zoomBy / zoomTo / pan`。

- `MIN_SCALE=0.05`、`MAX_SCALE=8`、`ZOOM_STEP=1.2`、`FIT_RATIO=0.92`（留边）。
- `fit()`：取 viewport 内适合的倍率居中；`zoomBy(factor, anchor)`：以锚点为不动点（默认视口中心），保证滚轮处画面不漂移。
- 纯观察状态，不参与导出。

### 3.4 小工具 hooks（新增）

- `useElementSize`：`ResizeObserver` 监听容器 `contentRect`，返回 `[ref, size]`，供 Konva Stage 用显式宽高。
- `useCanvasImage`：URL → `HTMLImageElement`，`onload` 后置 state；切换 URL 先返回 `null`，避免新旧解码竞态残留；卸载后到达的 `onload` 不更新废弃 state。

### 3.5 编辑器组件（新增 `frontend/src/components/editor/`）

- `CanvasStage.tsx`：Stage 铺满容器，`scale/x/y` 来自 store；底层白纸 Rect(文档尺寸，深色投影)，image 层渲染可见 image 层。监听 wheel（`preventDefault` + 按指针锚点缩放）、drag（pan）。`fit` 仅在画幅或视口变化时触发一次（`fitted` ref 缓存 shape），避免覆盖手动调整。
- `EditorToolbar.tsx`：`TitleField`（draft 跟随服务端，Enter/失焦提交，Escape 还原）、尺寸 + 「第 N 版」、缩放组（`－ / % / ＋ / 适应`）、`图层`开关（`aria-pressed`）。
- `ImageWall.tsx`：横滑条，`size-16` 缩略图，`remaining` 按 `current_asset_id` 高亮，`disabled={patch.isPending}`，开关 `title` 显示 kind/尺寸；`KIND_LABELS` 复用资产 kind 中文名。
- `LayerPanel.tsx`：三段——图层列表（name/尺寸/已锁定）、属性（画布/修订号/格式/大小/透明通道）、编辑记录（`ACTION_LABELS` + `formatDateTime`）。
- `SessionSidebar.tsx`：「新对话」→ `/create`；`useSessions` 列历史（标题 + 时间），`NavLink` 高亮当前，空态文案。

### 3.6 页面接线

- `EditorPage.tsx`（新增）：`/editor/:sessionId`。有 id → `Workspace`（toolbar + canvas + imageWall，右侧 `LayerPanel` 按开关抽屉）；无 id → 空态 Notice（「选择一个会话」+ 去创作链接）；`useSession` 404 → 会话不存在空态。`urls` Map 由 `assets` 生成，供画布取图。
- `CandidatesPage.tsx`（改）：`useCreateSession` 接入，`adopt()` 用 `picked` 建会话（`asset_ids`=候选全部、`title`=prompt 兜底），成功后 `navigate('/editor/{id}')`；按钮 pending 态文案「打开中…」。
- `CreatePage.tsx`（改）：`useCreateSession` 接入；上传成功 / 点历史素材 → `openEditor(id)` 建会话跳转；两处按钮 `disabled` 增加 `createSession.isPending`。
- `App.tsx`（改）：`/editor`、`/editor/:sessionId` 指向 `EditorPage`（替换占位页）。

## 4. 关键决策与理由

| 决策 | 理由 |
|---|---|
| `SessionAsset` 独立多对多、`position` 显式 | 图片墙顺序稳定且可挂未采用候选；不覆盖旧图 |
| `document` JSONB 全量存图 | 画布状态唯一权威，改一处即快照；S10+ 增量由 history 承担 |
| `revision` 递增 | 判定旧选区/遮罩失效，避免脏状态；S10+ 天然支持 |
| 视图态（scale/pan）前端 store、不入库 | 纯 UX 状态；图层真实几何存 `document`，导出用文档而非视图 |
| `history` 有界 20 条线性 | 简单可预测；版本树/分支属非范围 |
| 切换当前图重建文档（`document_of`） | 每个候选都是全新画布基础；切换即新版本语义 |
| Konva（非 Canvas2D 手写） | 已在依赖中；缩放/平移/后续图层拖拽是现成能力 |
| 复用参考项目迁移 ID `3565fae4ae0f` | 本项目迁移链尾与本提交链头完全一致，直接继承降本 |

## 5. 验证与验收对照

| 验收 | 验证方式 |
|---|---|
| AC1/AC2 | `pytest`；手动走候选页/创作页 → 编辑页 |
| AC3/AC8 | `test_switching_current_image_bumps_revision` 等（revision、文档、history 断言） |
| AC7 | `test_session_requires_authentication` / `test_sessions_are_isolated_per_user` |
| AC9 | `pytest -q`（全部含新增）；`npm run lint`、`npm run build` |
| AC5/AC6 | 前端手动验证（缩放/平移/空态） |

> 画布骨架为纯查看器，本次无前端单测框架；视觉与交互以手动核对为准，并在 S10 引入编辑动作后再补组件测试。