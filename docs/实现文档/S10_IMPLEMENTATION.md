# S10 实现文档：像素链路修正、交互跟手化、生成工具扩展、区域编辑

> 项目：pic-retouch-agent
> 里程碑：S10
> 日期：2026-09-28

## 1. 变更总览

本里程碑拆成五个提交，各自独立可回滚：

| # | 主题 | 内容 | 规模 |
|---|---|---|---|
| 1 | 拍平保留透明通道 | `flatten` 支持指定底色；调色走透明底并逐通道处理 | 后端 4 文件 + 测试 + 前端 1 文件 |
| 2 | 修图交互跟手化 | 缓动缩放、滚轮语义、视口锚定、实时预览、裁剪跟手、画布内对比、Toast | 前端 24 文件 |
| 3 | effect 返回值白屏 | 副作用回调改块体；错误态与加载态合并判断 | 前端 3 文件 |
| 4 | 换背景/扩图/超分 | 图像服务加 `edit`/`upscale` 能力；三个新工具 + 两个面板 | 后端 7 文件 + 测试 + 前端 6 文件 |
| 5 | 点选/笔刷选区与局部编辑 | 遮罩与分割模块、选区服务与接口、`erase_region`/`replace_region` | 后端 11 文件 + 测试 + 前端 10 文件 |

无数据库迁移，无新增依赖（`numpy` 经 `rembg` 间接引入，测试环境已有）。

---

## 2. 提交 1：拍平保留透明通道

### 2.1 问题

像素工具只认一张图，执行前要 `flatten` 拍平多层画布。原来 `flatten` 硬编码白底：

```python
canvas = Image.new("RGBA", (document.width, document.height), (255, 255, 255, 255))
```

去背景的产物是透明 PNG。经它拍平后透明区域被压成不透明白色，`adjust` 再怎么调，底图已经不是原来那张了。

### 2.2 改动

**`backend/app/edits/render.py`** — 底色变成参数，导出两个常量：

```python
WHITE = (255, 255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)

def flatten(document, images, *, background: tuple[int, int, int, int] = WHITE) -> bytes:
    canvas = Image.new("RGBA", (document.width, document.height), background)
    ...
```

**`backend/app/tools/context.py`** — `flatten_session` 透传同一个关键字参数，默认仍是 `WHITE`，调用方不传时行为不变。

**`backend/app/tools/retouch.py`** — 只有 `adjust_image_exec` 传 `TRANSPARENT`：

```python
data = await flatten_session(session, record, background=TRANSPARENT)
```

去背景仍用默认白底：抠图需要看清完整画面，透明底会让四角采样拿不到背景色。

**`backend/app/edits/pixels.py`** — 两处调整：

1. `image.convert("RGB")` 改为 `split()` + `merge()`，显式按通道拿 alpha，避免依赖转换函数的隐式行为。
2. 晕影从 `ImageOps.multiply` 换成 `ImageChops.multiply`。前者是按比例混合两张图（`blend` 语义），暗角会被糊成一片灰；后者才是逐像素相乘。

**`frontend/src/components/editor/LayerPanel.tsx`** — 调色「应用」后 `setValues({})`，否则同一组参数会被反复叠加。

### 2.3 测试

`backend/tests/test_edits.py` 新增 3 例：

| 用例 | 断言 |
|---|---|
| `test_adjust_preserves_transparent_pixels` | 透明像素 alpha 仍为 0；可见像素被调整后 R 通道 > 0 |
| `test_adjust_vignette_darkens_corners` | 四角 R < 中心 R |
| `test_flatten_can_keep_transparent_background` | `background=TRANSPARENT` 时空白区 alpha=0、主体区 alpha=255 |

---

## 3. 提交 2：修图交互跟手化

### 3.1 视图手感 `stores/canvasView.ts`

把「视图观察状态」拆成两类操作：

| 类别 | 方法 | 行为 |
|---|---|---|
| 手势 | `zoomBy` / `panBy` / `pan` | 直接 `set`，无插值 |
| 按钮 | `fit` / `stepZoom` / `zoomTo` | 走 `glide()` 缓动 |

```ts
const GLIDE_MS = 260
const easeOut = (p: number) => 1 - (1 - p) ** 3

function glide(apply, from, to) {
  stopGlide()
  const start = performance.now()
  const tick = (now) => {
    const ratio = easeOut(Math.min(1, (now - start) / GLIDE_MS))
    apply({ scale: ..., x: ..., y: ... })
    frame = ratio < 1 ? requestAnimationFrame(tick) : 0
  }
  frame = requestAnimationFrame(tick)
}
```

`frame` 是模块级单例，任何手势操作先 `stopGlide()`，避免缓动与手势互相打架。

**滚轮灵敏度**是这批改动里最实际的一处。触控板捏合每帧 delta 只有 2–10，鼠标滚轮一格 100+。原来统一走 `ZOOM_STEP` 固定倍率，两者手感差一个量级。改为：

```ts
const WHEEL_CAP = 50
const WHEEL_GAIN = 0.0035

zoomByWheel(delta, anchor) {
  const capped = Math.max(-WHEEL_CAP, Math.min(WHEEL_CAP, delta))
  get().zoomBy(Math.exp(-capped * WHEEL_GAIN), anchor)
}
```

先夹住增量再取指数，两种设备的手感就对齐了。`ZOOM_STEP` 顺带从 1.2 提到 1.25。

**视口锚定**解决面板开合跳位：`setViewport` 检测到尺寸变化时，把位移按差值的一半补偿。

```ts
setViewport: (next) => {
  const { viewport, x, y } = get()
  const grown = { width: next.width - viewport.width, height: next.height - viewport.height }
  if (!viewport.width || !viewport.height || (!grown.width && !grown.height)) {
    set({ viewport: next }); return
  }
  set({ viewport: next, x: x + grown.width / 2, y: y + grown.height / 2 })
}
```

`fit` 增加 `options.animate`：首次落位直接 `set`（避免进页面时画面从左上角飞进来），后续画幅变化才缓动。

### 3.2 调色实时预览

**`frontend/src/lib/adjustPreview.ts`** — 与后端 `pixels.adjust` 对齐的前端实现。

`PREVIEW_KEYS` 只收九项逐像素运算（亮度、对比度、饱和度、高光、阴影、色温、色调、自然饱和度、晕影）。锐化与清晰度是卷积，单帧算不动，明确留给「应用」时后端处理。

性能上做了两件事：

- **查表**：亮度与对比度只与单通道取值有关，预先算 256 项 LUT，替代逐像素算术。对比度以整图平均灰度为轴心，所以只在 `contrast != 0` 时才扫一遍求均值。
- **缓存**：`KonvaImage` 需要 `node.cache()` 才能跑 `filters`。缓存按 `pixelRatio: 0.6` 做——屏幕量级足够，且滤镜每帧重算才跟得上滑杆。

```ts
// 数值不变时保持数组同一引用，平移缩放才不会白白重算滤镜
const filters = useMemo(
  () => (filtered && color ? [makeAdjustFilter(color)] : NO_FILTERS),
  [filtered, color],
)
```

**跨域降级**在 `useCanvasImage`：先按 `crossOrigin='anonymous'` 加载（位图可读像素），失败则退回普通加载。`CanvasImage` 带 `safe` 标记，`ImageLayer` 只在 `safe === true` 时才挂滤镜——读不到像素时 `getImageData` 会抛 `SecurityError`。

```ts
element.onerror = () => { if (!cancelled && safe) load(false) }
```

### 3.3 画布交互 `components/editor/CanvasStage.tsx`

- **滚轮语义**：`ctrlKey/metaKey` 为缩放，否则平移。
- **首次落位不动画**：`fitted.current` 为空时 `fit(document, { animate: false })`。
- **裁剪跟手**：`onDragMove` / `onTransform` 期间就回写 rect，并把夹取结果写回 Konva 节点位置——夹取后若数值没变不会触发重渲染，节点会停在画布外。手柄、描边、虚线按 `1 / scale` 反向补偿。
- **对比分隔线**：`CompareDivider` 替代底部原生 `range`。手柄 `scaleX/Y = 1 / scale` 保持屏幕尺寸；拖动时直接取 `getRelativePointerPosition()`，绕开手柄自身反向缩放的换算。
- **store 选择器**：`useCanvasView()` 整体订阅改成逐字段 `useCanvasView(state => state.scale)`，避免任一字段变化都重渲整个画布。

### 3.4 提示与 Toast

- **`components/editor/CanvasHint.tsx`**：画布上方一行上下文提示，内容按「处理中 / 裁剪 / 对比 / 点选 / 笔刷」优先级分支。
- **`stores/toasts.ts` + `components/ToastHost.tsx`**：`push` 保留最近 3 条，3.2 秒后 `dismiss`；`dismiss` 先置 `leaving` 让退场动画播完（180ms）再从数组移除，避免动画中断。

### 3.5 其它

- `useElementSize`：尺寸未变时返回同一对象引用，杜绝 ResizeObserver 的无效重渲。
- `index.css`：新增 `--ease-soft`、`pop`/`fade-out`/`slide-in`/`fade-in` 四个关键帧；滑杆统一为细轨道 + 浮起滑块（WebKit 与 Firefox 两套伪元素）；`scrollbar-slim` 工具类弱化面板滚动条。
- `LayerPanel`：滑杆拖动中写 `layerPreview`，松手才 `invoke` 工具；切图层或关面板时清空。
- `EditorPage`：图层面板从右侧常驻栏改为画布内浮层，带 `animate-slide-in`。

---

## 4. 提交 3：effect 返回值白屏

### 4.1 问题

React 要求 effect 回调只能返回清理函数或 `undefined`，返回其它值会被 React 存为 `destroy`，下次 effect 重跑时调用它。

表达式体写法把回调的返回值直接交回 React，而返回值是否「无害」完全取决于被调函数当天返回什么：

```tsx
useEffect(() => end.current?.scrollIntoView({ block: 'end' }), [turns.length])
useEffect(() => setViewport(size), [size, setViewport])
```

第一处是真实故障：新版浏览器的 `Element.scrollIntoView()` 返回 `Promise`，React 把它当清理函数存下，下次重跑时调用 `Promise()` 抛 `TypeError`。异常发生在 `flushPassiveEffects` 中，且项目没有 ErrorBoundary，整棵 React 树被卸载，页面只剩 body 背景色——表现为「每次发完消息就白屏，刷新才恢复」。`turns.length` 从 0 变 1 只触发一次告警，从 1 变 2 才在 cleanup 阶段崩溃，所以首次进页面看起来是好的。

第二处当前无害（zustand 的 `set` 返回 `undefined`），但属于同一类隐患：调用方的返回值一旦变成非清理函数，症状与第一处完全相同。

### 4.2 改动

两处都改成块体、显式不返回值。`AgentConversation` 的那处已在 `3a457e9` 处理，本提交补上 `CanvasStage` 的同类改写。

### 4.3 顺带修的渲染分支

`EditorPage` 里两个早返回改成合并：

```tsx
if (!session) {
  return isError ? <Notice title="会话不存在" …/> : <Notice title="加载中" …/>
}
```

原来的写法是 `if (isError) return <会话不存在>`。撤销后触发 invalidate，后台刷新短暂失败会让 `isError` 为真而 `data` 仍有缓存——旧代码会把整个工作台换成整页提示，看起来就是白屏。合并后只有**确实没有数据**时才渲染占位。

---

## 5. 提交 4：换背景 / 扩图 / 超分

### 5.1 图像服务扩展 `providers/base.py`

`ImageProvider` 协议新增两个方法，`EditRequest` 是新的请求结构：

```python
@dataclass(frozen=True)
class EditRequest:
    prompt: str
    image: bytes
    count: int = 1
    width: int | None = None      # 有值时同时改画幅，用于扩图
    height: int | None = None
    negative_prompt: str | None = None

async def edit(self, request: EditRequest, on_progress=None) -> list[bytes]: ...
async def upscale(self, image: bytes, scale: int, on_progress=None) -> bytes: ...
```

`width`/`height` 选填是关键：换背景和局部编辑要保持原画幅，扩图要改画幅，同一个接口靠这两个字段区分。

### 5.2 DashScope 实现

- **编辑接口是同步的**，不支持 `X-DashScope-Async`，所以直接 `post` 等结果，超时放宽到 180s；文生图仍走异步任务 + 轮询。
- **边长约束**：编辑接口要求边长落在 `[512, 2048]`，`_fit_edit_size` 负责夹取——先按比例放大到最短边达标，再按长边比例缩回来，最后各边兜底不小于 512。
- **`upscale` 复用 `edit`**：算出目标尺寸后调 `edit` 并取第一张，省掉一套独立实现。
- `_submit` 改为接收 path，文生图与编辑共用提交逻辑。

### 5.3 占位实现 `providers/mock.py`

`edit` 用「同尺寸即换背景、异尺寸即扩图」区分：同尺寸把主体缩到 88% 居中，四周露出新底色，视觉上就是换背景；异尺寸按原大居中，四周是新增区域。构图由提示词哈希决定，同一提示词结果稳定。

`upscale` 直接 LANCZOS 放大。

### 5.4 画幅计算 `ratios.py`

```python
def cover_size(width: int, height: int, ratio: Ratio) -> tuple[int, int]:
    """刚好包住原图的目标比例画幅，扩图时主体不必被裁切。"""
```

与 `crop` 里的 `_fit_ratio` 是同一套几何的两种方向：`_fit_ratio` 往里切，`cover_size` 往外扩。

### 5.5 工具 `tools/enhance.py`

三个工具共用 `_store()`，差别只在「要不要自动采用」：

```python
result: dict = {"asset_ids": [...]}
if adopt_first and created:
    result["adopt_asset_id"] = str(created[0].id)
```

- `replace_background`：`count == 1` 自动采用，`count > 1` 只进图片墙。提示词自动加约束前缀「只替换背景，保持主体、光线和边缘不变」。
- `expand_canvas`：固定自动采用，进度文案提示「延伸画幅」。
- `upscale_image`：固定自动采用。

三者都 `session_required=True`、`queued=True`，与既有像素工具一致。

### 5.6 前端

`GenerateEdits.tsx` 放三个表单：`BackgroundForm`（描述 + 1/2/4 张）、`ExpandForm`（比例选择）、`ReplaceForm`（局部替换描述）。`LayerPanel` 的 `panel` 联合类型扩展出 `'background' | 'expand' | 'replace'`。

---

## 6. 提交 5：点选/笔刷选区与局部编辑

### 6.1 遮罩原语 `edits/mask.py`

四个纯函数，全部与业务无关：

| 函数 | 作用 |
|---|---|
| `to_luma(data, size)` | 任意格式遮罩 → L 通道图，可选缩放到目标尺寸 |
| `overlay_png(mask, color)` | L 遮罩 → 半透明着色 PNG，选区在画布上的可视化载体 |
| `rasterize_strokes(size, strokes, radius, base)` | 归一化笔迹 → L 遮罩，可基于已有遮罩叠加 |
| `union(left, right)` | 两张 L 遮罩取并集 |
| `apply_masked(source, edited, mask)` | 按遮罩把编辑结果合成回原图 |

`rasterize_strokes` 用 `draw.line(joint="curve")` 再逐点补圆点，保证笔迹拐角和端点不出缺口；笔刷直径按画布短边比例算，`radius` 因此是画布无关的相对量。

`apply_masked` 是「选区外一个像素都不动」的落点：

```python
luma = to_luma(mask, original.size).filter(ImageFilter.GaussianBlur(1.2))
return _png(Image.composite(result, original, luma))
```

遮罩先羽化再合成，否则选区边缘会出现硬锯齿。

### 6.2 点选分割 `edits/segment.py`

`segment_points(image, points)` 按归一化标点生成 L 遮罩。

- 优先走 SAM（rembg 自带 `sam` session，量化权重）：encoder 的 embedding 按图片内容哈希缓存（LRU，上限 4 张），同一张图连续点选只算一次 encoder。
- `matting_provider == "corner"` 或 SAM 不可用时，退回圆形并集——不下载模型也能跑通链路和测试。
- 两种路径最终都过 `overlay_png` 返回，保证下游拿到的格式一致。

坐标换算：`apply_coords` → 补齐齐次坐标 → 乘 `transform` 的转置 → decoder → `transform_masks` 还原到原图尺寸 → 取并集。

### 6.3 选区服务 `services/selections.py`

选区不进数据库。遮罩作为 `AssetKind.MASK` 素材落库，指针存 Redis：

```python
TTL = 24 * 3600
key = f"selection:{session_id}"
payload = {"revision": ..., "mask_asset_id": ..., "markers": [...]}
```

**修订号绑定**是这个设计的核心。`get()` 比对 payload 的 `revision` 与调用方传入的，不一致返回 `None`；写入时 `_guard()` 不一致抛 `StaleSelection`。画布一变（采用新图、裁剪、任何编辑都会 `revision += 1`），旧选区自动失效，两端都不需要额外的清理逻辑。

两条建立路径：

- `select_points` — `append=True` 时先读现有 markers 再追加，标点编号连续。
- `select_strokes` — 先读已有遮罩作 base，新笔迹 rasterize 后与 base 求并集，所以笔刷可以叠加。

`mask_bytes()` 供工具取遮罩：优先用调用方显式传的 `mask_asset_id`，否则取该会话当前修订号下的选区。

### 6.4 接口 `routers/sessions.py` + `schemas/session.py`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/sessions/{id}/selection` | `points` 或 `strokes` 二选一；空选区 422，选区过期 409 |
| GET | `/sessions/{id}/selection` | 当前修订号下的选区，无则返回 `null` |
| DELETE | `/sessions/{id}/selection` | 清除，204 |

`SelectIn` 里 `points` / `strokes` / `radius`（0.005–0.12）/ `append`；`SelectionOut` 返回 `revision`、`mask`（复用 `AssetOut`，带签名 URL）、`markers`。

### 6.5 局部工具 `tools/region.py`

`_edit_region` 是两个工具的公共外壳：

1. 校验 `revision`（显式传了就必须等于当前修订号）。
2. 取遮罩，取不到就报「请先点选或涂抹要修改的区域」。
3. 拍平画布 → `provider.edit()` → `apply_masked()` 合成 → 存素材并采用。
4. `selections.clear(record.id)`。

两个工具只在提示词上分叉，且都加约束前缀：

```python
# erase_region 无提示词时的默认指令
"移除选中物体，用周围背景自然填补，不要改变选区以外的画面。"

# replace_region
f"只改选中区域：{prompt}。选区外的主体、光线和背景必须保持原样。"
```

`mask_asset_id` 与 `revision` 都进 `agent_hidden`，模型看不到也不需要填。

### 6.6 Agent 感知

`services/agent.describe()` 的画布摘要追加选区状态：

```
已有选区，3 个标点 / 已有笔刷选区 / 当前无选区
```

`agent/graph.py` 的系统提示词同步加一条：摘要标明已有选区时可直接调用局部消除/替换，不要再让用户重选。

### 6.7 前端

- **`stores/editorUi.ts`** — `selectMode: 'point' | 'brush' | null`、`selection: CanvasSelection | null`、`dropStaleSelection(revision)`。裁剪 / 对比 / 选区三模式互斥，开任一自动关其余。
- **`hooks/useSelection.ts`** — 点选与笔刷两条 mutation；`addPoint` 在已有同修订号选区时带 `append: true`，实现连续点选累积。
- **`hooks/useSelectStroke.ts`** — 笔迹收集。`points` 用 ref（拖动过程不触发重渲），`draft` 用 state（只有这样才能在画布上实时画出草稿）。
- **`components/editor/SelectionOverlay.tsx`** — 遮罩半透明叠加、草稿笔画（圆头圆角）、标点编号徽标（`scaleX/Y = 1 / scale` 保持屏幕尺寸）。
- **`CanvasStage`** — 选区模式下光标变十字，禁用 Stage 拖拽；`canvasPoint()` 把指针位置转成归一化坐标，越界返回 `null`。
- **`EditorToolbar`** — 工具栏按模式分支渲染；选区模式下提供点选/笔刷/消除/替换/清除/完成，无选区时按钮禁用并在 `title` 说明原因。

---

## 7. 关键决策与理由

| 决策 | 理由 |
|---|---|
| 只有调色走透明底拍平 | 去背景要靠四角颜色采样铺满背景；模型编辑类工具需要看清完整画面。透明底只对「已经在透明图上做逐像素运算」这一种场景正确 |
| 晕影用 `ImageChops` 而非 `ImageOps` | 前者是逐像素相乘，后者按比例混合两张图。用错会得到灰蒙蒙的暗角而不是压暗 |
| 选区存 Redis 而非建表 | 选区是一次性输入，不是需要长期留存的领域数据。指针本身很小，遮罩走 `assets` 表，24 小时 TTL 自然回收 |
| 选区绑定 `revision` 而非显式失效 | `revision` 在任何画布变化时都会递增，选区自动失效，不需要在每个改动点挂清理逻辑，也不会漏 |
| 选区不进 `LayerDocument` | 画布文档是画布的几何权威；选区是「接下来这一次工具执行的输入」，混进去会让撤销快照语义变浑 |
| 预览只做九项逐像素运算 | 锐化/清晰度是卷积，单帧算不动。做一半的预览比不做更糟——用户会以为所见即所得 |
| 预览按 `pixelRatio: 0.6` 缓存 | 屏幕量级足够看清，且滤镜每帧重算才跟得上滑杆。按原图缓存会直接卡死 |
| 滚轮增量先夹住再取指数 | 触控板与鼠标的 delta 量级差一个数量级，不夹住就没法用同一套参数伺候两种设备 |
| 手势不插值、按钮才缓动 | 拖拽中插值会产生橡皮筋滞后；按钮点击是一次性跳变，插值反而更自然 |
| `useCanvasImage` 用 `safe` 标记降级 | `getImageData` 读不到跨域像素会抛 `SecurityError`。降级成「能看不能预览」远好过整个画布报错 |
| 选区坐标一律归一化 | 视图倍率是纯前端状态，存像素坐标会让选区与缩放状态耦合，跨缩放级别失效 |

## 8. 验证与验收对照

| 验收 | 验证方式 |
|---|---|
| AC1–AC3 | `pytest backend/tests/test_edits.py` — 透明像素保 alpha、晕影压暗四角、透明底拍平 |
| AC15–AC17 | `pytest backend/tests/test_tools.py` — 换背景多候选只进图墙、扩图比例、超分倍率 |
| AC19 / AC24 | `pytest backend/tests/test_tools.py`、`test_sessions.py` — 选区绑修订号、按用户隔离 |
| AC20 / AC21 | `test_masked_composite_keeps_pixels_outside_the_selection` |
| AC23 | `test_existing_selection_is_given_to_the_planner` |
| AC5–AC14、AC18、AC22 | 前端手动核对（手势、预览、裁剪、选区） |
| AC25 | `pytest -q`、`npm run build`、`npm run lint` |
