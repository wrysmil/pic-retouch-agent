# 工作台前端 UI 能力全量盘点（frontend/src，非 admin）

> 用途：编写 UI 测试计划的输入。覆盖 frontend/src 下 **全部** 应用页面、组件、hooks、stores、lib、api。
> 排除：admin 后台（frontend/src/admin、frontend/src/pages/Admin*.tsx、frontend/src/api/admin*.ts、frontend/src/components/admin）。
> 代码基线：`frontend/src/App.tsx` + `main.tsx` + 8 个页面 + 2 个布局 + 全部组件/hooks/stores/lib/api。

---

## 0. 全局结构与基础设施

### 0.1 启动与全局 Provider
- 入口 `frontend/src/main.tsx`
  - `StrictMode` 包裹（**测试注意：Effect 会双跑，SSE/EventSource 会被建两次**）
  - `@tanstack/react-query` `QueryClientProvider`，全局默认：`retry: 1`、`refetchOnWindowFocus: false`（无默认 staleTime）
  - 引入 `@/index.css`
- `frontend/src/App.tsx`：`<BrowserRouter>`，无全局 ErrorBoundary、无 Suspense fallback、无 i18n、无主题切换。

### 0.2 路由表（`App.tsx`）
| 路径 | 组件 | 是否需登录 | 备注 |
|---|---|---|---|
| `/` | `LandingPage` | 否 | 落地页 |
| `/auth` | `AuthPage` | 否（已登录则重定向 `/create`） | `?mode=register` 切注册 |
| `/create` | `CreatePage` | 是 | 创作页 |
| `/editor` | `EditorPage` | 是 | 无 sessionId → 显示「选择一个会话」 |
| `/editor/:sessionId` | `EditorPage` | 是 | 编辑器 |
| `/marketing` | `MarketingPage`(Picker) | 是 | 无 sessionId → 会话选择器 |
| `/marketing/:sessionId` | `MarketingPage`(Workspace) | 是 | 导出物料 |
| `/batch` | `BatchPage`(Compose) | 是 | 批量编排 |
| `/batch/:runId` | `BatchPage`(Watch) | 是 | 批量进度 |
| `/candidates/:runId` | `CandidatesPage` | 是 | 候选选图 |
| `*` | `<Navigate to="/" replace />` | — | 兜底重定向 |

- 后台 admin **不在此应用内**（独立 vite 入口 `vite.admin.config.ts`，端口 7303），路由表无 admin 项。

### 0.3 全局 HTTP 层（`api/client.ts`）
- 所有 JSON 请求前缀 `/api`，默认头 `Content-Type: application/json`。
- `api.get/post/patch/delete`；`204` 返回 `undefined`。
- 错误统一转 `ApiError{status,message}`；解析 FastAPI `detail`：
  - 数组（pydantic 校验）→ 每项取 `msg`/`message`，用 `；` 连接；
  - 剥离 `^Value error,\s*` 前缀；
  - 解析不出 → 用 `response.statusText` 作兜底文案。
- 上传/下载走原生 `fetch`，错误文案分别为 `上传失败` / `读取素材失败` / `打包失败`。
- **无请求拦截器、无 401 全局跳登录**（401 由各页各自的 Query/Mutation 状态处理）。

### 0.4 全局 Toast（`stores/toasts.ts` + `components/ToastHost.tsx`）
- 触发入口：模块级 `toast(text, tone, options)`，tone 仅 `'ok' | 'danger'`。
- 常量：`STAY_MS = 3200`、`STAY_WITH_ACTION_MS = 5200`、`LEAVE_MS = 180`；**同时最多保留 3 条**（`items.slice(-2)` 再 push）。
- 位置：`fixed inset-x-0 bottom-6`，居中列排。
- 点击提示文字本身 → 立即 dismiss；带 `action` 时额外渲染操作按钮（如「撤销」），点击后先执行 `run()` 再 dismiss。
- 触发点汇总（测试可断言的 toast 文案）：
  - `useSessionTools` 工具失败 → `errorMessage(error)` danger
  - 工具完成后 → `${ACTION_LABELS[tool]}完成`（ok）；若该工具在 `UNDOABLE` 集合内则附带「撤销」按钮
  - 工具 run 失败 → `live.error || '处理失败'` danger
  - `useExportPack` / `useExportBatch` / `useCreateBatch` 失败 → danger
  - `useSelection` 的 select/clear/replay 失败 → danger
  - `MarketingPage.download` / `BatchPage.Watch.download` 成功 → `已打包 N 张` ok
- **`ToastHost` 只挂在 `WorkbenchLayout` 内**：登录页/落地页不会有 toast 容器。

### 0.5 全局 Zustand Store
| Store | 用途 | 跨页持久 |
|---|---|---|
| `stores/canvasView` | 画布视图倍率/位移/适应 | 是（不随路由重置） |
| `stores/editorUi` | 编辑器 UI 态：选中图层、裁剪、对比、面板、选择模式、选区、预览 | 是（**跨会话不重置，切 sessionId 需注意残留**） |
| `stores/toasts` | 提示队列 | 是 |

### 0.6 后端 API 全表（前端实际调用）
**认证**
- `POST /api/auth/register`、`POST /api/auth/login`、`POST /api/auth/logout`、`GET /api/auth/me`

**素材**
- `POST /api/assets`（multipart `file`）
- `GET /api/assets?limit=50`
- `GET /api/assets/library?limit=50`

**生成任务**
- `POST /api/generations`
- `GET /api/runs/{runId}`
- `GET /events/runs/{runId}`（**SSE，注意：不带 `/api` 前缀**，Vite 代理 `/events` → 7302）

**会话**
- `POST /api/sessions`、`GET /api/sessions`、`GET /api/sessions/{id}`
- `PATCH /api/sessions/{id}`
- `GET /api/sessions/{id}/history`
- `POST /api/sessions/{id}/tools`（统一工具入口：`{tool, params}`）
- `POST /api/sessions/{id}/undo`、`POST /api/sessions/{id}/redo`
- `POST /api/sessions/{id}/selection`、`POST /api/sessions/{id}/selection/prepare`
- `GET /api/sessions/{id}/selection`、`DELETE /api/sessions/{id}/selection`
- `POST /api/sessions/{id}/exports`（ZIP 下载，body `{asset_ids}`）

**智能体对话**
- `GET /api/sessions/{id}/messages`
- `POST /api/sessions/{id}/messages`
- `POST /api/sessions/{id}/messages/{turnId}/confirm|cancel|retry`

**批量**
- `POST /api/batches`、`GET /api/batches`、`GET /api/batches/{id}`、`GET /api/batches/{id}/export`（ZIP）

**前端实际调用的 tool 名**（`POST /api/sessions/{id}/tools`）：
`crop_canvas`、`flip_layer`、`remove_background`、`upscale_image`、`split_layers`、`promote_object_to_layer`、`erase_region`、`replace_region`、`replace_background`、`expand_canvas`、`adjust_image`、`set_layer_visible`、`set_layer_opacity`、`scale_layer`、`rotate_layer`、`reorder_layer`、`set_layer_text`、`move_layer`、`generate_marketing`、`prepare_delivery_sizes`。
（`create_session` / `switch_current` / `generate_image` 由后端/智能体侧使用，前端不直调。）

---

## 1. 工作台外壳 `layouts/WorkbenchLayout.tsx`

**入口**：所有需登录页面的父级布局（`RequireAuth` → `WorkbenchLayout` → 各页）。

**可执行动作**
1. 鼠标悬停左侧导航条 → 导航从 `w-16`(64px) 展开到 `w-52`(208px)，文字淡入，展开/收起过渡 **200ms**。
2. 点击导航项「创作」→ 跳 `/create`；「编辑」→ `/editor`；「导出」→ `/marketing`；「批量」→ `/batch`。当前项高亮（`aria-current`）。
3. 点击底部「退出登录」按钮 → `POST /api/auth/logout`，成功后 `queryClient.clear()` + 跳转 `/`（replace）。
4. 退出按钮上的头像字母 = 用户名首字符大写；`title` 为 `用户名 · 退出登录`。

**关键状态与边界**
- 未登录访问 → `RequireAuth` 渲染「加载中…」→ 重定向 `/auth`。
- `/auth/me` 的 `retry:false`、`staleTime:Infinity`、`throwOnError:false`：**未登录 401 不报错**，视为 `user=null`。测试需先等 `/auth/me` 落地才能判断是否跳转（会有短暂「加载中…」）。
- `main` 容器 `overflow-auto`；编辑器页自身 `h-full overflow-hidden` 防外层滚动条。

---

## 2. 落地页 `/` `pages/LandingPage.tsx`

**入口**：直接访问 `/`；或任意未匹配路由的兜底。

**可执行动作**
1. 点击 Header 品牌 → `/`；点击「登录」→ `/auth`；已登录时显示「用户名 · 进入工作台」→ `/create`。
2. 在 Hero 需求框输入文本 → 右侧「免费开始 / 进入工作台」按钮文案随登录态切换。
3. **在需求框按 Enter（未按 Shift）** → 触发 `onStart(prompt)`；**Shift+Enter 换行**；输入法组合中（`isComposing`）不触发。
4. 点击「上传商品图」按钮 → **不打开文件选择器**，而是与提交同路径 `onStart(prompt)`（当前行为等同提交，注意断言）。
5. 点击 5 个场景胶囊按钮（商品主图 / 场景氛围图 / 模特上身 / 促销海报 / 多尺寸物料）→ 覆盖输入框文本并聚焦。
6. 点击底部 StartBanner 主按钮 → 跳 `/auth`（未登录）或 `/create`（已登录），**不携带 prompt**。
7. 点击「← 返回首页」（在 AuthPage，不在本页）。

**触发的 API**
- `onStart` → `savePromptDraft(prompt)`（写 `sessionStorage['retouch:prompt-draft']`，trim 后，空串则 removeItem）→ 跳 `/auth` 或 `/create`。
- `LandingHero` 初始值 = `readPromptDraft()`（**从 /create 返回落地页时会回填**）。
- 页面加载：`GET /api/auth/me`。

**关键状态与边界**
- `CapabilityShowcase` / `DeliverySteps` / `previews.tsx` 全部为**纯静态样式拼图**，`aria-hidden`，无可交互元素。
- `sessionStorage` 在隐私模式写入失败被静默吞掉（不报错）。

**是否依赖 AI**：❌ 纯静态 + 草稿传递，无任何模型调用。

---

## 3. 登录/注册页 `/auth` `pages/AuthPage.tsx`

**入口**：落地页「登录 / 免费开始」、退出后跳转、任何未登录访问受保护页的重定向。

**可执行动作**
1. 填写用户名 + 密码 → 点击「登录」/「注册并进入」→ `preventDefault` 提交 → 成功后 `navigate('/create', {replace:true})`。
2. 在表单内按 Enter → 同样提交。
3. 点击底部「还没有账号？注册」/「已有账号？登录」→ `action.reset()` + 改写 URL `?mode=register|login`。
4. 点击「← 返回首页」→ `/`。

**表单校验规则（前端）**
| 模式 | 用户名 | 密码 |
|---|---|---|
| 注册 `?mode=register` | `required` + `minLength=3` `maxLength=32` `pattern=[\p{L}\p{N}_]{3,32}` `title=3–32 位字母、数字或下划线` | `required` + `minLength=6` `maxLength=64` `title=6–64 位` |
| 登录（默认） | `required`（**不限长度**，为兼容老账号） | `required`（不限长度） |
- 用户名 placeholder：`3–32 位字母、数字或下划线`；密码 placeholder：`至少 6 位`。
- `autoComplete`：用户名 `username`；密码登录 `current-password` / 注册 `new-password`。
- 后端一致规则：`Credentials.username` 3–32 且 `replace('_','').isalnum()`（只允许字母数字下划线），密码 6–64；用户名会 `strip()`。

**关键状态与边界**
- 已登录且 `isLoading=false` → `<Navigate to="/create" replace />`，不渲染表单。
- 提交中：按钮 disabled + 文案「处理中…」。
- 失败：`action.isError` → 表单下方红色 `errorMessage(action.error)`（如「用户名或密码不正确」/「用户名已被占用」）。切换模式时错误被 `reset()`。
- **无「忘记密码 / 记住我 / 显示密码」入口**。

**是否依赖 AI**：❌ 纯认证。

---

## 4. 创作页 `/create` `pages/CreatePage.tsx`

**入口**：工作台导航「创作」；登录成功跳转；落地页开始；编辑器「去创作」。

### 4.1 生成表单 `components/GenerateForm.tsx`
**可执行动作**
1. 在画面描述 textarea 输入 → **Enter（无 Shift、非输入法组合）→ 触发 form submit**；Shift+Enter 换行。
2. 比例分段控件：5 选 1 —— `1:1 / 4:5 / 3:4 / 9:16 / 16:9`（**默认 `1:1`**），选中项 `aria-pressed=true` 且黑底白字。
3. 数量分段控件：4 选 1 —— `1 / 2 / 4 / 6`（**默认 `4`**）。
4. 点击「排除项」按钮 → 展开/收起高级区（文案切换为「收起排除项」）；输入 `negative_prompt`（可选）。
5. 点击「生成」→ `POST /api/generations {prompt:trim(), ratio, count, negative_prompt: trim()||undefined}`。
6. 提交成功后：`savePromptDraft('')` 清除草稿 → `navigate('/candidates/{run.id}')`。

**校验与禁用**
- `canSubmit = prompt.trim().length > 0 && !pending`；否则「生成」disabled（`opacity-40`，`cursor-not-allowed`）。
- 提交中按钮文案「提交中…」，底部提示改为「任务已提交，稍后会跳到候选页」。
- 失败：`generate.isError` → 表单下方红色错误文案（不跳转）。

### 4.2 上传已有图片 `components/ImageDropzone.tsx`
**可执行动作**
1. 点击拖拽区 → 打开系统文件选择（`accept="image/jpeg,image/png,image/webp"`，`multiple` 未开）。
2. 拖拽文件到虚线框 → 高亮（`border-brand bg-brand-soft`）；`dragover` 阻止默认、`dragleave` 取消高亮、`drop` 取 `files[0]`。
3. 单选模式只取第一个文件；`multiple` 模式逐个 `accept()`。
4. 选择后立即重置 `input.value=''`（可重复选同一文件）。

**校验与禁用**
- `checkFile(file)`：`file.type ∉ ['image/jpeg','image/png','image/webp']` → 「仅支持 JPG、PNG 与 WebP」；`file.size > 20*1024*1024` → 「文件超过 20 MB 上限」。**前端拦截，不发请求**，错误红字显示在拖拽框下方。
- `disabled` 时文案变为「上传中…」，`opacity-50`，点击不弹文件选择器。
- `onFile` → `POST /api/assets` → 成功后**自动创建会话**：`POST /api/sessions {current_asset_id}` → 跳 `/editor/{session.id}`。
- 上传中或建会话中整个拖拽区 disabled。
- 后端同样校验：>20MB → **413**；格式不支持/文件损坏 → **422**。

### 4.3 历史素材 `components/AssetLibrary.tsx` + `AssetCard.tsx`
**可执行动作**
1. 加载中 → 文案「加载中…」。
2. 空态 → 文案「还没有素材，先描述画面或上传一张图片。」
3. 点击组封面行 → 若该组有 `session_id` → 跳 `/editor/{sessionId}`；否则（散图）用封面 `POST /api/sessions` 新建 → 跳 `/editor/{id}`。
4. 组内资产 > 1 张时右侧出现「展开 / 收起」按钮（`aria-expanded`）；展开后是 2/3/4 列网格。
5. 点击组内任意 `AssetCard` → 已归组则打开该组会话；未归组则以该素材新建会话。
6. 卡片展示：`宽 × 高`、`image_format · 文件体积`（B/KB/MB）、创建时间；`has_alpha` 为真时左上角「透明底」角标；hover 缩放 1.02。

**关键状态与边界**
- 数据源 `GET /api/assets/library?limit=50`（**默认只取 50 组，页面上没有「加载更多」**）。
- 素材分组由后端给出，遮罩类中间产物不返回。

**是否依赖 AI**
- 表单生成、换背景等：**依赖图像模型**（见 §11）。
- 上传、建会话、素材浏览：❌ 不依赖。

---

## 5. 候选页 `/candidates/:runId` `pages/CandidatesPage.tsx`

**入口**：创作页提交生成成功后自动跳转；手输 URL 直达。

**状态分支（互斥，按顺序判定）**
| 条件 | 渲染 | 文案 |
|---|---|---|
| `notFound`（`GET /api/runs/{id}` 出错） | Centered | 标题「任务不存在」，提示「链接可能已失效，回到创作页重新开始。」 |
| `status ∈ {failed, canceled}` | Centered | 标题「生成失败」，提示 = `error` 或「未知原因」；按钮「返回重试」→ `/create` |
| `status !== 'succeeded'`（含 queued/running） | Progress | 标题「正在生成」，副标题 = `stage` 或「任务已提交，正在排队」；进度条 + 百分比数字 |
| `succeeded` | 候选网格 | 见下 |

**可执行动作**
1. 点击任一候选卡（`aria-pressed` 切换）→ 选中，右上出现「已选」角标，左上角显示序号 1..N，`alt="候选图 N"`。
2. 点击「进入编辑」→ `POST /api/sessions {current_asset_id: picked, asset_ids: 所有候选 id, title: prompt}` → 跳 `/editor/{session.id}`。
3. 「进入编辑」在未选中时禁用，**按钮文案本身变成「先点选一张」**；提交中文案「打开中…」。
4. hover 候选图：边框变品牌色、上浮 0.5、阴影、图 `scale 1.01`。

**关键状态与边界**
- 网格列数：`<640px` 1 列，`≥640px` 2 列。图片 `max-h-[52vh]`，`loading="lazy"`。
- 进度来自 `useRun`：SSE `GET /events/runs/{id}` + 快照 `GET /api/runs/{id}` 合并；显示值经 `useSmoothedProgress` 平滑（只增不减、上限 99、成功收束到 100）。
- SSE 在快照已是终态时**不建立**；收到终态帧后立即 `close()` 并 invalidate 快照。
- 会话创建时 `asset_ids` 传全部候选；后端上限 **12 张（`MAX_WALL_ASSETS`）** —— 数量为 6 时安全，超过会 422（前端无此限制，但候选数由 count 控制 ≤6）。

**是否依赖 AI**：✅ 文生图必须接图像模型；mock adapter 下返回占位图（彩色底 + 圆 + 提示词文字）。

---

## 6. 编辑器 `/editor/:sessionId` `pages/EditorPage.tsx`

**入口**：候选页「进入编辑」；上传图片自动建会话后跳转；侧栏历史会话；创作页/导出页素材。

**整体布局**：`SessionSidebar`(左 288px) + `Workspace`（工具条 56px + 细进度条 + 画布 + 可选右面板 288px + 底部图片墙）。

### 6.0 空态 / 错误态
| 条件 | 文案 | 操作 |
|---|---|---|
| 无 `sessionId`（`/editor`） | 标题「选择一个会话」/ 提示「从左侧打开历史对话，或回到创作页开始新的一张。」 | 按钮「去创作」→ `/create` |
| `session` 未加载且 `isError` | 标题「会话不存在」/「链接可能已失效，回到创作页新建一个。」 | 「去创作」 |
| `session` 未加载且未报错 | 标题「加载中」/「正在读取会话状态」 | — |

### 6.1 左栏会话侧栏 `components/editor/SessionSidebar.tsx`
**可执行动作**
1. 点击「新对话」→ `/create`。
2. 点击「历史」→ 展开/收起会话列表（`active` 高亮）。
3. 列表加载中 → 「加载中…」；无会话 → 「还没有会话」。
4. 点击任一会话 → `NavLink` 跳 `/editor/{id}`；当前会话 `bg-brand-soft` 高亮；每项显示标题 + `updated_at`（MM/DD HH:mm）。
5. 有 `activeId` 时，下方是 `AgentConversation` + `MessageComposer`。

**关键状态与边界**
- 列表最大高度 `max-h-52`，可滚动。
- API：`GET /api/sessions`。

### 6.2 智能体对话 `components/editor/AgentConversation.tsx` + `MessageComposer.tsx`
**可执行动作**
1. 输入指令 → **Enter 发送**（Shift+Enter 换行，中文输入法组合中不发送）；或点「发送」按钮。
2. 发送 → `POST /api/sessions/{id}/messages {text}`（**trim 后**），发送后输入框清空。
3. 计划状态为 `queued` → 显示「执行计划」「取消」两个按钮：
   - 「执行计划」→ `POST .../messages/{turnId}/confirm`
   - 「取消」→ `POST .../messages/{turnId}/cancel`
4. `running` → 显示「取消后续」→ 同 cancel 接口。
5. `failed` → 显示「重试失败步骤」→ `POST .../messages/{turnId}/retry`。
6. 三个按钮在 `confirm/cancel/retry` 任一 pending 时禁用。

**对话气泡结构（每个 turn）**
- 用户目标气泡（右对齐、`bg-brand-soft`）= `turn.goal`
- 回复文案（左对齐）；若 `turn.error` 非空则显示红色 `turn.error` 取代 `reply`
- 每步卡片：`N. {step.label}` + 右侧状态/百分比
  - 状态映射：`pending→等待中`、`waiting→待确认`、`queued→排队中`、`running→进行中`、`succeeded→已完成`、`failed→未完成`、`canceled→已取消`
  - `queued/running` 时额外渲染进度条 + `stage` 文案
  - `error` 非空时卡片内追加红色小字
- 计划中的每一步用 `useRun(step.run_id)` 单独订阅 SSE；该步进入终态后 invalidate `session` / `session/history` / `session/messages` 三个 query。

**关键状态与边界**
- 加载中 → 「加载中…」；无 turn → 引导文案「用一句话说明要怎么改，例如「水平翻转」或「去背景再调亮一点」。多步计划会先列出再执行。」
- **计划未结束时锁输入框**：`planActive = 存在 turn.status ∈ {queued, running}` → 输入框 disabled、placeholder 改为「当前计划进行中，确认、取消或等它结束后再发」、发送按钮 disabled、文案「思考中…」。
- 轮询：最后一个 turn 仍为 `running` 时每 **800ms** 重新拉取 `GET /messages`；由 running 转终态时额外 invalidate session 与 history。
- 发送错误 → `MessageComposer` 下方红字。
- `aria-label="修图指令"`，textarea `rows=2`。

**是否依赖 AI**：✅✅ **强依赖 LLM 规划器**（`ChatOpenAI` + 工具绑定）。mock adapter 只作用于**图像**模型，文字规划模型仍需真实可用的 OpenAI 兼容端点；未发布/不可用时后端抛 `PlannerUnavailable`。

### 6.3 工具条 `components/editor/EditorToolbar.tsx`
工具条有三套互斥形态（按优先级：选择模式 > 裁剪模式 > 默认）。

#### A. 默认形态（11 个操作按钮 + 右侧工具区）
| 按钮 | 动作 | 请求 |
|---|---|---|
| 裁剪 | 打开裁剪模式（互斥：关对比、关选择模式、清 replace 面板） | 无（本地） |
| 水平翻转 | `tools.invoke('flip_layer', {direction:'horizontal', layer_id:选中图层})` | `POST /tools` |
| 垂直翻转 | 同上，`direction:'vertical'` | `POST /tools` |
| 去背景 | `tools.invoke('remove_background', {layer_id})` | `POST /tools` |
| 换背景 | 切换右侧「换背景」表单（再次点击收起） | 无 |
| 扩图 | 切换右侧「扩图」表单 | 无 |
| 超分 | `tools.invoke('upscale_image', {scale: 2})` | `POST /tools` |
| 调色 | 切换右侧「调色」表单 | 无 |
| 拆层 | `tools.invoke('split_layers', {include_text: 图层面板勾选状态})` | `POST /tools` |
| 点选 | 切换选择模式为 `point` | 无 |
| 笔刷 | 切换选择模式为 `brush` | 无 |

#### B. 裁剪模式形态（5 个比例 + 确定 + 取消）
- 比例按钮：`自由 / 1:1 / 4:5 / 9:16 / 16:9`（**注意：没有 3:4**，与扩图表单的 5 个比例不同）
- 切换比例 → 裁剪框按新比例重算并居中（`fitCrop`）
- 「确定」→ `tools.invoke('crop_canvas', {rect:{x,y,width,height}})`，其中四个值均为**除以画布宽高的归一化比例**；随后立即关闭裁剪 UI
- 「取消」→ 关闭裁剪 UI

#### C. 选择模式形态（点选/笔刷/消除/替换/成层/清除/完成）
| 按钮 | 禁用条件 | 动作 |
|---|---|---|
| 点选 | — | 在 `point`/`null` 间切换 |
| 笔刷 | — | 在 `brush`/`null` 间切换 |
| 消除 | `tools.busy \|\| picking.busy \|\| !selection` | `invoke('erase_region', {mask_asset_id, revision, layer_id})` |
| 替换 | `!selection` | 打开/关闭右侧「局部替换」面板（`active` 高亮） |
| 成层 | `tools.busy \|\| picking.busy \|\| !selection` | `invoke('promote_object_to_layer', {mask_asset_id, revision})` |
| 清除 | `!selection \|\| picking.busy` | `DELETE /api/sessions/{id}/selection` |
| 完成 | — | 退出选择模式（Esc 等价） |

#### D. 右侧常驻工具区（8 项）
| 控件 | 行为 |
|---|---|
| 会话标题输入框 | `aria-label="会话标题"`；**Enter → blur 提交**；**Escape → 丢弃草稿**；失焦提交。空字符串或与原值相同则不提交。提交 → `PATCH /api/sessions/{id} {title}` |
| 画幅文字 | `宽 × 高`（`sm` 以上才显示） |
| 撤销 | `disabled = tools.busy \|\| picking.busy \|\| !(picking.canUndo \|\| session.can_undo)`；点击优先撤销**选区**，否则撤销会话。`title` 动态显示「撤销选区 ⌘Z」/「撤销上一步 ⌘Z」/「没有可撤销的操作」 |
| 重做 | 同上，优先 `picking.redo()`，否则 `tools.redo()` |
| 对比 | `disabled = !session.previous_document`；切换 `compareOpen`（`active` 高亮）。`title` 为「还没有上一版」当无上一版 |
| － | `stepZoom(1/1.25)` |
| 百分比按钮（`w-12`） | `zoomTo(1)`（100%），文案 `Math.round(scale*100)%` |
| ＋ | `stepZoom(1.25)` |
| 适应 | `fit(session.document)` |
| 导出（Link） | 跳 `/marketing/{sessionId}` |
| 图层 | 切换右侧图层面板（`active` 高亮） |

**关键状态与边界**
- 工具条 `h-14`，`overflow-x-auto`（窄屏横向滚动）。
- `tools.busy` = `invoke.isPending || undo.isPending || redo.isPending || 等待上一次 run 结束`。
- **进度显示是「点哪个哪个变」**：`Button` 接 `progress` 时显示 `xx%` + 底部 2px 进度条 + `aria-busy`，其余按钮只是 disabled，不会显示百分比。
- `tools.pending` 时工具条下方出现 `h-0.5` 品牌色细进度条。
- 撤销/重做有**链式锁**（`historyLock`）：上一次未 settle 时再次点击被忽略。
- 工具完成后 toast：`「裁剪完成」「拆层完成」…`（`ACTION_LABELS`），部分带「撤销」按钮。

#### E. 画布提示 `CanvasHint`（`canvasHint()` 分组）
| 优先级 | 模式 | 文案 |
|---|---|---|
| 1 | `busy` | 有 pending：`{stage \|\| '处理中'} · {progress}%`；否则「处理中」 |
| 2 | `cropOpen` | 「拖动裁剪框，点确定应用 · Esc 取消」 |
| 3 | `compareOpen` | 「拖动画布上的圆点对比上一版 · Esc 退出」 |
| 4 | `selectMode==='point'` | picking 中：「正在识别选区…」；否则「点击物体建立选区，可连续点选 · Esc 退出」 |
| 5 | `selectMode==='brush'` | 「按住圈出要改的区域，松手即选中圈内 · Esc 退出」 |
| 6 | idle | 不渲染 |

### 6.4 画布 `components/editor/CanvasStage.tsx`（Konva）
**视图**
- `draggable = !cropOpen && !selecting && !holdingStage`（拖拽图层或缩放中时舞台不可平移）
- 指针样式：选择/裁剪模式 `cursor-crosshair`，否则 `cursor-grab`，按下 `cursor-grabbing`

**画布手势（可执行动作 → 行为）**
| 手势 | 条件 | 行为 |
|---|---|---|
| 滚轮 / 触控板双指捏合 | `ctrlKey \|\| metaKey` | 以指针为锚点缩放：`exp(-clamp(deltaY, ±50) * 0.0035)`；缩放夹在 **[0.05, 8]** |
| 普通滚轮 | 无修饰键 | 平移 `panBy(-deltaX, -deltaY)` |
| 拖拽空白画布 | `!cropOpen && !selecting && !holdingStage` | 平移视图 |
| **双击画布空白** | `!selecting` 且 target 是 Stage | 适应窗口 `fit(canvas)`（**带 260ms 缓动**） |
| 点击画布 | `selectMode==='point'` | 记录标点 + 本地泛洪预览 + `onPoint(x,y)`；坐标归一化到 [0,1]，点在画布外（<0 或 >1）忽略 |
| 按下/移动/抬起 | `selectMode==='brush'` | 采集笔迹；**点数 < 2 时不发请求**（直接 settle） |

**图层交互**
| 手势 | 行为 |
|---|---|
| 单击图层 | 选中（`dragDistance=2` 产生的「拖完松手也触发 click」通过 `dragged` ref 抑制）；选中描边 `#5f98ad`，`strokeWidth=2` |
| 拖拽图层 | 鼠标悬停变 `cursor:move`；`onDragEnd` 计算新左上角，位移 < 0.5px 不提交；提交 → `POST /tools move_layer {layer_id,x,y}`；拖拽期间画面「钉住」，文档追上后解除 |
| 拖四角手柄缩放 | 仅 4 个角（`top-left/top-right/bottom-left/bottom-right`），`rotateEnabled=false`、`flipEnabled=false`、`keepRatio`；手柄尺寸按视图倍率反向补偿；夹在 **[0.1, 8]**；提交 → `POST /tools scale_layer {layer_id, scale_x, scale_y, x, y}` |
| **双击文字图层** | 打开画布内联 `textarea` 编辑；原图层在编辑期间 `opacity=0` |
| 锁定图层 | `draggable=false`，仍可点选 |
| 隐藏图层 | 不渲染（`layers.filter(l => l.visible)`） |

**内联文字编辑（`TextEditor`）**
- 打开即 `focus()` + 全选 `select()`
- **Enter（无 Shift）→ 提交**；**Escape → 取消**；**失焦 → 提交**
- 提交时若文本与 `layer.text` 相同则不发请求；不同则 `POST /tools set_layer_text {layer_id, text}`
- textarea 位置/宽高/字号按图层变换 × 视图倍率换算，宽度 `max(48, layer.width*scale)`，高度 `max(28, layer.height*scale)`，字号 `max(12, fontSize*scale)`；跟随旋转角
- 编辑期间进入非交互模式会自动关闭（`!interactive → setEditingId(null)`）

**裁剪层（`CropLayer`）**
- 框外 4 块半透明遮罩 `rgba(20,26,20,0.45)` 形成暗角
- 框可拖动、可缩放；`keepRatio = cropRatio !== 'free'`
- `clampRect` 保证框在画布内；**最小边长 32px**（`boundBoxFunc` 与 `onTransform` 双重限制）
- 「自由」比例初始框 = 画布内缩 **8%**
- 虚线描边按倍率反向补偿

**对比层（`CompareDivider`）**
- `split = canvas.width * compareAt`，默认 `compareAt = 0.5`
- 左侧渲染 `previous_document`（裁剪 0..split），右侧渲染当前 document
- 拖动白色圆形手柄 → `compareAt = pointer.x / canvas.width`，夹在 [0,1]
- 手柄 `scaleX/Y = 1/viewScale` 保持屏幕尺寸恒定；hover `cursor: ew-resize`

**选区浮层（`SelectionOverlay`）**
- 遮罩图 `opacity=0.45`；本地泛洪预览 `opacity=0.45`；笔迹预览描边宽度 `brushWidth(document) = max(2, min(w,h)*0.03)`
- 笔迹点数 ≤2 时不填充，>2 时闭合并填充 `#5f98ad`
- 标点徽章：外圈 `r=11` 实心 + 数字；遮罩未就绪时外套 `r=17` 半透明圈表示 pending
- 服务端遮罩上屏后自动 `settle()` 清掉本地预览

**切图过渡**
- `useHeldCanvas`：按 `画幅 + 图层id:asset_id` 组成 stamp 判断是否换图
- 换图时先预加载新图 URL，**最多等 4000ms**；期间继续画旧图
- 旧图以「鬼影」叠层淡出，`SWITCH_FADE_MS = 180ms`
- 画幅变化时**立即 `fit(..., {animate:false})`**，不走缓动

**画布实时滤镜**
- 调色预览仅在图片 `crossOrigin='anonymous'` 解码成功（`image.safe === true`）时启用 Konva filters
- `node.cache({pixelRatio: 0.6})`；9 项逐像素参数前端实时算：`brightness / contrast / saturation / highlights / shadows / temperature / tint / vibrance / vignette`
- **`sharpness` 与 `clarity` 不做前端预览**（卷积运算），需「应用」后由后端处理
- 全部为 0 → `toAdjustPreview` 返回 null，跳过缓存与滤镜

### 6.5 右面板 `components/editor/LayerPanel.tsx`
面板由 `useMountTransition` 驱动，关闭后保留 200ms 退场动画（与 `index.css` slide-out 时长一致）。宽度 288px，`<960px` 时变为右侧绝对定位浮层。

**面板内容（自上而下）**

**① 调色（`panel==='adjust'`）**
- 11 个滑杆：亮度 / 对比度 / 高光 / 阴影 / 色温 / 色调 / 饱和度 / 自然饱和度 / 锐化 / 清晰度 / 晕影
- 取值范围：前 10 项 **[-1, 1] step 0.05**；**晕影 [0, 1] step 0.05**
- 数值显示 `toFixed(2)`；**双击滑杆标签复位到原值（0）**
- 拖动中 → `setAdjustPreview` 实时上画布；`onPointerUp`/`onLostPointerCapture` 时提交
- 「重置」/「应用」按钮在未触碰过任何滑杆（`touched`）时禁用
- 「应用」→ `POST /tools adjust_image {..., layer_id: 选中图层}`，随后清空预览值；`title` 为「先拖动滑杆再应用」
- 说明文案明示「锐化与清晰度需应用后可见」

**② 换背景（`panel==='background'`，`GenerateEdits/BackgroundForm`）**
- textarea 输入背景描述（placeholder「例如：浅木色桌面，晨光从左侧照入」）
- 张数切换：**1 / 2 / 4**（默认 1），单选
- 「生成」在 `prompt.trim()` 为空时禁用；提交后清空输入框
- 提交 → `POST /tools replace_background {prompt, count}`
- 两种说明文案二选一（`wallOnly`）：已拆层时提示「结果拍平成整图只进图片墙，点选采用；画布与图层保持不变」；未拆层时「一张直接上画布；多张进图片墙，点选采用」

**③ 扩图（`panel==='expand'`，`ExpandForm`）**
- 比例 5 选 1：`1:1 / 4:5 / 3:4 / 9:16 / 16:9`（**默认 `16:9`**）
- 「扩展」按钮 → `POST /tools expand_canvas {ratio}`
- 文案同样有 `wallOnly` 分支

**④ 局部替换（`panel==='replace'`，`ReplaceForm`）**
- textarea（placeholder「例如：把杯子换成陶瓷马克杯」）；空文本时「替换」禁用
- 提交 → `POST /tools replace_region {prompt, mask_asset_id: 当前选区, revision, layer_id}`
- 整个表单在 `!selection` 时禁用（工具条上「替换」按钮已阻止无选区进入）

**⑤ 图层区（常驻）**
- 复选框「同时拆出文字」→ 控制 `split_layers` 的 `include_text`
- 「拆层」按钮（`disabled = tools.busy`）→ `invoke('split_layers', {include_text})`；`title` 随勾选变化
- 「成层」按钮（`disabled = tools.busy || !selection`）→ `invoke('promote_object_to_layer', {mask_asset_id, revision})`；无选区时 `title` 为「先点选或涂抹」
- 图层列表（**倒序渲染，即顶层在上**）：缩略图（无素材时显示「文」）、名称、副标题（文字层显示文本或「文字」；图像层显示「已锁定」/「图像」）、右侧 `round(opacity*100)%`
- 点击图层行 → 选中（同步画布描边 + 缩放手柄）
- 点击眼睛图标 → `invoke('set_layer_visible', {layer_id, visible: !visible})`；隐藏行整体 `opacity-50`
- 面板顶部未选图层时默认选中 `document.layers.at(-1)`

**⑥ 文字区（仅选中文字层时显示）**
- textarea（`rows=3`）→ 实时 `setLayerPreview({id, text})`；**失焦提交**、**⌘/Ctrl+Enter 提交**
- 字号滑杆 **[8, 120] step 1**，整数显示
- 颜色 `<input type="color">` → 变更即提交（不是失焦提交）
- 三项都未变则不发请求
- 提交 → `POST /tools set_layer_text {layer_id, text, font_size, fill}`

**⑦ 变换区（有选中图层时显示）**
- 透明度 **[0, 1] step 0.01**，显示 `xx%`，原值 1
- 图层缩放 **[0.1, 3] step 0.05**，显示 `xx%`，原值 1
- 旋转 **[-180, 180] step 1**，显示 `x°`，原值 0
- 四个排序按钮：置顶 / 上移 / 下移 / 置底 → `invoke('reorder_layer', {layer_id, place})`
- 全部滑杆拖动实时预览，松手提交；**双击复位到 origin**

**⑧ 属性区（常驻）**
- 画布 `宽 × 高`、修订号 `revision`、格式 `image_format`、大小（`formatBytes`）、透明通道（有/无）

**⑨ 编辑记录区（常驻）**
- `GET /api/sessions/{id}/history`；空态「暂无记录」
- 每条：`ACTION_LABELS[action]`（未知名回落到原名）+ `MM/DD HH:mm`

### 6.6 底部图片墙 `components/editor/ImageWall.tsx`
**可执行动作**
1. 点击任一缩略图 → `PATCH /api/sessions/{id} {current_asset_id}` → 切换当前画布图（带 180ms 鬼影过渡）。
2. 当前图的缩略图**禁用**（`disabled={disabled || active}`），`title` 为「当前画布 · 原图」。
3. 其他缩略图 `title` 为「采用这张 · 生成 1024×1024」等。

**过滤规则（重要）**
- 过滤掉 `kind === 'mask'`
- 过滤掉 `kind ∈ {subject, background}` **且不是当前图**的资产（即拆层产物只在它是当前图时才出现）
- 横向滚动条，缩略图 `size-16`(64px)，底部黑色标签显示 kind 中文名

**禁用条件**：`disabled = patch.isPending || tools.busy`（整个图片墙在改会话标题或跑工具时不可点）。

### 6.7 选择（点选 / 笔刷）`hooks/useSelection.ts` + `hooks/useSelectStroke.ts` + `hooks/usePointPreview.ts`
**点选模式流程**
1. 切到点选模式 → **立即** `POST /api/sessions/{id}/selection/prepare`（预热 SAM embedding，失败静默忽略）
2. 点击画布 → 立刻出现**本地泛洪预览**（`lib/floodPreview.ts`，纯浏览器计算，容差 36、最大边 480px、填充超 55% 时退化为圆形），同时发 `POST /api/sessions/{id}/selection {revision, points:[{x,y}], append}`
   - `append = Boolean(selection && selection.revision === revision)` → **已有同 revision 选区时连续点选会并入，选区标记编号递增**
3. 服务端遮罩返回后覆盖预览，`SelectionOverlay` 的 `onMaskReady` 触发 `settle()` 清本地草稿

**笔刷模式流程**
1. 按下 → 采集起点；移动 → 追加；抬起 → 点数 ≥2 才发 `POST .../selection {revision, strokes:[points], radius: 0.03}`
2. 松手后笔迹预览保留到遮罩上屏

**选区失效规则**
- `revision` 变化（任何画布变更）→ `dropStaleSelection(revision)` 自动清空本地选区
- 工具调用失败（画布已变导致 mask 不匹配）→ 后端报「选区已过期，请重新选择」→ toast danger

**选区撤销/重做**
- 纯前端历史（`lib/selectionHistory.ts`），**不进会话历史**
- `undo`/`redo` → `replay(entries)`：先 `DELETE .../selection`，再按顺序 `POST .../selection {points, append:false}`，若有笔迹再 `POST .../selection {strokes, radius:0.03}`
- 会话 `revision` 变化 → 历史 reset

**清除**：`DELETE /api/sessions/{id}/selection` → 清空本地选区与历史。

**是否依赖 AI**：选区本身用 **rembg/SAM**（`matting_provider=auto` 有则用，否则退化为四角圆形遮罩 `matting_provider=corner`）。`erase_region` / `replace_region` / `promote_object_to_layer` 需要**图像模型**。

---

## 7. 导出物料页 `/marketing[/:sessionId]` `pages/MarketingPage.tsx`

### 7.1 Picker（`/marketing`）
- 加载中 → 「加载中…」
- 空态 → 「还没有可导出的会话，先到 **创作** 打开一张图。」（「创作」是内嵌链接）
- 否则复用 `AssetLibrary`：点击组封面/卡片 → 有 `session_id` 则跳 `/marketing/{id}`，否则 `POST /api/sessions {current_asset_id}` 后跳
- API：`GET /api/assets/library?limit=50`

### 7.2 Workspace（`/marketing/:sessionId`）
**头部卡片**
- 80×80 当前图缩略图 + 会话标题（`shortTitle(title, 28)` 截断，`title` 属性为完整标题）+ `画布 宽 × 高`
- `SessionSwitch`：`<select aria-label="切换会话">`，仅当 `GET /api/sessions` 返回 **≥2 条**时渲染；切换即 `navigate('/marketing/{id}')`；选项显示 `shortTitle(item.title)`（默认截断 18 字）
- 右上「回编辑器」→ `/editor/{sessionId}`

**四类营销图**
- 文案输入框（placeholder「可选：海报文案或补充要求，例如「新品首发 限时 8 折」」），`tools.busy` 时禁用
- 4 张卡片（2 列 / lg 4 列）：
  | kind | 名称 | 说明 |
  |---|---|---|
  | `product` | 商品主图 | 白底居中，适合详情页主图 |
  | `scene` | 场景氛围图 | 真实场景，侧逆光浅景深 |
  | `model` | 模特上身 | 模特手持或佩戴展示 |
  | `poster` | 促销海报 | 突出商品，预留文案区 |
- 点击卡片「生成」→ `POST /tools generate_marketing {kind, caption: trim() || undefined}`；该卡按钮文案变「生成中…」，其余卡禁用
- **说明**：区块副标题「以当前画布为参考生成，结果进图片墙，**不改画布**。」

**投放尺寸**
- 「生成 1:1 / 4:5 / 9:16」主按钮 → `invoke('prepare_delivery_sizes')`（**不传 ratios**，后端用默认三档）
- 3 个单比例按钮，每个显示标签 + 尺寸文案：
  - `1:1` · 1080×1080
  - `4:5` · 1080×1350
  - `9:16` · 1080×1920
- 单比例点击 → `invoke('prepare_delivery_sizes', {ratios: [value]})`
- 运行中：对应按钮显示「生成中…」（尺寸文案位置替换），下方显示 `{stage || '处理中'}` + 进度条
- **注意：不传 ratios 与传单比例是两个不同的 `deliveryRunning` 匹配条件**

**打包下载**
- 列表项 = `packable(asset, current_asset_id)`：`mask` 一律排除；`subject`/`background` 仅当前图保留
- 默认勾选（`defaultSelected`）：优先全选 `marketing` + `export` 类资产；否则仅当前图；若无当前图则空
- 点击卡片 → 切换勾选（`aria-pressed`，选中时边框 `border-brand` + 左上角圆形对勾 + 底部条显示「类型 · 比例标签」）
- 卡片底部：`宽 × 高` + 当前图追加「 · 当前」
- 「全选 / 取消全选」按钮（`items.length > 0` 才渲染）
- 「打包 N 张」按钮：`disabled` 当 `selected.length === 0`；文案随选中数变化；打包中「处理中…」
- 点击 → `POST /api/sessions/{id}/exports {asset_ids: selected}` → 前端 `URL.createObjectURL` + 隐藏 `<a download>` 触发下载 → toast「已打包 N 张」
- `error` 显示在区块上方红字
- 空态：「还没有素材。」

**关键状态与边界**
- 加载中 → 「加载中 / 正在读取画布与素材」；`isError` → 「会话不存在 / 回到列表另选一个会话。」+ 「返回导出物料」链接
- `ratioLabel` 把 `1080×1080 / 1080×1350 / 1080×1920` 映射为 `1:1 / 4:5 / 9:16`，其余显示 `宽×高`
- `shortTitle` 折叠连续空白，超长加 `…`

**是否依赖 AI**
- `generate_marketing` → ✅ 需要图像模型（`provider.edit`）
- `prepare_delivery_sizes` → ❌ 纯 PIL `letterbox`，不调模型
- 打包下载 → ❌ 纯后端压缩

---

## 8. 批量页 `/batch[/:runId]` `pages/BatchPage.tsx`

### 8.1 Compose（`/batch`）
**选图**
1. 拖拽区（`multiple`）：拖入或点击选择多文件 → 逐个 `POST /api/assets` → 自动加入选择列表
2. 提示文案：`JPG / PNG / WebP，最多 20 张`
3. 已选列表缩略图（`size-16`），每个右上角「×」按钮（`aria-label="移除"`）可移除
4. `groups.length > 0` 时下方展示「从历史素材添加」，取素材库**前 12 个**（`slice(0, 12)`）作为 `size-14` 缩略图按钮，点击加入

**处理步骤（`BATCH_STEPS`，2 列网格复选卡）**
| id | 名称 | 说明 | 展开的子控件 |
|---|---|---|---|
| `remove_background` | 去背景 | 去掉背景，保留主体 | — |
| `replace_background` | 换背景 | 按描述替换背景 | textarea（placeholder「例如：浅木色桌面，晨光」） |
| `adjust_image` | 调色 | 亮度、对比度、饱和度 | 3 个滑杆：**[-1, 1] step 0.05**，标签 亮度/对比/饱和 |
| `upscale_image` | 超分 | 提高分辨率 | 单选 2 倍 / 4 倍（默认 2） |
| `expand_canvas` | 扩图 | 扩展到指定比例 | 单选 `1:1 / 4:5 / 9:16 / 16:9`（默认 `16:9`） |
| `prepare_delivery_sizes` | 投放尺寸 | 完整放入 1:1 / 4:5 / 9:16 | 多选 `1:1 / 4:5 / 9:16` |

**导出格式**：两个复选框 `PNG` / `JPG`（默认只勾 `PNG`）。

**默认 draft（`EMPTY_DRAFT`）**：`selected: ['remove_background']`、`scale: 2`、`expandRatio: '16:9'`、`delivery: ['1:1','4:5','9:16']`、`formats: ['png']`、三滑杆全 0、`prompt: ''`

**提交**
- 「开始处理」按钮（`create.isPending` 时文案「提交中…」）
- → `POST /api/batches {asset_ids, operations: operationsOf(draft), formats}`
- `operationsOf` 按选中顺序映射：
  - `replace_background` → `{prompt: draft.prompt.trim()}`
  - `adjust_image` → `{brightness, contrast, saturation}`
  - `upscale_image` → `{scale}`
  - `expand_canvas` → `{ratio}`
  - `prepare_delivery_sizes` → `{ratios: draft.delivery}`
  - 其他 → `{}`
- 成功 → `navigate('/batch/{run.id}')`

**禁用原因文案（`draftReady`，按顺序判定，只显示第一条）**
1. `先选至少一张图`（0 张）
2. `先勾选至少一步处理`（0 步）
3. `换背景需要填写描述`（勾了换背景但 prompt 为空）
4. `投放尺寸至少选一个比例`（勾了投放尺寸但 delivery 为空）
5. `至少选择一种导出格式`（formats 为空）

**最近任务**
- `GET /api/batches`，非空时渲染列表；每项显示「N 张 · {stage || status}」+ 创建时间（`MM/DD HH:mm`）；点击 → `/batch/{runId}`
- **无分页**

**关键状态与边界**
- `assets.length >= 20` 时拖拽区 `disabled`（文案「上传中…」仍会显示，**是个已知文案缺陷，可作为测试观察点**）
- 同一素材重复加入被去重；后端 `BatchIn.asset_ids` 上限也是 20
- `create.isError` → 按钮右侧红字（同时 hook 内也会 toast danger）
- `history` 为空时整个区块不渲染

### 8.2 Watch（`/batch/:runId`）
**可执行动作**
1. 「新任务」→ `/batch`
2. 「打包下载」→ `GET /api/batches/{id}/export` → ZIP 下载 → toast「已打包 N 张」（N = `status === 'succeeded'` 的条目数）
   - `disabled` 当：未到终态 / 成功数为 0 / `pack.isPending`
3. 顶部标题区：「批量进度」+ `{stage || '处理中'}` +（未完成时）`{progress}%` 与进度条
4. 每条 item：源图缩略图 + 状态文案 + 尺寸（`宽 × 高`，有结果时追加 ` → N 张结果`）+ 最多 **4 张**结果缩略图（`slice(0,4)`）+ `item.error` 红字

**状态文案映射**：`succeeded→已完成`、`failed→失败`、`running→处理中`、其他（含 pending）→`等待中`

**关键状态与边界**
- `!data && isError` → 「任务不存在」+ 「返回批量」链接
- 轮询：运行中每 **1200ms** 拉取 `GET /api/batches/{id}`；SSE `GET /events/runs/{runId}` 同步头部进度；终态时 invalidate batch 详情与列表
- 失败展示：`live.error`（顶部）与 `pack.isError`（下方）
- **无取消/重试按钮**

**是否依赖 AI**
- 批量步骤中 `replace_background`、`upscale_image`、`expand_canvas` → ✅ 需要图像模型（mock 下可跑通，产出占位图）
- `remove_background`（rembg/四角）、`adjust_image`、`prepare_delivery_sizes` → ❌ 纯本地计算

---

## 9. 占位页 `pages/PlaceholderPage.tsx`
- 通用占位组件（标题 + 提示），**当前无任何路由引用**（`App.tsx` 未挂载），仅保留给后续开发。
- **不算入测试范围**（可选：作为死代码记录）。

---

## 10. 快捷键清单（全局汇总）

### 10.1 编辑器全局（`EditorPage.Workspace`，`window.addEventListener('keydown')`）
**前置条件**：焦点不在 `<input>` / `<textarea>` 时才生效（`event.target instanceof HTMLInputElement || HTMLTextAreaElement` → 直接 return）。

| 键 | 行为 |
|---|---|
| `Escape` | **分层退栈，一次只收一层**：cropOpen → 关闭裁剪；否则 compareOpen → 关闭对比；否则 selectMode → 退出选择；否则 panel → 关闭右侧面板 |
| `Cmd/Ctrl + Z` | 撤销：`picking.canUndo` → 撤销选区；否则 `session.can_undo` → `POST /undo`。`preventDefault()`。**`event.repeat`（长按）或 `tools.busy`/`picking.busy` 时忽略** |
| `Cmd/Ctrl + Shift + Z` | 重做：`picking.canRedo` → `picking.redo()`；否则 `session.can_redo` → `POST /redo` |
| `Cmd/Ctrl + Y` | 同上（重做） |
| `0` | `fit(session.document)` 适应窗口（**带 260ms 缓动**） |
| `1` | `zoomTo(1)` 实际像素 |
| `=` 或 `+` | `stepZoom(1.25)` 放大 |
| `-` | `stepZoom(1/1.25)` 缩小 |

**边界规则**：视图快捷键（`0/1/=/+/-`）在任何 `meta || shift || alt` 修饰下**直接 return**（避开浏览器缩放）；但 `Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y` 在任意组合下都优先处理。

### 10.2 组件内快捷键
| 位置 | 键 | 行为 |
|---|---|---|
| 画布内联文字编辑（双击文字层） | `Enter`（无 Shift） | 提交 `set_layer_text` |
| 同上 | `Escape` | 取消，不提交 |
| 同上 | 失焦 | 提交 |
| 工具条会话标题 | `Enter` | `blur()` → 提交重命名 |
| 工具条会话标题 | `Escape` | 丢弃草稿（不提交） |
| 左栏修图指令 `MessageComposer` | `Enter`（无 Shift、非 `isComposing`） | 发送 |
| 同上 | `Shift + Enter` | 换行 |
| 落地页需求框 `PromptComposer` | `Enter`（无 Shift、非 `isComposing`） | `onStart`（保存草稿 + 跳转） |
| 同上 | `Shift + Enter` | 换行 |
| 创作页生成表单 | `Enter`（无 Shift、非 `isComposing`） | `form.requestSubmit()` |
| 同上 | `Shift + Enter` | 换行 |
| 图层面板文字 textarea | `Cmd/Ctrl + Enter` | 提交 |
| 图层面板**所有滑杆标签** | 双击 | 复位到 origin（调色=0、透明度=1、缩放=1、旋转=0、字号=层默认） |
| 画布 | 双击空白 | 适应窗口 |
| 画布 | 双击文字图层 | 进入内联编辑 |

---

## 11. 表单校验规则汇总

### 11.1 前端
| 位置 | 规则 |
|---|---|
| 注册用户名 | `required`、3–32、`pattern=[\p{L}\p{N}_]{3,32}`、title「3–32 位字母、数字或下划线」 |
| 注册密码 | `required`、6–64、title「6–64 位」 |
| 登录用户名/密码 | 仅 `required` |
| 创作页 prompt | `trim().length > 0` 且 `!pending`；无前端长度上限 |
| 创作页 negative_prompt | 可选，trim 后为空则不传 |
| 上传文件 | type ∈ `image/jpeg, image/png, image/webp`；`size ≤ 20 * 1024 * 1024`（20 MB）；前端拦截不发请求 |
| 批量编排 | `draftReady` 五条（见 §8.1） |
| 批量图片数 | ≤ 20（前端 `MAX_IMAGES`，后端 `min 1 max 20`） |
| 换背景 prompt | `trim().length > 0` 才可生成 |
| 局部替换 prompt | `trim().length > 0` 才可替换 |
| 调色 | 至少拖动一个滑杆（`touched`）才可应用/重置 |
| 候选页 | 必须先选一张才能「进入编辑」 |
| 打包下载 | `selected.length > 0` |
| 智能体指令 | `trim().length > 0` 且 `!pending && !planActive` |
| 会话标题 | `trim()` 非空且与原值不同才提交 |
| 选区操作 | `消除`/`成层`/`替换`/`清除` 均要求先有 `selection` |
| 图层工具 | 全部 `tools.busy` 时禁用 |
| 图片墙 | `patch.isPending \|\| tools.busy` 时禁用；当前图自身禁用 |

### 11.2 后端（前端可能触发 422 的边界，用于断言错误文案）
| 接口 | 限制 |
|---|---|
| `POST /api/auth/register|login` | username 3–32，仅字母数字下划线；password 6–64 |
| `POST /api/generations` | `prompt` 1–**1500**；`negative_prompt` ≤1500；`count` **1–6**；`seed` 0–2147483647；`reference_asset_ids` ≤**3** |
| `POST /api/sessions/{id}/messages` | `text` 1–**1000**，纯空白 → 「指令不能为空」 |
| `POST /api/sessions` | `asset_ids` ≤**12**（`MAX_WALL_ASSETS`） |
| `POST /api/sessions/{id}/selection` | `points[].x/y ∈ [0,1]`；`radius ∈ [0.005, 0.12]`（前端固定 **0.03**）；`revision` 必填 |
| `POST /api/assets` | >20MB → **413**；格式不支持/损坏 → **422** |
| `GET /api/assets?limit` / `/library?limit` | `limit ∈ [1, 200]`，前端固定 50 |
| `POST /api/batches` | `asset_ids` **1–20**；`operations` **1–6**；`formats` **1–2**（`png`\|`jpg`） |
| tool `generate_image` | 同 generations |
| tool `replace_background` | `prompt` 1–**500**；`count` **1–4**；`negative_prompt` 可选 |
| tool `expand_canvas` | `ratio` 必填；`prompt` ≤500 默认「自然延伸画面边缘，保持主体完整」 |
| tool `upscale_image` | `scale` **2–4**（前端固定 2） |
| tool `adjust_image` | 10 项 `[-1,1]` + `vignette [0,1]` |
| tool `erase_region` | `prompt` ≤500 可选 |
| tool `replace_region` | `prompt` **1–500** 必填 |
| tool `promote_object_to_layer` | `name` ≤40 可选（前端不传） |
| tool `generate_marketing` | `kind ∈ {product,scene,model,poster}`；`caption` ≤**200**；`count` 1–4；`ratio` 默认 `1:1` |
| tool `prepare_delivery_sizes` | `ratios` **1–5**（去重）；`prompt` ≤500 |
| tool `set_layer_text` / `crop_canvas` / `flip_layer` / `set_layer_opacity` / `scale_layer` / `rotate_layer` / `move_layer` / `reorder_layer` / `set_layer_visible` / `split_layers` | 见 `backend/app/edits/document.py` |

### 11.3 选区相关错误
- `revision` 不匹配 → `ToolError("选区已过期，请重新选择")` → toast danger
- `mask_for_layer` 抛 `EmptyCut` → `ToolError("选区没有覆盖到该图层")`

---

## 12. 硬编码尺寸 / 比例 / 数量限制（前端常量）

### 12.1 视图（`stores/canvasView.ts`）
| 常量 | 值 | 含义 |
|---|---|---|
| `MIN_SCALE` | **0.05** | 最小缩放（5%） |
| `MAX_SCALE` | **8** | 最大缩放（800%） |
| `FIT_RATIO` | **0.92** | 适应窗口时四周留白 8% |
| `GLIDE_MS` | **260** | 按钮缩放/适应的缓动时长 |
| `ZOOM_STEP` | **1.25** | `+`/`-` 每档倍率 |
| `WHEEL_CAP` | **50** | 单次滚轮 delta 上限（触控板 vs 滚轮差异补偿） |
| `WHEEL_GAIN` | **0.0035** | 滚轮→倍率指数系数 |

### 12.2 画布（`components/editor/CanvasStage.tsx`）
| 常量 | 值 |
|---|---|
| `PREVIEW_PIXEL_RATIO` | 0.6（滤镜缓存像素比） |
| `SWITCH_FADE_MS` | 180（切图鬼影淡出） |
| `MIN_LAYER_SCALE` | **0.1**（图层缩放下限） |
| `MAX_LAYER_SCALE` | **8**（图层缩放上限） |
| `SELECTED_STROKE` | `#5f98ad` |
| Transformer 锚点 | 仅 4 角，`anchorSize=10/scale`、`anchorCornerRadius=3/scale`、`anchorStrokeWidth=1.5/scale` |
| 裁剪最小边 | **32px** |
| 裁剪「自由」初始内缩 | **8%** |
| 裁剪遮罩色 | `rgba(20,26,20,0.45)` |
| 对比手柄 | 半径 15（画布坐标），`scale=1/viewScale` |
| 选区/预览不透明度 | 0.45 |
| 选区标记 | 实心 r=11，pending 环 r=17，描边 2 |
| 位移提交阈值 | **0.5px**（小于则不发 `move_layer`） |
| 缩放提交阈值 | `0.001` |
| 拖拽触发距离 | `dragDistance = 2` |
| 画板阴影 | `shadowBlur=32, opacity=0.16` |

### 12.3 选区 / 笔刷
| 常量 | 值 |
|---|---|
| `BRUSH_RADIUS` | **0.03**（画布短边 3%，最小 2px） |
| 后端 `SelectIn.radius` | `[0.005, 0.12]`，默认 0.03 |
| `floodPreview.TOLERANCE` | 36（RGBA 距离，含 alpha 0.25 权重） |
| `floodPreview.MAX_SIDE` | 480（本地预览降采样最大边） |
| `floodPreview.MAX_FILL` | 0.55（填充超 55% 退化为圆形） |
| `floodPreview` 预览色 | `rgba(95,152,173,1)` |
| 退化圆半径 | `max(16, min(w,h)*0.16)` |
| 笔迹最少点数 | **2**（<2 不发请求） |
| `useCanvasImage` 缓存 | **16** 张 LRU |
| `useHeldCanvas` 预加载超时 | **4000ms** |
| `useElementSize` | 量到 0 宽高时沿用上次值 |

### 12.4 进度与节奏
| 常量 | 值 |
|---|---|
| `useAgent` 轮询间隔 | **800ms**（最后一个 turn 为 running） |
| `useBatch` 轮询间隔 | **1200ms**（运行中） |
| `PROGRESS_CEILING` | **99**（运行中上限） |
| `pacingSeconds` 缺省 | **25s** |
| 各工具预估秒数 | `crop_canvas/flip/rotate/move/scale/opacity/visible/text/reorder = 0.8`；`adjust_image=2`；`prepare_delivery_sizes=8`；`remove_background=10`；`generate_image/erase_region/replace_region/promote_object_to_layer=40`；`replace_background/expand_canvas/upscale_image/generate_marketing=45`；`batch_process=60`；`split_layers=70` |
| `CATCH_UP_S / SETTLE_S / CREEP_PER_S / EPSILON` | 0.35 / 0.25 / 0.12 / 0.4 |
| `SHAPE` | 2.2 |

### 12.5 Toast 与动画
| 常量 | 值 |
|---|---|
| `STAY_MS` | 3200 |
| `STAY_WITH_ACTION_MS` | 5200 |
| `LEAVE_MS` | 180 |
| 最多同时显示 | **3** 条 |
| `PANEL_EXIT_MS` | 200（面板退场，与 `index.css` 一致） |

### 12.6 数量 / 比例
| 位置 | 限制 |
|---|---|
| 创作页比例 | `1:1 / 4:5 / 3:4 / 9:16 / 16:9`，默认 `1:1` |
| 创作页数量 | `1 / 2 / 4 / 6`，默认 `4` |
| 裁剪比例（工具条） | `自由 / 1:1 / 4:5 / 9:16 / 16:9`（**无 3:4**） |
| 扩图比例（编辑器/批量） | `1:1 / 4:5 / 3:4 / 9:16 / 16:9`（编辑器 GenerateEdits）与 `1:1 / 4:5 / 9:16 / 16:9`（批量 `EXPAND_RATIOS`） |
| 投放尺寸 | 1:1=1080×1080、4:5=1080×1350、9:16=1080×1920 |
| 营销图类型 | 4 种（product/scene/model/poster） |
| 换背景张数 | `1 / 2 / 4`，默认 1 |
| 批量最大图片数 | **20** |
| 批量历史素材快捷入口 | 只取前 **12** 个 |
| 素材库 / 会话列表 limit | **50** |
| 候选页列数 | 1 列（<640px）/ 2 列 |
| 图片墙缩略图 | 64px |
| 会话侧栏 / 右侧面板宽度 | 288px（`w-72`）；`<960px` 面板改绝对定位 |
| 导航条宽度 | 64px（收）→ 208px（`hover`） |

### 12.7 滑杆区间
| 滑杆 | 范围 | 步长 | 原值 |
|---|---|---|---|
| 调色（10 项） | -1 ~ 1 | 0.05 | 0 |
| 晕影 | 0 ~ 1 | 0.05 | 0 |
| 透明度 | 0 ~ 1 | 0.01 | 1 |
| 图层缩放 | 0.1 ~ 3 | 0.05 | 1 |
| 旋转 | -180 ~ 180 | 1 | 0 |
| 字号 | 8 ~ 120 | 1 | 层默认 24 |
| 批量亮度/对比/饱和 | -1 ~ 1 | 0.05 | 0 |

---

## 13. AI 模型依赖矩阵（mock 模式下哪些能真正跑通）

**背景**：图像模型可在后台发布为 `mock` adapter（`MockImageProvider`，本地 PIL 画占位图，不产生费用）；文字规划模型走 `ChatOpenAI`，**mock 不覆盖**。抠图/OCR 走本地可选依赖（rembg/SAM、rapidocr），未安装时自动降级。

| 功能 | 前端入口 | 需要的模型 | mock 模式能否跑通 | 备注 |
|---|---|---|---|---|
| 登录/注册/退出/当前用户 | `/auth`、工作台 | — | ✅ | 纯认证 |
| 上传素材、素材库、历史列表 | `/create` | — | ✅ | |
| 创建/重命名/切换当前会话 | 编辑器、导出页 | — | ✅ | |
| 画布文档类工具：裁剪、翻转、移动、缩放、旋转、透明度、显隐、改文字、图层排序 | 编辑器工具条/图层面板/画布 | — | ✅ | 纯 `edits/document.py` |
| 调色 `adjust_image` | 图层面板调色 | — | ✅ | 纯 PIL；前端另有 9 项实时预览 |
| 投放尺寸 `prepare_delivery_sizes` | 导出页、批量 | — | ✅ | 纯 `letterbox` |
| 去背景 `remove_background` | 工具条、批量 | 本地 rembg（可降级为四角抠图） | ✅（降级可用） | `matting_provider=auto\|rembg\|corner` |
| 文生图（候选图） | 创作页「生成」 | **图像模型** | ✅（占位图） | `POST /api/generations` |
| 换背景 / 扩图 / 超分 | 编辑器、批量 | **图像模型** | ✅（占位图） | 拆层后只进图片墙 |
| 营销图 | 导出页 | **图像模型** | ✅（占位图） | |
| 局部消除 / 局部替换 | 编辑器选择模式 | **图像模型** | ✅（占位图） | 需要先有选区 |
| 选区（点选 / 笔刷） | 编辑器 | **本地 SAM（rembg）**，缺失降级为圆 | ✅（降级可用） | `POST /selection/prepare` 会预热 embedding |
| 成层 `promote_object_to_layer` | 工具条、图层面板 | 选区 + **图像模型**（补洞） | ✅（占位图） | 需先有选区 |
| 拆层 `split_layers` | 工具条、图层面板 | 抠图 + **OCR（rapidocr，可选）** + **图像模型**（背景补洞） | ⚠️ 部分 | 无 rapidocr 时不拆文字层；无图像模型时背景补洞退化 |
| 智能体对话（发指令 → 自动规划多步） | 编辑器左栏 | **真实 LLM（ChatOpenAI 规划器）** | ❌ | mock 只覆盖图像；未发布/不可用时后端 `PlannerUnavailable` |
| 计划确认/取消/重试 | 编辑器左栏 | 依赖计划状态 | ⚠️ | 只能在有真实 LLM 的前提下验证 |
| 批量任务 | `/batch` | 混合（见上） | ✅（依赖图像的步骤出占位图） | |
| ZIP 打包下载 | 导出页、批量页 | — | ✅ | |

**给测试计划的三条判定**
1. **纯前端/纯后端像素链路**（画布工具、调色、投放尺寸、裁剪、图层、文字、显隐、打包）可在无任何模型配置下全量覆盖 —— 这部分应作为主干回归集。
2. **图像模型链路**（生成、换背景、扩图、超分、营销图、局部消除/替换、成层、批量中的对应步骤）用 `mock` adapter 覆盖「请求形状、进度流转、结果落图片墙/画布、失败 toast」，**不要断言画面内容**。
3. **LLM 规划器链路**（智能体对话、计划确认/取消/重试）必须接真实可用文本模型，否则应作为「跳过 / 预期失败」用例单独归组。

---

## 14. 状态与边界速查（测试断言点）

### 14.1 加载中
| 位置 | 文案 |
|---|---|
| `RequireAuth` | 「加载中…」（整屏） |
| 创作页素材区 | 「加载中…」 |
| 编辑器会话加载 | 「加载中」+「正在读取会话状态」 |
| 编辑器历史列表 | 「加载中…」 |
| 编辑器对话 | 「加载中…」 |
| 导出页 Picker | 「加载中…」 |
| 导出页 Workspace | 「加载中」+「正在读取画布与素材」 |
| 批量页 | **无 loading 态**（历史列表为空时不渲染区块） |

### 14.2 空态
| 位置 | 文案 |
|---|---|
| 创作页 | 「还没有素材，先描述画面或上传一张图片。」 |
| 编辑器无会话 | 「打开一个历史对话，或回到创作页开始新的一张。」 |
| 编辑器历史 | 「还没有会话」 |
| 编辑器对话 | 「用一句话说明要怎么改…多步计划会先列出再执行。」 |
| 编辑器编辑记录 | 「暂无记录」 |
| 导出页 Picker | 「还没有可导出的会话，先到 **创作** 打开一张图。」 |
| 导出页打包区 | 「还没有素材。」 |
| 批量页最近任务 | 区块整体不渲染 |

### 14.3 错误态
| 位置 | 标题 / 文案 | 出口 |
|---|---|---|
| 编辑器 会话不存在 | 「会话不存在」/「链接可能已失效，回到创作页新建一个。」 | 「去创作」 |
| 候选页 任务不存在 | 「任务不存在」/「链接可能已失效，回到创作页重新开始。」 | — |
| 候选页 失败/取消 | 「生成失败」/ `{error}` 或「未知原因」 | 「返回重试」→ `/create` |
| 批量页 任务不存在 | 「任务不存在」 | 「返回批量」 |
| 导出页 会话不存在 | 「会话不存在」/「回到列表另选一个会话。」 | 「返回导出物料」 |

### 14.4 权限 / 角色
- 前端**没有**任何基于 `user.role` 的分支；`role: 'user' | 'admin'` 只在类型里存在。
- 被停用账号（`is_active=false`）/ 越权访问他人资源 → 后端 401/403，前端表现为对应 Query 报错（`/auth/me` 401 视为未登录跳 `/auth`；会话/素材 403 会显示「会话不存在」等兜底文案）。
- **测试建议**：普通用户访问他人 `sessionId` / `assetId` 应表现为「会话不存在」/「任务不存在」，而不是 500。

### 14.5 并发与互斥
- 工具层「同时只跑一个任务」：`tools.busy` 为 true 时，除撤销/重做/查看类外全部禁用。
- 撤销/重做链式锁：上一次未 `settled` 时忽略再次点击。
- 智能体计划运行时输入框锁死（`planActive`）。
- 图片墙在 `patch.isPending || tools.busy` 时禁用。
- 编辑器面板互斥：`openCrop` 会关 compare + 选择模式；`setSelectMode` 会关 crop + compare；`setCompareOpen(true)` 会关 crop + 选择模式；`panel === 'replace'` 在离开选择模式时被清空。
- `useEditorUi.selectLayer` 切图层时只清掉**别的**图层的预览（避免拖到一半的位移被清）。

### 14.6 已知的「死代码 / 未接线」点（可用于负面测试或清理记录）
- `hooks/useAssets.ts` 的 `useAssets(limit)` 已定义但**全项目无调用**（`useAssetLibrary` 才是被用的）。
- `pages/PlaceholderPage.tsx` 未被任何路由引用。
- `api/sessions.ts` 的 `sessionsApi.getSelection` 已定义但前端**未调用**（选区由 `useSelection` 的 mutation 返回驱动）。
- `api/agent.ts` 的 `Turn.reply` / `PlanStep.depends_on` / `StepStatus.waiting` 在 UI 上有对应渲染但不产生交互。
- 落地页「上传商品图」按钮**不打开文件选择器**，行为等同提交。

---

## 15. 建议的测试分组（便于直接落地）

| 组 | 覆盖 | 依赖 |
|---|---|---|
| G1 认证与外壳 | `/auth` 注册/登录校验、模式切换、重定向、工作台导航、退出登录 | 无 |
| G2 素材与上传 | `ImageDropzone` 类型/体积拦截、上传成功建会话、素材库分组/展开/打开 | 无 |
| G3 画布纯工具链 | 图层选中/拖动/缩放手柄/排序/显隐/透明度/旋转/裁剪/翻转/改文字/撤销重做/对比 | 无 |
| G4 像素类工具 | 调色（前端实时预览 + 应用）、投放尺寸 | 无 |
| G5 选区链路 | 点选/笔刷/连续点选 append/清除/选区撤销重做/revision 失效 | rembg 可降级 |
| G6 智能体对话 | 发送/计划确认/取消/重试/步骤进度/输入锁 | **真实 LLM** |
| G7 图像生成链路 | 创作页生成 → 候选页 → 进入编辑；换背景/扩图/超分/营销图/局部消除替换/成层/拆层 | 图像模型（mock 够） |
| G8 导出与打包 | 营销图 4 类、投放尺寸 4 按钮、打包勾选/全选/ZIP 下载/toast | 无 |
| G9 批量 | 选图上限/去重/移除、历史素材、5 步 pipeline、草稿校验 5 条、进度、单项失败、打包 | 无 + mock |
| G10 边界与错误 | 413/422/404/401、选区过期、撤销链式锁、并发禁用、SSE 重连、StrictMode 双挂 | — |
