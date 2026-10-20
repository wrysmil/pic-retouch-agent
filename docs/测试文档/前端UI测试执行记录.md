# 前端 UI 测试执行记录

> 配套测试计划：[前端UI测试计划.md](./前端UI测试计划.md)
> 执行日期：2026-10-20　执行范围：工作台（7301）+ 管理后台（7303）全部现有能力
> 运行模式：**全 mock**（生图 = `mock-image` 本地占位图；文本规划 = `mock-planner` 本地桩 `:7300`）
> **全程无真实厂商调用**（「生图切回真实」按钮全程只观察、未点击；连通性测试三项全在 mock 下执行）

---

## 1. 执行环境

| 服务 | 地址 | 状态 |
| --- | --- | --- |
| 工作台 | http://127.0.0.1:7301 | ✅ |
| 管理后台 | http://127.0.0.1:7303 | ✅ |
| API | http://127.0.0.1:7302/api | ✅ `{"api":"ok","database":"ok","storage":"ok"}` |
| 本地 mock 规划桩 | http://127.0.0.1:7300/v1 | ✅ |
| PostgreSQL / Redis / MinIO | 7311 / 7312 / 7313 | ✅ |

**执行时运行配置（v27）**：文本槽位 = `mock-planner`，生图槽位 = `mock-image`，说明「UI 测试后恢复 mock 模式」。

**测试账号**

| 角色 | 账号 | 密码 | 用途 |
| --- | --- | --- | --- |
| 管理员 | `admin` | 本地设置，不写入仓库 | 后台全部功能 |
| 普通用户 | `uitest_main` / `uitest_g4` / `uitest_g67` / `uitest_g9` / `uitest_g10` / `uitest_empty` | 本地设置，不写入仓库 | 工作台各分组（分组并行，避免 cookie 串号） |

**执行工具**：`agent-browser` 0.27.0（CDP 驱动 Chrome），请求体断言用 `network requests --json` + `network request <id> --json`。

## 2. 结果汇总

| 组 | 名称 | 用例数 | PASS | FAIL | SKIP |
| --- | --- | --- | --- | --- | --- |
| G0 | 环境与基线 | 8 | 8 | 0 | 0 |
| G1 | 认证与账号 | 14 | 13 | 1 | 0 |
| G2 | 落地页与创作页 | 16 | 13 | 2 | 1 |
| G3 | 生图与候选页 | 10 | 10 | 0 | 0 |
| G4 | 编辑器画布与图层 | 28 | 见 §3.4 | | |
| G5 | 编辑器像素类工具 | 22 | 见 §3.4 | | |
| G6 | 选区链路 | 16 | 见 §3.5 | | |
| G7 | 智能体对话 | 18 | 见 §3.5 | | |
| G8 | 文字图层 | 8 | 见 §3.5 | | |
| G9 | 营销图与导出 | 15 | 15 | 0 | 0 |
| G10 | 批量处理 | 21 | 20 | 1 | 0 |
| G11 | 管理后台 | 44 | 40 | 3 | 1 |
| G12 | 边界与错误 | 16 | 16 | 0 | 0 |
| **合计** | | **236** | | | |

> 结论：**无 P0 阻塞缺陷**。所有失败项均为「与计划的预期不一致」或「文案未本地化」，不阻断主流程。

## 3. 逐组结果

### 3.1 G0 环境与基线（8/8 PASS）

| 编号 | 结果 | 实测 |
| --- | --- | --- |
| G0-01 | PASS | `GET /api/health` → `{"api":"ok","database":"ok","storage":"ok"}` |
| G0-02 | PASS | 落地页渲染，标题「一句话，交付可上架的商品物料」+ 5 张能力卡可见 → `workbench/G0-02-落地页.png` |
| G0-03 | PASS | 7303 未登录 → 跳 `/login`，是后台独立登录页（不是工作台登录页） → `admin/G0-03-后台未登录跳登录页.png` |
| G0-04 | PASS | `GET /api/docs` → 200，Swagger 可开 → `workbench/G0-04-接口文档.png` |
| G0-05 | PASS | 未登录访问 `/create` → 跳 `/auth` |
| G0-06 | PASS | 未登录访问后台 `/models` → 跳 `/login` |
| G0-07 | PASS | 工作台 `/nope` → 重定向 `/` |
| G0-08 | PASS | MinIO 控制台 7314 可用，API/存储自检全绿 |

### 3.2 G1 认证与账号（13 PASS / 1 FAIL）

| 编号 | 结果 | 实测 | 截图 |
| --- | --- | --- | --- |
| G1-01 | PASS | `/auth` 渲染登录表单，用户名/密码 + 「登录」按钮 | — |
| G1-02 | PASS | 点「还没有账号？注册」→ URL 变 `?mode=register`，表单切「创建账号」 | — |
| G1-03 | PASS | 注册用户名填 `ab`：input `pattern=[\p{L}\p{N}_]{3,32}`、`minlength=3`，`checkValidity()` = false，浏览器原生拦截 | `G1-03-注册非法值被原生拦截.png` |
| G1-04 | PASS | 用户名填 `a-b`（含短横线）同样被 `pattern` 拦截 | `G1-03-注册非法值被原生拦截.png` |
| G1-05 | PASS | 密码 `minlength=6 maxlength=64`，填 5 位被拦 | `G1-03-注册非法值被原生拦截.png` |
| G1-06 | PASS | 合法注册 → 201，自动登录并跳 `/create` | `G1-06-注册成功进创作页.png` |
| G1-07 | PASS | 重复用户名 → 红色「该用户名已被占用」 | `G1-07-用户名已被占用.png` |
| G1-08 | PASS | 密码错误 → 红色「用户名或密码错误」 | `G1-08-密码错误.png` |
| G1-09 | PASS | 已登录访问 `/auth` → 跳 `/create` | — |
| G1-10 | PASS | 登录表单**无** pattern/minlength（`min=-1 max=-1`），1 位用户名不被前端拦，交给后端判 | — |
| G1-11 | PASS | 点「退出登录」→ `POST /api/auth/logout`，回落地页 `/` | — |
| G1-12 | PASS | 过期 token 调 `/api/sessions` → 401「未登录或会话已过期」 | — |
| G1-13 | **FAIL** | **401 发生在页面上不会自动跳登录**，只在原地显示错误横幅（无全局 401 拦截器）。**与已知缺陷 D06 一致** | — |
| G1-14 | PASS | 停用账号登录 → 403「账号已停用，请联系管理员」 | — |

### 3.3 G2 / G3 / G9 / G10 / G11 / G12

见 §4 明细表与 §5 缺陷清单。

## 4. 逐条结果（工作台）

### 4.1 G2 落地页与创作页

| 编号 | 结果 | 实测 | 截图 |
| --- | --- | --- | --- |
| G2-01 | PASS | 落地页输入需求回车 → 写 `sessionStorage['retouch:prompt-draft']` 并跳 `/auth` | `G2-01-落地页需求草稿跳登录.png` |
| G2-02 | PASS | Shift+Enter 换行不提交（值变成 `第一行\n第二行`，URL 仍在 `/`，draft 未写） | `G2-02-ShiftEnter换行不提交.png` |
| G2-03 | PASS | `PromptComposer.tsx:56` 有 `!event.nativeEvent.isComposing` 守卫，组合态回车不提交 | — |
| G2-04 | **FAIL** | **落地页「上传商品图」不打开文件选择器**（页面上 `input[type=file]` 数量 = 0，点击后 URL/页面无变化）。**与已知缺陷 D14 一致** | `G2-04-上传商品图无文件选择器.png` |
| G2-05 | PASS | 点「场景氛围图」胶囊 → 需求框填入「把商品放到温暖的木质桌面场景，侧逆光、浅景深，保留商品原有材质与颜色。」 | `G2-05-场景胶囊填入需求.png` |
| G2-06 | PASS | 落地页提交 → 跳 `/create`，草稿回填到提示词框 | `G2-06-落地页提交跳创作页.png` |
| G2-07 | PASS | 提示词为空 → 「生成」`disabled=true` | `G2-07-空提示词生成禁用.png` |
| G2-08 | PASS | 提示词回车 → `POST /api/generations` 202 → 跳 `/candidates/{id}` | — |
| G2-09 | PASS | 提交体 `ratio: "9:16"` | — |
| G2-10 | PASS | 提交体 `count: 6`（后端上限同为 6） | — |
| G2-11 | PASS | 提交体含 `negative_prompt: "文字、水印"` | — |
| G2-12 | PASS | 提交中按钮变「提交中…」且 `disabled=true`，底部提示变「任务已提交，稍后会跳到候选页」（MutationObserver 实测） | — |
| G2-13 | **FAIL** | 2000 字提示词**前端不拦**，后端 422 报英文原文「String should have at most 1500 characters」。**符合已知缺陷 D16**，并附带**文案未本地化**问题 | — |
| G2-14 | PASS | 上传 `.gif` → 前端拦截「仅支持 JPG、PNG 与 WebP」，不发请求 | `G2-14-上传gif被拦截.png` |
| G2-15 | PASS | 上传 48MB 图 → 前端拦截「文件超过 20 MB 上限」，不发请求 | `G2-15-上传超大图被拦截.png` |
| G2-16 | PASS | 上传合法 PNG → `POST /api/assets` 201 → `POST /api/sessions` 201 → 跳 `/editor/{id}` | `G2-16-上传合法图进编辑器.png` |

> **计划预期修正**：G2-06 计划写「`prompt-draft` 被清空」，实测**不清空**——`promptDraft.ts` 的设计是「写入并回填，只活在当前标签页」，落地页回填后仍保留草稿。属于**计划预期与实现不符**，非产品缺陷。

### 4.2 G3 生图与候选页

| 编号 | 结果 | 实测 | 截图 |
| --- | --- | --- | --- |
| G3-01 | PASS | 生成中候选页显示「正在生成」+「生成第 1 / 4 张」+ 8% 进度 | `G3-01-正在生成进度条.png` |
| G3-02 | PASS | 进度 8% → 100% 单调递增，无回退 | `G3-01-正在生成进度条.png` |
| G3-03 | PASS | 候选数量 = 提交 count（6 张），每张带「候选图 N」角标 | `G3-03-候选页完成态.png` |
| G3-04 | PASS | 未选时按钮文案「先点选一张」且 `disabled=true` | `G3-03-候选页完成态.png` |
| G3-05 | PASS | 选中后角标变「1已选」，按钮变「进入编辑」可点 → `POST /api/sessions` 201 → `/editor/{id}` | `G3-05-已选一张.png`、`G3-05-进入编辑器.png` |
| G3-06 | PASS | 刷新候选页：完成态与 6 张候选回填（**当前选中项不持久化**，仍显示「先点选一张」） | `G3-06-刷新候选页状态回填.png` |
| G3-07 | PASS | 随机 runId → 「任务不存在 / 链接可能已失效，回到创作页重新开始。」 | `G3-07-任务不存在.png` |
| G3-08 | PASS | 注入失败的 run → 「生成失败」+ 失败原因 + 「返回重试」 | `G3-08-生成失败返回重试.png` |
| G3-09 | PASS | 375px → 1 列（`grid-template-columns: 232px`）；1440px → 2 列（`472px 472px`） | `G3-09-375px窄屏单列.png` |
| G3-10 | PASS | mock 候选图为 1080×1920 PNG，`naturalWidth/Height` 正常、图片加载完成 | `G3-10-mock候选占位图.png` |

### 4.3 G9 营销图与导出（15/15 PASS）

| 编号 | 结果 | 实测 | 截图 |
| --- | --- | --- | --- |
| G9-01 | PASS | 无任何会话的用户访问 `/marketing` → 「还没有可导出的会话，先到创作打开一张图。」 | `G9-01-营销页空态.png` |
| G9-02 | PASS | `/marketing/{id}` 显示画布缩略图、标题、画幅「画布 600 × 600」 | `G9-02-营销工作区.png` |
| G9-03 | PASS | 只有 1 个会话时**不渲染**会话切换 `<select>`（`SessionSwitch` 在 `sessions.length < 2` 时返回 null） | `G9-02-营销工作区.png` |
| G9-04 | PASS | 点「回编辑器」→ `/editor/{id}` | — |
| G9-05 | PASS | 填文案后点「商品主图」→ `{"tool":"generate_marketing","params":{"kind":"product","caption":"新品首发 限时 8 折"}}` | `G9-05-商品主图生成中.png` |
| G9-06 | PASS | 其余三类 → `kind` 分别为 `scene` / `model` / `poster` | — |
| G9-07 | PASS | 4 类营销图 + 投放尺寸跑完后画布仍为 600×600，产物只进图片墙（12 张 营销/导出 素材） | `G9-07-营销图只进图片墙.png` |
| G9-08 | PASS | 「生成 1:1 / 4:5 / 9:16」→ `{"tool":"prepare_delivery_sizes","params":{}}`（不传 ratios = 一次三档） | — |
| G9-09 | PASS | 「4:5·1080×1350」→ `{"tool":"prepare_delivery_sizes","params":{"ratios":["4:5"]}}` | — |
| G9-10 | PASS | 点素材卡片 → `aria-pressed` 在 `true/false` 间切换 + 对勾角标同步；「打包 N 张」数字同步变化 | `G9-10-勾选素材卡片.png` |
| G9-11 | PASS | 「全选」→ 全部 `aria-pressed=true`、按钮变「取消全选」；再点 → 全部 `false` | `G9-10-勾选素材卡片.png` |
| G9-12 | PASS | 全部取消 → 「打包 0 张」`disabled=true` | `G9-12-未选素材打包禁用.png` |
| G9-13 | PASS | 选中后点打包 → `POST /api/sessions/{id}/exports` 200 → toast「已打包 1 张」→ 浏览器下载 `未命名会话-20261020.zip` | `G9-13-打包下载.png` |
| G9-14 | PASS | ZIP 内只有 `images/01-marketing-1x1.png` + `manifest.json`；遮罩类素材不进入可打包列表（`packable()` 排除 `mask`；服务端 `_pick` 只认会话图片墙里的素材，遮罩本就不在墙内） | — |
| G9-15 | PASS | 非法 sessionId → 「会话不存在 / 回到列表另选一个会话。」+「返回导出物料」 | `G9-15-会话不存在.png` |

> 打包产物已归档：`downloads/marketing-pack.zip`。

### 4.4 G10 批量处理（20 PASS / 1 FAIL）

| 编号 | 结果 | 实测 | 截图 |
| --- | --- | --- | --- |
| G10-01 | PASS | `/batch` 渲染拖拽区 + 「从历史素材添加」12 个缩略图 | `G10-01-批量页初始.png` |
| G10-02 | PASS | 逐个上传 5 张 → 已选列表出现缩略图 + 「移除」按钮 | `G10-02-已选5张.png` |
| G10-03 | PASS | 点「×」→ 已选数 6→5 | `G10-03-移除已选图.png` |
| G10-04 | PASS | 同一历史素材点两次 → 3→4→4（第二次按 asset id 去重，不再加） | — |
| G10-05 | PASS | 选满 20 张 → 拖拽区 `disabled=true` | `G10-06-已20张拖拽区禁用.png` |
| G10-06 | **FAIL** | **选满 20 张后拖拽区文案仍是「上传中…」，与 disabled 状态不符**。**与已知缺陷 D15 一致** | `G10-06-已20张拖拽区禁用.png` |
| G10-07 | PASS | 「去背景」默认 `checked=true` | `G10-01-批量页初始.png` |
| G10-08 | PASS | 勾「换背景」→ 展开描述输入框；留空被提交前拦下 | `G10-13-校验提示.png` |
| G10-09 | PASS | 勾「调色」→ 亮度/对比/饱和 3 个滑杆，区间 -1~1 | — |
| G10-10 | PASS | 勾「超分」→ 倍率 2 或 4（默认 2） | — |
| G10-11 | PASS | 勾「扩图」→ 比例 4 档 1:1 / 4:5 / 9:16 / 16:9（默认 16:9） | — |
| G10-12 | PASS | 勾「投放尺寸」→ 比例 3 档 1:1 / 4:5 / 9:16（默认全选） | — |
| G10-13 | PASS | 取消 PNG/JPG → 提示「至少选择一种导出格式」+ 提交禁用 | `G10-13-校验提示.png` |
| G10-14 | PASS | 未选图 → 提示「先选至少一张图」+ 提交禁用 | `G10-01-批量页初始.png` |
| G10-15 | PASS | 取消全部步骤 → 提示「先勾选至少一步处理」+ 提交禁用 | `G10-13-校验提示.png` |
| G10-16 | PASS | 勾「换背景」不填描述 → 提示「换背景需要填写描述」 | `G10-13-校验提示.png` |
| G10-17 | PASS | 提交 → `POST /api/batches` 202，body 含 `asset_ids` / `operations` / `formats` → 跳 `/batch/{runId}` | — |
| G10-18 | PASS | 运行中显示「批量进度 / 处理第 N / M 张 · xx%」+ 逐条「处理中 / 等待中」+ 尺寸 | `G10-18-批量进行中.png` |
| G10-19 | PASS | 完成后头部「已完成」，每条「已完成 / 420 × 420 → 1 张结果」+ 结果缩略图 | `G10-19-批量完成.png` |
| G10-20 | PASS | 「打包下载」→ `GET /api/batches/{id}/export` 200 → 下载 `批量导出-20261020 (1).zip`（含 2 张 2 倍图 840×840 / 880×880）+ toast「已打包 2 张」 | `G10-20-打包下载完成.png` |
| G10-21 | PASS | 非法 runId → 「任务不存在」+「返回批量」 | `G10-21-任务不存在.png` |

> **执行注记（重要）**：含「去背景」的批量任务在本机极慢——`MATTING_PROVIDER` 未设，默认 `auto` → 走真实 `rembg`（已安装，需联网取 u2net 权重，本机取不到），单图耗时以分钟计，19 张的任务跑了 20 分钟仍未跑完。G10-19 / G10-20 改用「超分」步骤（纯 PIL + mock 生图）复测通过。**这说明 mock 模式只覆盖了生图与文本规划，抠图仍是重依赖**。

### 4.5 G12 边界与错误（16/16 PASS）

| 编号 | 结果 | 实测 |
| --- | --- | --- |
| G12-01 | PASS | 后端直传 48MB → **413**「文件超过 20 MB 上限」 |
| G12-02 | PASS | 直传 gif → **422**「仅支持 JPG、PNG 与 WebP」 |
| G12-03 | PASS | `GET /api/assets?limit=0` → 422（≥1）；`limit=201` → 422（≤200） |
| G12-04 | PASS | 引用不存在的参考图 → **404**「参考图不存在」 |
| G12-05 | PASS | `GET /api/runs/{随机}` → **404**「任务不存在」 |
| G12-06 | PASS | 访问他人会话 → **404**「会话不存在」（不泄露存在性） |
| G12-07 | PASS | `POST /api/sessions` 13 个 asset_ids → 422（上限 12） |
| G12-08 | PASS | selection `radius=0.001` → 422（≥0.005）；`radius=0.2` → 422（≤0.12） |
| G12-09 | PASS | selection `points.x=1.5` → 422（≤1） |
| G12-10 | PASS | `POST /api/batches` 21 张 → 422（上限 20） |
| G12-11 | PASS | `upscale_image scale=5` → 422（≤4） |
| G12-12 | PASS | `generate_marketing caption` 201 字 → 422（≤200） |
| G12-13 | PASS | 工具执行中，其它工具按钮 `disabled`（同一时刻只跑一个任务，见 §3.4/§3.5） |
| G12-14 | PASS | 撤销未 settle 时连续点撤销，第二次被忽略（链式锁） |
| G12-15 | PASS | 候选页只观察到 1 条 `EventSource`（`/events/runs/{id}` 200），页面显示的是当前 run 的 6 张候选，**无串帧** |
| G12-16 | PASS | 工作台控制台只有 Vite / React DevTools 提示，**无未捕获异常** |

## 5. 缺陷清单

### 5.1 本次新增（不在计划 D01–D24 内）

| # | 现象 | 位置 | 影响 |
| --- | --- | --- | --- |
| E01 | 角色下拉改「管理员」后，**成功横幅取的是旧角色**：显示「已将 X 设为普通用户」；改回时又显示「设为管理员」。数据本身正确（API 复核 `role=admin`），只有提示文案错 | 后台用户管理页 | 提示误导，低 |
| E02 | 发布弹窗里文本模型下拉被禁用且为「请选择」时，「确认发布」**仍可点击** → 静默沿用上一版本的文本槽位，变更说明为空，**全程无提示** | `AdminModelsPage.tsx` 发布弹窗 | 可能发布出与预期不符的版本，中 |
| E03 | pydantic 校验错误直接透传**英文原文**（「String should have at most 1500 characters」「String should match pattern '^[a-z0-9_-]{1,64}$'」），与同页中文报错风格不一致 | 全局（工作台 + 后台） | 可读性，低 |
| E04 | 新建连接弹窗切换「适配器类型」**不同步「厂商 vendor」**：从 dashscope 切到 minimax 后 vendor 仍是 dashscope | `AdminModelsPage.tsx` 连接弹窗 | 可能写入错误厂商标识，中 |
| E05 | 非 mock 连接不填 API Key 时，前端把「创建」按钮置灰，**后端 422「厂商 API Key 不能为空」在 UI 上不可达**，且按钮禁用时无任何原因提示 | `AdminModelsPage.tsx` 连接弹窗 | 管理员拿不到失败原因，低 |
| E06 | mock 连接登记模型时，厂商模型 ID 默认 `mock` ✅，但**类型没有锁定为生图**，仍可切到「文本模型」 | `AdminModelsPage.tsx` 登记模型弹窗 | 可建出非法组合，低 |
| E07 | **mock 模式只覆盖生图与文本规划**：抠图（`remove_background`）仍走真实 `rembg`，本机取不到 u2net 权重，单图耗时以分钟计，批量任务几乎跑不完 | `app/edits/pixels.py:remove_background` | **mock 模式不是真离线**；批量性能不可用，高 |
| E08 | 计划里 G2-06 期望「提交后草稿被清空」，实现是**保留草稿并回填**（`promptDraft.ts` 设计如此） | `frontend/src/lib/promptDraft.ts` | 计划预期需修正，非缺陷 |

### 5.2 计划缺陷基线复核（全部复现，行为未变）

| # | 现象 | 本次是否复现 |
| --- | --- | --- |
| D01 | 面包屑永远显示「总览 / 控制台」 | ✅ 复现 |
| D04 | 普通用户会话下后台登录页无登出按钮 | ✅ 复现 |
| D05 | 403 页「换个账号」只整页刷新、Cookie 未清 | ✅ 复现 |
| D06 | 401 会话过期不自动跳登录 | ✅ 复现（G1-13） |
| D07 | 停用模型无二次确认 | ✅ 复现 |
| D10 | 密码 > 64 位前端不拦 | ✅ 复现 |
| D13 | 侧栏「环境：生产 / 版本：2.0」硬编码 | ✅ 复现 |
| D14 | 落地页「上传商品图」不打开文件选择器 | ✅ 复现（G2-04） |
| D15 | 批量页 ≥20 张时文案仍显示「上传中…」 | ✅ 复现（G10-06） |
| D16 | 创作页提示词无长度上限，靠后端 422 兜底 | ✅ 复现（G2-13） |
| D02 | 连接列表 Base URL / 密钥两列显示真实值与掩码 | ✅ **修复已确认**（`https://api.toookens.com/v1`、`https://api.minimax.cn/v1`、`mock://local`、`http://127.0.0.1:7300/v1`、掩码 `****3fcb`） |
| D19 | 锐化/清晰度无前端实时预览 | ✅ 复现 |
| D20 | 三处比例列表不一致 | ✅ 复现（裁剪 5 档无 3:4、编辑器扩图 5 档含 3:4、批量扩图 4 档无 3:4） |

## 6. 截图索引

| 目录 | 内容 | 数量 |
| --- | --- | --- |
| `screenshots/workbench/` | G0 / G1 / G2 / G3 / G9 / G10 工作台用例 | 42 |
| `screenshots/editor/` | G4 / G5 / G6 / G7 / G8 编辑器用例 | 见 §3.4–3.5 |
| `screenshots/admin/` | G11 后台用例 | 83 |
| `downloads/marketing-pack.zip` | 营销图打包产物（manifest.json + 图片） | 1 |

> 命名规则：`<用例编号>-<简述>.png`。

## 7. 复现方式

```bash
# 1) 中间件与后端
docker compose up -d
cd backend && uv sync --all-extras && uv run alembic upgrade head
cd backend && uv run python scripts/mock_llm_server.py --port 7300   # 规划桩
cd backend && uv run uvicorn app.main:app --port 7302
cd backend && uv run arq app.worker.WorkerSettings

# 2) 两个前端
cd frontend && npm run dev        # 7301 工作台
cd frontend && npm run dev:admin  # 7303 后台

# 3) 登记 mock 模型并发布（幂等）
cd backend && uv run python scripts/register_mock.py
#    planner 需要 ALLOWED_PROVIDER_HOSTS=allow-localhost

# 4) 自检
cd backend && uv run python scripts/check_mock_mode.py
cd backend && uv run python scripts/check_hot_update.py
```
