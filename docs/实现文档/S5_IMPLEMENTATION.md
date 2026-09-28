# S5 实现文档：文生图链路、候选选图

> 项目：pic-retouch-agent
> 里程碑：S5
> 日期：2026-09-24

## 1. 仓库状态变化

| 提交 | 内容 |
|---|---|
| S1–S4（已存在） | 脚手架 / 基础设施 / 账号体系 / 素材上传 / 品牌化落地页 |
| **S5（本里程碑）** | 文生图全链路：`tool_runs` 执行模型 + provider 抽象 + ARQ 队列 + SSE 进度 + 候选转存 + 候选选图页 |

32 个文件，1472 行新增。后端零新增依赖；前端零新增 npm 依赖。

## 2. 数据模型

### 2.1 新增 `tool_runs` 表

```python
# backend/app/models/tool_run.py
class RunStatus(enum.StrEnum):
    QUEUED = "queued"; RUNNING = "running"
    SUCCEEDED = "succeeded"; FAILED = "failed"; CANCELED = "canceled"
    @property
    def is_terminal(self) -> bool:
        return self in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELED}

class ToolRun(UUIDBase):
    __tablename__ = "tool_runs"
    user_id: Mapped[uuid.UUID]   # FK→users.id, CASCADE, index
    tool: Mapped[str]            # String(48) —— 区分具体工具
    status: Mapped[RunStatus]    # enum_column, 默认 queued
    progress: Mapped[int]        # 0–100，单调不减
    stage: Mapped[str]           # String(64) 人类可读阶段文案
    params: Mapped[dict]         # JSONB 入参快照
    result: Mapped[dict]         # JSONB 结果（asset_ids）
    error: Mapped[str | None]    # Text
    retries: Mapped[int]
    started_at / finished_at     # DateTime(timezone=True), nullable
```

**设计要点**：run id 同时作为 ARQ `_job_id`，重复投递同一 run id 会命中已存在的 job，不产生第二次执行——幂等免费获得。

### 2.2 枚举统一存 VARCHAR

`base.py` 新增两个全库辅助（沿用 SQLAlchemy 的 `Enum(native_enum=False)`）：

```python
ENUM_LENGTH = 16
TIMESTAMPTZ = DateTime(timezone=True)

def enum_column(enum_cls):
    return Enum(enum_cls, native_enum=False, create_constraint=False,
                values_callable=lambda cls: [m.value for m in cls], length=ENUM_LENGTH)
```

`Asset.kind` / `Asset.source` 由裸 `String(16)` 换 `enum_column(AssetKind)` / `enum_column(AssetSource)`——存储值不变（仍是那几串小写字符串），读出来却是 Python 枚举成员。不用 PG 原生 enum 的原因是：增删取值只需改代码，不用 `ALTER TYPE`。

`UUIDBase.created_at` 从 `DateTime()` 改 `TIMESTAMPTZ`。

**两条迁移**（参考 S5 提交自带，revision 链接在既有 `96be783bb53e` 之后）：
- `20260826_1725_tool_runs` → 建 `tool_runs` 表（revision `5955abb6da37`）
- `20260826_1737_timestamptz` → `assets`/`tool_runs`/`users` 的 created_at、`tool_runs` 的 started_at/finished_at 改为带时区（revision `9091f7ebd312`）

迁移文件名沿用参考提交的日期，但**生成方式用 alembic autogenerate 校准**（见 §8 验证），确保与当前模型一致。

## 3. 尺寸映射 `ratios.py`

```python
class Ratio(enum.StrEnum):
    SQUARE = "1:1"; PORTRAIT_4_5 = "4:5"; PORTRAIT_3_4 = "3:4"
    VERTICAL_9_16 = "9:16"; LANDSCAPE_16_9 = "16:9"

SIZES = {  # 与交付尺寸对齐，生成后不再重采样
    Ratio.SQUARE: (1080, 1080), Ratio.PORTRAIT_4_5: (1080, 1350),
    Ratio.PORTRAIT_3_4: (1080, 1440), Ratio.VERTICAL_9_16: (1080, 1920),
    Ratio.LANDSCAPE_16_9: (1920, 1080),
}
DELIVERY_RATIOS = (Ratio.SQUARE, Ratio.PORTRAIT_4_5, Ratio.VERTICAL_9_16)  # S10 导出复用
```

## 4. Provider 抽象 `providers/`

```
providers/
├─ base.py       GenerateRequest（frozen dataclass）+ ImageProvider Protocol + ProviderError
├─ mock.py       MockImageProvider：确定性占位图
├─ dashscope.py  DashScopeImageProvider：异步任务 + 轮询
└─ __init__.py   get_image_provider()：@lru_cache 工厂，按配置装配
```

| 决策 | 理由 |
|---|---|
| `GenerateRequest` 带 `references: list[bytes]` | provider 不感知对象存储，参考图一律原始字节；base64 编码是各 adapter 自己的事 |
| DashScope 用**异步接口**（提交→`task_id`→轮询） | 部分账号不开放同步调用；异步路径提供真实的 PENDING/RUNNING 状态，正好映射到进度条 |
| `_PROGRESS = {"PENDING": (10, "排队中"), "RUNNING": (45, "生成中")}` | UI 阶段文案由 provider 给出，前端只渲染 |
| 轮询间隔 3s、总超时 300s、HTTP 超时 30s | 生成 4 张百炼通常 30–90s，300s 给足余量 |
| 结果 URL **立即下载**（独立 60s 超时 client） | 模型返回链接 24h 过期，须转存自有存储 |
| mock：`hashlib.sha256(prompt).hexdigest()[:8]` 作种子 + 4 个叠加圆 | 同一提示词结果稳定，测试可断言；0.4s/张模拟耗时 |
| 文件非 UTF-8 安全 | mock `_render` 用 `io.BytesIO` 输出 PNG |

## 5. 任务执行链路

### 5.1 队列 `queue.py`

延迟初始化 `ArqRedis` 连接池（worker 与 API 共用同一函数）：

```python
async def enqueue(task: str, run_id: uuid.UUID) -> None:
    pool = await queue()
    await pool.enqueue_job(task, run_id, _job_id=str(run_id))
```

- `close_queue()` 挂在 FastAPI lifespan 的 shutdown 段（`yield` 之后）。
- **worker 定义**：ARQ worker 需要 `functions` 列表。参考提交在 `tasks/__init__.py` 维护 `TASKS = [ping, generate_images]`；目标项目已有 `tasks/ping.py`，S5 新增 `tasks/generate.py` 并把 `generate_images` 并入 `TASKS`。worker 启动命令见 §8。

### 5.2 进度事件 `events.py`

Redis pub/sub，channel = `run:{run_id}`：

```python
async def publish(run_id, payload): ...      # json.dumps 后 publish
@asynccontextmanager
async def subscribe(run_id):
    # 返回 messages() 生成器；空闲 IDLE_TICK=15s 产 None → 供 SSE 发心跳
```

### 5.3 服务层 `services/runs.py`

| 函数 | 职责 |
|---|---|
| `create` | 落库（stage="等待开始"）→ 提交 → 刷新 |
| `start` | RUNNING / progress 5 / "已开始" / `started_at=UTC now` |
| `report` | `progress = max(现值, 新值)` 单调推进 + 更新 stage |
| `finish` | 终态落定：成功 → 100/"已完成"；失败 → "已结束"；`finished_at` |
| `snapshot` | 面向 SSE 的轻量 dict（id/tool/status/progress/stage/error，**不含 candidates**） |
| `get`/`load` | `get` 按 user 隔离；`load` 只管 id（worker 用） |

每次状态变更统一走 `_commit` = commit + `events.publish(snapshot)`——**数据库与推送同生共死**，不会出现库里已终态、SSE 还挂着的情况。

### 5.4 生成服务 `services/generation.py`

```
execute(session, run)
├─ start(run)
├─ size_of(Ratio(run.params["ratio"]))
├─ GenerateRequest(prompt/width/height/count/negative/seed, references=加载参考图字节)
├─ provider.generate(request, on_progress=报告进度)
├─ report(90, "保存候选图")
├─ create_from_bytes × N → kind=GENERATED, source=GENERATE
└─ finish(SUCCEEDED, {"asset_ids": [...]})
```

三条异常路径：
- `ProviderError`（模型明确失败）→ FAILED + `str(exc)`
- 其他异常 → `rollback` + FAILED "生成失败，请重试"
- reference 图不存在 → 抛 `ProviderError("参考图不存在")`

### 5.5 Worker 任务 `tasks/generate.py`

```python
async def generate_images(ctx, run_id):
    async with SessionFactory() as session:
        run = await runs.load(session, run_id)   # 不存在 → return
        if run.status.is_terminal:               # 重投/重跑不二次扣费
            return
        try:
            await generation.execute(session, run)
        except Exception:
            # 兜底：任何遗漏异常必须落终态，否则订阅方永远空等
            await session.rollback()
            await runs.finish(session, run, status=FAILED, error="生成失败，请重试")
```

## 6. API / 路由

### 6.1 `routers/runs.py`（挂 `/api` 下）

| 方法 | 路径 | 行为 |
|---|---|---|
| POST | `/api/generations` | 先逐个校验 reference 图归属（任一不存在 → 404）→ `runs.create` → `enqueue("generate_images", run.id)` → 202 + `RunOut` |
| GET | `/api/runs/{run_id}` | 按 user 隔离取 run → `RunOut.of(run, _candidates(session, run))`（重新签名 URL） |

### 6.2 `routers/events.py`（挂 `/api` 之外）

```
GET /events/runs/{run_id}
├─ 鉴权 + runs.get（跨用户 404）
└─ stream():
    ├─ events.subscribe(run_id)          # 先订阅
    ├─ runs.get + yield snapshot         # 再读快照 —— 两步之间终态也不丢
    ├─ is_terminal → return              # 已终态：只发快照就断
    ├─ 空转 > 600s → return
    ├─ 空闲帧 → yield ": ping\n\n"
    └─ 数据帧 → yield f"data: {json}\n\n"；终态 → return
```

头：`Cache-Control: no-cache` + `X-Accel-Buffering: no`。**为什么不挂 `/api` 下**：SSE 需要反代单独关缓冲，prefix 独立便于运维分流。前端事件源用浏览器原生 `EventSource`。

### 6.3 `main.py` 变更

- `from app.queue import close_queue`；`from app.routers import assets, auth, events, health, runs`
- lifespan `yield` 后 `await close_queue()`
- `api.include_router(runs.router)`（在 `/api` 前缀下）
- `app.include_router(events.router)` + 注释"SSE 不挂在 /api 下，便于反向代理单独关闭缓冲"

### 6.4 配置

`config.py` 增加：

```python
# 可改为业务空间专属域名 https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com
dashscope_base_url: str = "https://dashscope.aliyuncs.com"
```

`.env.example` / `.env` 同步补 `DASHSCOPE_BASE_URL`。

## 7. 前端

### 7.1 API 层 `api/runs.ts`

```ts
export type Ratio = '1:1' | '4:5' | '3:4' | '9:16' | '16:9'
export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled'
export type Run = { id, tool, status, progress, stage, error, candidates: Asset[] }
export const RATIO_LABELS / isTerminal(status)
export const runsApi = { generate, get }
```

### 7.2 `hooks/useRun.ts` —— SSE + 快照双源合并

```ts
export function useGenerate()          // mutation → runsApi.generate
export function useRun(runId: string | null) {
  const [live, setLive] = useState<Progress | null>(null)   // SSE 实时
  const snapshot = useQuery({ queryKey: ['run', runId], ... }) // 快照+候选图
  useEffect(() => {
    const source = new EventSource(`/events/runs/${runId}`)
    source.onmessage = (e) => { setLive(JSON.parse(e.data)); isTerminal → close + invalidate }
    source.onerror = refresh           // 断线回退快照，不卡过期进度
    return () => source.close()
  }, [runId])
  // current = live?.id === runId ? live : null  ← 换任务后旧帧不串台
}
```

### 7.3 `GenerateForm.tsx`

受控表单：prompt / ratio（1:1 默认）/ count（4 默认）/ negative / advanced 折叠。Enter 提交判 `!event.shiftKey && !event.nativeEvent.isComposing`（中文输入法兼容）。工具类 `Segmented<T>` 泛型分段控件复用比例/数量。

### 7.4 `CandidatesPage.tsx`

```
useParams → runId → useRun(runId)
├─ notFound        → "任务不存在" + 回创作页
├─ failed/canceled → "生成失败" + error + "返回重试"链接
├─ 未终态          → Progress 组件（进度条 + stage + %）
└─ succeeded       → 候选网格：序号角标 / 点击选中 aria-pressed / 顶栏"进入编辑"
                     → navigate(`/editor?asset=${picked}`)
```

### 7.5 `CreatePage.tsx` 接入

- 顶部 `GenerateForm`（`defaultPrompt={readPromptDraft()}`，`onSubmit` → `useGenerate().mutate` → 成功清草稿 + `navigate('/candidates/{run.id}')`）
- 上传区收进"上传已有图片"小节；空态文案改"还没有素材，先描述画面或上传一张图片。"

### 7.6 路由 `App.tsx`

- `/editor`、`/batch` 提示改"功能开发中"（清掉过期里程碑编号文案）
- 新增 `/candidates/:runId`（在 WorkbenchLayout 内）
- 删 `/candidates` 与 `/marketing` 的顶层占位路由（marketing 提示也改"功能开发中"）

### 7.7 前端类型注意

`api/assets.ts` 的 `Asset` 类型必须含 `url`（既有 `AssetOut` 已带）与 `id`；`useRun` 的 `Progress` 是 `Pick<Run, ...>` 省略 `candidates`。

## 8. 验证

```bash
# 1) 迁移（在 backend/ 下，用项目 .venv）
uv run alembic upgrade head          # 建 tool_runs + timestamptz 变更

# 2) 单元/集成测试（需要 docker 起 postgres/redis/minio）
uv run pytest                          # 含新增 test_generation.py 12 例

# 3) 前端
cd frontend && npm run lint && npm run build

# 4) 端到端（需要 API+worker 在跑）
#    终端 A: cd backend && uv run uvicorn app.main:app --port 7302
#    终端 B: cd backend && uv run arq app.tasks.WorkerSettings --port 7302  # worker 起法见后
#    终端 C: uv run python scripts/e2e_generation.py   # 从参考 S5 移植
```

**worker 启动**：ARQ worker 通过 `app.tasks.WorkerSettings`（或 `worker.py`）暴露 `functions=TASKS`。参考项目 worker 启动方式在依赖 `arq` CLI：`arq app.tasks.WorkerSettings`。实现时确认目标项目的 worker 入口，缺则新建 `backend/worker.py` 定义 `arq` 可识别的 settings 对象。

## 9. 已知问题 / 后续清理

| 编号 | 描述 | 归属 |
|---|---|---|
| K1 | 任务不可取消（无 CANCELED 触发路径，状态机留有该值） | S6+ / 运营需求 |
| K2 | retention：`tool_runs` 无清理策略，长期运行会累积 | S10+ |
| K3 | mock 占位图构图简单（色块 + 序号），仅够链路验证 | 接真实模型自动替换 |
| K4 | SSE 单机 pub/sub，多实例部署需换 Redis Stream / 多播模式 | 横向扩展时 |
| K5 | `reference_asset_ids` 虽可传，前端生成表单暂未暴露参考图选择 | S9 编辑底座 |

## 10. 后续路线图

1. **S9 编辑**：`/editor?asset=` 接住候选图，真实编辑工具链。
2. **S10 导出**：`DELIVERY_RATIOS` 复用交付尺寸。
3. **真实模型上线**：置 `IMAGE_PROVIDER=dashscope` + key，链路零改动。
4. 后续工具（抠图/批量）复用 `ToolRun` 执行模型与 SSE。