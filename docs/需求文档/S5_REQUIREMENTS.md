# S5 需求文档：文生图链路、候选选图

> 项目：pic-retouch-agent（AI 修图智能体）
> 里程碑：S5 — 一句话生成候选图 → 挑一张进入编辑
> 日期：2026-09-24
> 前置里程碑：S1–S4（已完成）
> 后续里程碑：S6+（测试清理）、S7（启动端口配置化）、S8（品牌 favicon）

## 1. 背景与目标

S1–S4 完成了脚手架、账号体系、素材上传（对象存储）与品牌化落地页。落地页 Hero 的输入面板（S4 的 `PromptComposer`）目前只采集文案并跳转，不产生任何真实请求——这是全产品第一段"用户主动创作"的闭环缺失。

S5 打通第一条完整创作链路：

1. **文生图入口**：创作页出现生成表单（画面描述 + 比例 + 数量 + 排除项），提交后异步执行。
2. **后端任务化**：生成是长耗时操作（真实模型数秒到数十秒），不能阻塞 HTTP 请求。用 Redis 队列（ARQ worker）+ `tool_runs` 表记录任务状态，SSE 实时推送给前端进度。
3. **候选落地**：模型返回的图片链接 24 小时过期，必须转存到自有 MinIO、写入 `assets` 表后才对外暴露。
4. **候选选图**：新增 `/candidates/:runId` 页面，实时看到进度条与候选图网格，选中一张进入后续编辑（S9+）。

**为什么这一里程碑独立**：它引入任务执行模型（队列 + 运行记录 + 进度推送）与 provider 抽象（mock / dashscope），是后续所有工具型能力（编辑、批量、导出）的公共地基。

## 2. 用户与场景

| 角色 | 场景 |
|---|---|
| 已登录创作者 | 在创作页输入"白色陶瓷马克杯放在浅木色桌面"，选竖版 4:5、4 张，点生成 |
| 等待中的用户 | 看到实时进度（排队中 → 生成中 → 保存候选图），而不是空白等待 |
| 批量尝试者 | 一次生成 4 张候选，挑一张满意的进入编辑 |
| 有参考图的用户 | 附带已有素材 id 作为参考图（图生图），模型中图以 base64 内联 |
| 中断/刷新用户 | 刷新后通过快照接口拿到最终候选图与状态，不会停在进度条 |
| 运营/测试 | 无模型 key 时用 mock provider 生成确定性占位图，链路全通 |

## 3. 功能需求

### 3.1 生成表单 F1

- **F1.1** 创作页顶部出现 `GenerateForm`：多行画面描述框（Enter 提交、Shift+Enter 换行、中文输入法合成不误触）、比例分段控件（1:1 / 4:5 / 3:4 / 9:16 / 16:9）、数量分段控件（1 / 2 / 4 / 6）、可折叠排除项输入、生成按钮。
- **F1.2** 比例默认 1:1，数量默认 4；描述框初始值从落地页草稿（sessionStorage）回填，生成成功后草稿清空。
- **F1.3** 提交后按钮变"提交中…"并禁用，避免连点重复创建任务。

### 3.2 任务提交与队列 F2

- **F2.1** `POST /api/generations` 接受 `{prompt, ratio, count, negative_prompt, reference_asset_ids}`；校验通过后返回 **202 Accepted** + 任务快照（`status=queued`），不等生成完成。
- **F2.2** 任务记录写入 `tool_runs` 表，同时以 run id 作为 ARQ job id 投递到队列——重复投递同一 run id 不会产生第二次执行。
- **F2.3** `reference_asset_ids` 引用的素材必须属于当前用户；任一不存在即 **404**。
- **F2.4** 校验：prompt 去空格后非空且 ≤1500 字；count 1–6；ratio ∈ 五个枚举；seed 0–2147483647；参考图 ≤3 张。违规返回 422。

### 3.3 生成执行 F3

- **F3.1** worker 消费任务：启动（RUNNING，进度 5，"已开始"）→ 调用 provider 生成 → 报进度 → 转存候选图（90，"保存候选图"）→ 成功（SUCCEEDED，100，"已完成"）。
- **F3.2** 尺寸由比例映射：1:1→1080×1080、4:5→1080×1350、3:4→1080×1440、9:16→1080×1920、16:9→1920×1080，与交付尺寸对齐，避免生成后二次重采样。
- **F3.3** provider 抽象：`mock`（本地确定性占位图，按提示词哈希构图，零费用）与 `dashscope`（百炼异步接口：提交任务取 task_id → 轮询 3s/超时 300s → 下载结果）。按配置 `IMAGE_PROVIDER` 选择。
- **F3.4** 参考图入参一律 base64 内联（本地 MinIO 无法被模型服务访问）。
- **F3.5** 生成的每张图转存 MinIO、写入 `assets` 表（`kind=generated`、`source=generate`），结果集 `asset_ids` 落回 run.result。
- **F3.6** 失败路径：模型/网络异常 → FAILED + 错误信息；未捕获异常 → rollback + FAILED"生成失败，请重试"。**任何异常都必须落终态**，否则订阅进度的客户端永远挂起。

### 3.4 任务快照查询 F4

- **F4.1** `GET /api/runs/{run_id}`：仅本人可查（跨用户 404）；返回状态/进度/阶段/错误 + 候选图列表。
- **F4.2** 候选图的签名 URL 有有效期，每次读取时重新签发。

### 3.5 实时进度 SSE F5

- **F5.1** `GET /events/runs/{run_id}`（挂载在 `/api` 前缀外，便于反向代理单独关闭缓冲）推送任务每个状态变更。
- **F5.2** 先订阅再读快照：任务在两步之间结束也不会让连接空等；断线重连时客户端先收到快照，不丢状态。
- **F5.3** 空闲 >15s 发 `: ping` 心跳；总时长 >600s 主动断开；终态后关闭连接。

### 3.6 候选选图页 F6

- **F6.1** 提交生成后跳转 `/candidates/:runId`；未终态时显示实时进度条 + 阶段文案 + 百分比。
- **F6.2** 终态成功显示候选图网格：序号角标、点击选中（`aria-pressed`）、顶栏显示已选状态。
- **F6.3** 选中后"进入编辑"钮可用，跳转 `/editor?asset={id}`（编辑页 S9+ 实现，先带参跳转）。
- **F6.4** 失败/取消显示错误原因 +"返回重试"链接；任务不存在显示提示 + 回到创作页。
- **F6.5** SSE 进度与快照接口双源并用：SSE 给实时性，快照管刷新恢复与候选图；SSE 中断时回退到快照，不卡在过期进度。

## 4. 非功能需求

| 编号 | 类别 | 描述 |
|---|---|---|
| NFR1 | 性能 | 生成不阻塞 HTTP 请求（202 即返）；SSE 单连接，终态即断 |
| NFR2 | 一致 | 时间统一带时区（`DateTime(timezone=True)`），全库迁移对齐 |
| NFR3 | 复用 | provider 通过工厂按配置装配，新增平台只登记一处 |
| NFR4 | 安全 | run/素材均按 user_id 隔离校验；SSE 同样鉴权 |
| NFR5 | 可测 | mock provider 确定性输出；worker 幂等（终态不重跑）；pytest 覆盖主链路 |
| NFR6 | 可观测 | 异常走 `logger.exception` 带 run_id；任务终态必达，不悬挂 |
| NFR7 | 扩展 | 枚举存 VARCHAR（非 PG 原生 enum），增删取值无需 ALTER TYPE |

## 5. 数据模型

| 表 | 字段 | 说明 |
|---|---|---|
| `tool_runs` | id, user_id(FK→users, CASCADE), tool(48), status(queued/running/succeeded/failed/canceled), progress, stage, params(JSONB), result(JSONB), error(Text), retries, started_at, finished_at, created_at | 单次工具调用的执行记录；run id 兼作队列 job id |

`assets` 现有表补两处枚举列类型声明（`kind`/`source` 从裸 String 换 `enum_column`，存储值不变）。

## 6. 技术约束

- 沿用现有栈：FastAPI + SQLAlchemy 2 async + ARQ/Redis + MinIO + React 19 + react-query。
- 零新增后端依赖（httpx/pillow 已在依赖中）；前端零新增 npm 依赖（EventSource 原生）。
- 结果显示一律走既有 `AssetOut.of`（重新签名 URL）。

## 7. 验收标准

| 编号 | 描述 |
|---|---|
| AC1 | 创作页出现生成表单；提交即 202 返回任务；跳转候选页 |
| AC2 | 候选页实时看到进度（排队 → 生成 → 保存）；成功显示 4 张 1080×1080 候选图 |
| AC3 | 竖版 4:5 生成的候选图为 1080×1350 |
| AC4 | 空提示词 / 非法比例 / count 0 或 7 均 422；未知参考图 404 |
| AC5 | 未登录提交或查任务 401；A 用户查 B 用户任务 404 |
| AC6 | 同一任务投递两次只产出一次候选图（幂等） |
| AC7 | SSE 终端态回放快照后关闭；跨用户订阅 404 |
| AC8 | mock provider 下整链路（登录→生成→SSE→取图→下载 PNG）端到端通过 |
| AC9 | `pytest` 全绿；`tsc -b` + 前端 lint 通过 |
| AC10 | 切到真实模型只需配置 `IMAGE_PROVIDER=dashscope` + key，代码零改动 |

## 8. 范围与非范围

**本里程碑范围**：

- 后端：`tool_runs` 模型 + 迁移（建表 + 时间字段带时区化）；`providers/`（base/mock/dashscope + 工厂）；`ratios.py` 尺寸映射；`queue.py` / `events.py` pub-sub；`runs` / `generation` 服务；`/generations` + `/runs/{id}` + SSE 路由；worker 任务 `generate_images`；`scripts/e2e_generation.py` 端到端脚本；`test_generation.py`。
- 前端：`api/runs.ts`、`hooks/useRun.ts`（SSE+快照合并）、`GenerateForm`、`CandidatesPage`、`CreatePage` 接入、`App` 路由（`/candidates/:runId`）。
- 配置：`config.py` 增加 `dashscope_base_url`；`.env.example` / `.env` 补 `DASHSCOPE_BASE_URL`。

**本里程碑非范围**：

- 真实编辑 / 抠图（S9+）；`/editor` 仍是占位页（仅接受 `?asset=` 参数）
- 素材批量 / 导出（S10+）
- 未登录的生成入口（生成需要账号与存储隔离）
- 任务取消 / 队列管理界面 / 多 worker 横向扩展监控

## 9. 后续依赖

- **S9 编辑**：`/editor?asset=` 接住候选图 id，开始真实编辑。
- **S10 导出**：`DELIVERY_RATIOS` 复用交付尺寸，物料包导出直接对齐。
- **后续工具**（抠图/批量）：`ToolRun` 是公共执行模型，`tool` 字段区分。
- **真实模型上线**：置 key + `IMAGE_PROVIDER=dashscope` 即切换，链路无需改动。