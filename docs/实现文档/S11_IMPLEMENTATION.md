# S11 实现文档：拆层成层、图层单独操作、素材库收拢

> 项目：pic-retouch-agent
> 里程碑：S11
> 日期：2026-09-29

## 1. 变更总览

对应参考项目 `ai-picture-editor` 的 `c85888b`（拆层成层）与 `07c558e`（修撤销连发与空历史、避免拆层把主体画回背景）两条提交。

本里程碑拆成八个提交，各自独立可回滚：

| # | 主题 | 内容 | 规模 |
|---|---|---|---|
| 1 | 图层文档模型 | `Layer` 字段扩展；`set_visible` / `move`；固定图层 id | 后端 3 文件 + 测试 |
| 2 | 拆层像素算子 | `edits/split.py`、`edits/ocr.py` | 后端 2 文件 + 测试 |
| 3 | 按图层寻址与读写 | `tools/target.py`；`retouch` / `region` / `enhance` 改造 | 后端 5 文件 |
| 4 | 拆层与成层工具 | `tools/layers.py`、工具注册、`ocr_provider` 配置 | 后端 4 文件 + 测试 |
| 5 | 空操作与素材库 | `apply_edit` 空操作短路；`GET /assets/library`；画布摘要与提示词 | 后端 6 文件 + 测试 |
| 6 | 画布图层交互 | 文字层、选中、拖动、缩放 | 前端 4 文件 |
| 7 | 面板与工具栏 | 缩略图、显隐、拆层成层确认、图片墙过滤 | 前端 4 文件 |
| 8 | 创作页素材库 | `AssetLibrary` 分组、撤销并发闸 | 前端 5 文件 |

无数据库迁移（`Layer` 新增字段只落在 `edit_sessions.document` 的 JSONB 里），无新增硬依赖（`cv2` / `rapidocr_onnxruntime` 均为可选导入）。

---

## 2. 提交 1：图层文档模型

### 2.1 固定图层 id

`backend/app/layers.py`：

```python
BASE_LAYER_ID = "base"
BACKGROUND_LAYER_ID = "background"
SUBJECT_LAYER_ID = "subject"
```

底图是会话创建时的唯一层，锁定。拆层后底图消失，取而代之的是锁定的背景层与可编辑的主体层。

### 2.2 Layer 新字段

```python
class Layer(BaseModel):
    ...
    source_hash: str | None = None   # 由哪份遮罩/蒙版产生，幂等判定用
    text: str | None = None          # 文字层内容
    font_size: float = 24
    fill: str = "#141414"
```

`source_hash` 是幂等的地基：`promote_object_to_layer` 用 `object-{遮罩哈希}` 当图层 id，用它判断「这个物体已经是独立图层了」；`split_layers` 把它记在主体层上，与 `already_split` 互为补充。

### 2.3 两个新的纯函数变换

`backend/app/edits/document.py`：

```python
def set_visible(document, layer_id, visible): ...   # 绝对显隐
def move(document, layer_id, *, x=None, y=None, dx=None, dy=None): ...
```

`move` 的 `x`/`y` 是绝对坐标、`dx`/`dy` 是相对位移，两者都可只给一个。与既有的 `scale`（`factor` 相对、`scale_x` 绝对）是同一套入参风格，模型不容易填错。

---

## 3. 提交 2：拆层像素算子

### 3.1 `backend/app/edits/split.py`

纯像素与纯文档两个层次的东西放在一个模块，因为它服务的目标很单一：把一张图拆成几张。

**像素层**：

| 函数 | 作用 |
|---|---|
| `alpha_mask(data)` | 把 PNG 的 alpha 通道做成可视化遮罩，供 `apply_masked` 等复用 |
| `mask_hash(mask)` | 对遮罩 luma 取 sha256 前 16 位，作为图层 id 与幂等键 |
| `cut_object(source, mask)` | 用遮罩裁出物体，返回 `(PNG, left, top, width, height)`；遮罩为空抛 `EmptyCut` |
| `expand_mask(mask, size)` | `MaxFilter` 膨胀主体轮廓，避免背景上残留一圈主体边缘 |
| `fill_background(source, mask)` | 挖掉遮罩覆盖的像素再补上，优先 OpenCV `inpaint`，无则模糊兜底 |
| `punch(source, mask, x=, y=)` | 把遮罩覆盖到的像素打成透明；`x`/`y` 是图层原点 |

`fill_background` 的兜底路径值得说明：

```python
def _blur_inpaint(image, luma):
    keep = ImageChops.invert(luma)
    ring = ImageChops.subtract(luma.filter(ImageFilter.MaxFilter(9)), luma)
    seed = Image.new("RGB", image.size, _mean_where(image, ring) or _mean_where(image, keep))
    seed.paste(image, mask=keep)
    patched = seed
    for radius in (24, 12, 5):
        patched = Image.composite(patched.filter(ImageFilter.GaussianBlur(radius)), patched, luma)
    return Image.composite(patched, image, luma)
```

先用空洞**外圈**的平均色铺一张底（外圈是完好的背景色，比整图平均色准得多），再由粗到细三次高斯模糊把色块抹匀，最后把原图按 `luma` 合成回去——洞外像素原样保留。

**文档层**：

- `split_document`：产出 `background` + `subject`（+ 文字层）。
- `as_background_and_object`：未拆层时直接提升选区，产出 `background` + `object-{hash}`。
- `promote_document`：已拆层时追加物体层，并按 `replacements` 把被改写过的图层换成新素材。
- `already_split` / `already_promoted`：幂等判定。

`already_split` 的判定有点绕：

```python
def already_split(document):
    ids = {layer.id for layer in document.layers}
    if BACKGROUND_LAYER_ID in ids and SUBJECT_LAYER_ID in ids:
        return True
    return BACKGROUND_LAYER_ID in ids and BASE_LAYER_ID not in ids
```

第一条是整图拆层的形态，第二条是「底图已被成层动作替换掉」的形态。两种都算已拆，不能再拆一次。

### 3.2 `backend/app/edits/ocr.py`

`rapidocr_onnxruntime` 是可选依赖，装不上就静默返回空列表（拆层退化成不拆文字）。配置项 `ocr_provider` 与既有的 `matting_provider` 同构：`auto` 有就用、没有就跳过，`none` 强制跳过，`rapidocr` 强制启用（装不上直接报错）。测试统一置 `none`。

---

## 4. 提交 3：按图层寻址与读写

### 4.1 `backend/app/tools/target.py`

把「对某一层做像素处理」这件事从四个工具里抽出来：

| 函数 | 作用 |
|---|---|
| `layer_image` | 取某层自己的素材字节，读素材仍走 `get_for_user` 做归属校验 |
| `write_layer_image` | 新建素材并写回该层 `asset_id`；仅当画布只剩一个图像层时额外返回 `adopt_asset_id` |
| `background_target` | 有背景层就返回背景层，否则退回默认目标层 |
| `layer_under_mask` | 选区覆盖到的最上层可见图像层；无交集退回默认层 |
| `mask_for_layer` | 画布坐标的遮罩换算成图层本地坐标；空则抛 `EmptyCut` |

`_single_image` 这个判断决定了行为差异：单图层画布上处理结果还要切成当前图（与 S10 行为一致），多层画布上**不能**——那会把整个多层结果压成一张底图。

### 4.2 四个工具的改造

```python
# retouch.py
layer = resolve_layer(document_of(record), run.params.get(_LAYER))
data = await layer_image(session, record, layer)
output = await asyncio.to_thread(remove_background, data)
return await write_layer_image(session, run, record, layer.id, output, AssetKind.SUBJECT)
```

`adjust_image` 顺带解决了一个 S10 遗留：原来靠 `flatten_session(background=TRANSPARENT)` 保透明通道，现在直接读图层自己的 PNG，透明通道天然就在，不需要再拍平。

`params = {key: value for key, value in run.params.items() if value and key != _LAYER}` —— `layer_id` 不是调色参数，必须排除。

```python
# region.py
layer = resolve_layer(...) if run.params.get("layer_id") else layer_under_mask(document, mask)
local_mask = mask_for_layer(mask, layer, (document.width, document.height))
source = await layer_image(session, record, layer)
output = apply_masked(source, edited, local_mask)
```

遮罩从画布坐标换到图层本地坐标这一步是按层局部编辑能成立的前提：遮罩是整张画布尺寸的，而图层可能只有物体那么大且带偏移。

```python
# enhance.py（换背景）
target = background_target(document)
source = await layer_image(...) if target.id == BACKGROUND_LAYER_ID else await flatten_session(...)
kind = AssetKind.BACKGROUND if target.id == BACKGROUND_LAYER_ID else AssetKind.GENERATED
return await write_layer_image(session, run, record, target.id, images[0], kind)
```

未拆层时保持原样（拍平 → 生成 → 切成当前图）；已拆层时只换背景层。

---

## 5. 提交 4：拆层与成层工具

### 5.1 修补背景的两步法

这是整批改动里最容易做错的一处。直接把「原图 + 提示词」丢给生成模型让它补背景，模型看到主体还在，就会顺手把主体一起重画一遍——拆完层一看，背景里又出现了一个主体。

`_fill_hole` 因此是三步：

```python
async def _fill_hole(session, run, source, mask):
    # 先挖空再填，模型只看到没有主体的图，避免又把主体画回背景
    hole = expand_mask(mask, Image.open(io.BytesIO(source)).size)
    prepared = await asyncio.to_thread(fill_background, source, hole)
    edited = (await get_image_provider().edit(
        EditRequest(prompt=_RECONSTRUCT, image=prepared),
        on_progress=lambda progress, stage: runs.report(session, run, progress, stage),
    ))[0]
    return apply_masked(prepared, edited, hole)
```

1. **外扩**：`expand_mask` 把主体轮廓膨胀 `max(8, min(size)//64)` 像素，否则背景上会留下一圈主体的边缘色。
2. **确定性修补**：`fill_background` 先用算法把洞填掉，得到一张确定不含主体的图 `prepared`。
3. **模型衔接**：模型只做「让这块补丁和周围景物自然衔接」，并且结果按 `hole` 遮罩合成回 `prepared`——**洞外一个像素都不会被模型改到**。

提示词同样关键：

```python
_RECONSTRUCT = (
    "画面中已有一块被修补过的区域。只把这块修补处修得和周围景物衔接自然，"
    "不要新增人物、动物或物体，也不要改变未修补的部分。"
)
```

不写「不要新增物体」，模型面对一块突兀的色块最容易做的就是补一个物体进去。

### 5.2 `split_layers`

```python
source   = await flatten_session(session, record)
subject  = await remove_background(source)
mask     = alpha_mask(subject)
background = await _fill_hole(session, run, source, mask)
texts    = await detect_text(source) if include_text else []
next_document = split_document(document, background_id=..., subject_id=..., texts=texts,
                               subject_hash=mask_hash(mask))
```

`mask` 直接复用抠图产物的 alpha 通道，不再单独算一次分割。`selections.clear(record.id)` 在拆层后清掉选区——画布已经变了，旧选区没有意义。

### 5.3 `promote_object_to_layer`

两条分支：

```python
if already_split(document):
    next_document, created = await _promote_onto_split(...)   # 背景层写补齐结果，其余层 punch
else:
    next_document = as_background_and_object(...)              # 底图直接换成背景层 + 物体层
```

`_promote_onto_split` 逐层处理图像层：背景层用 `apply_masked` 把修补结果贴回去，其余层用 `punch` 把选区打成透明（`x`/`y` 传各自 `transform` 原点）。不这么做的话，主体层仍然完整覆盖着那个物体，新物体层叠上去就是「同一个东西出现两次」。

### 5.4 幂等

```python
key = mask_hash(mask)
if already_promoted(document, key):
    return {"document": document.model_dump(mode="json")}
```

命中时直接返回，不落素材、不写历史——这跟提交 5 的空操作短路是同一条原则。

---

## 6. 提交 5：空操作与素材库

### 6.1 空操作不写历史

`apply_edit` 原来无条件做三件事：截断重做分支 → 改状态 → 追加历史。拆层上线后暴露了问题：`split_layers` 命中幂等时会返回**和当前完全相同**的文档，于是历史里凭空多一条一模一样的记录，重做分支也被清掉——用户按一次撤销，回到了一个看不出变化的画面，再也重做不回去。

改为先算出「有没有变」再决定要不要记账：

```python
added = await _attach(session, record, extra_assets)
if not changed and not added:
    await session.commit()
    await session.refresh(record)
    return record

await session.execute(delete(EditHistory).where(..., EditHistory.seq > record.history_seq))
record.current_asset_id = next_current
record.document = next_document
if bump_revision:
    record.revision += 1
```

**这里与参考实现有一处刻意分歧**：参考项目只看 `changed`，本项目加上 `added`。理由是文生图这类工具只往图墙丢候选、既不改画布也不换当前图（`record_result` 走的就是这条路），按参考写法这些产出不会进编辑记录，用户在「编辑记录」里看不到自己生成过什么——已有的 `test_results_join_the_wall_without_switching_current` 就是被这一点打掉的。判定标准应该是「这一轮有没有产生任何用户可见的东西」，而不是「画布数字有没有动」。

`_attach` 因此要返回新挂上的数量。素材先挂上去再判定，也是为了让「只产出候选」的工具走完整条记账路径。

### 6.2 撤销连发

前端 `useSessionTools` 加一个 `historyLock`：

```ts
const historyLock = useRef(false)
const unlockHistory = () => { historyLock.current = false }
// ...
const undo = useMutation({ ..., onSettled: unlockHistory })
const runHistory = (action) => {
  if (historyLock.current || busy) return
  historyLock.current = true
  action()
}
```

`useRef` 而不是 `useState`：它是闸门不是 UI 状态，不需要触发重渲染。`onSettled` 而不是 `onSuccess`——失败的撤销也得放开，否则一次 409 就把撤销永久锁死。

快捷键侧补 `if (event.repeat || tools.busy) return`：按住 ⌘Z 会连续触发 `keydown`，`event.repeat` 为真时不响应。

`invoke` 里加 `useEditorUi.getState().setConfirming(null)`：二次确认按钮如果调别的工具，装甲状态要跟着清掉，否则下一次点别的按钮会直接执行。

### 6.3 素材库

`services/assets.py` 加 `library_for_user`：先取最近的会话，再一次性把它们的 `session_assets` 拉出来按会话分组，遮罩/主体/背景三类中间产物过滤掉，没进过会话的素材收成「未归入会话」一组。

```python
_WORKING = {AssetKind.MASK, AssetKind.SUBJECT, AssetKind.BACKGROUND}
```

`GET /api/assets/library` 返回 `LibraryGroupOut[]`（`session_id` 可空，为空即未归组）。前端 `CreatePage` 用它替换原来的平铺卡片墙，`AssetLibrary` 按组渲染封面 + 可展开的网格。

### 6.4 画布摘要与提示词

`describe()` 把图层数换成图层名列表，并补一条默认作用规则：

```python
names = [_layer_name(layer) for layer in document.layers]
parts = [
    f"画幅 {document.width}×{document.height}",
    f"图层 {len(document.layers)} 个（{'、'.join(names)}）",
    "未指定图层时，调色/去背/翻转/移动作用在最上层图像，换背景作用在背景层",
    ...
]
```

`_layer_name` 对文字层取文案前 8 个字，隐藏层加「·隐藏」后缀。

`graph.py` 的系统提示词同步补两条规则：已有选区时 `promote_object_to_layer` 可直接调用；拆层默认不拆文字。

---

## 7. 提交 6：画布图层交互

### 7.1 分层与选中

`DocumentLayer` 从「只渲染可见图像层、`listening={false}`」改成「渲染全部可见层、`listening={interactive}`」：

```tsx
const interactive = !selecting && !cropOpen && !compareOpen
```

`interactive` 为假时图层既不监听也不可拖，裁剪/对比/选区三种模式下不会误拖。

`useLayerInteract` 抽公共交互逻辑，图像层与文字层共用：

```tsx
const pick = () => {
  if (dragged.current) { dragged.current = false; return }  // 拖完松手不再触发一次选中
  onSelect?.(layer.id)
}
```

`onMouseDown` 里 `stage.draggable(false)`，让画布平移让位给图层拖动，`onMouseUp` / `onDragEnd` 里恢复。这就是 `stageDraggable` 之外还要一个 `holdingStage` 局部状态的原因——`Transformer` 变换期间同样要按住画布。

### 7.2 拖动与缩放

拖动结束写入绝对坐标，缩放结束写入绝对倍率，保留翻转方向：

```tsx
onDragEnd: (event) => {
  const next = { x: event.target.x() - layer.width / 2, y: event.target.y() - layer.height / 2 }
  if (Math.abs(next.x - layer.transform.x) < 0.5 && Math.abs(next.y - layer.transform.y) < 0.5) return
  setDrop(next)
  onMove?.(layer.id, next.x, next.y)
}
```

`drop` / `pinnedScale` 是**本地**的临时位置，文档回传后再撤：

```tsx
useEffect(() => {
  if (!drop) return
  if (Math.abs(layer.transform.x - drop.x) < 0.5 && Math.abs(layer.transform.y - drop.y) < 0.5) setDrop(null)
}, [layer.transform.x, layer.transform.y, drop])
```

`LayerPreview` 相应加上 `x` / `y`。`LayerScaler` 用 `viewScale` 反向补偿手柄尺寸，`boundBoxFunc` 把缩放夹在 0.1×–8×。

### 7.3 文字层

```tsx
<Text text={layer.text || layer.name} fontSize={layer.font_size ?? Math.max(12, layer.height * 0.72)}
      fill={layer.fill ?? '#141414'} align="center" verticalAlign="middle" ... />
```

文字层没有 `asset_id`，也走不进像素工具（`write_layer_image` 对非图像层直接报错）。

---

## 8. 提交 7：面板与工具栏

### 8.1 图层面板

- `LayerRow` 从「一整块按钮」拆成「缩略图 + 名称/副标题 + 显隐按钮」三块，缩略图取 `layer.asset_id` 对应的会话素材 URL。
- 新增 `LayerAction`（拆层 / 成层），与工具栏的 `ConfirmTool` 同一套「先武装再确认」：`confirming === id` 时按钮文案变成确认词。
- 勾选框 `splitIncludeText` 决定 `include_text`。
- 调色与局部替换面板的 `onApply` 带上 `layer_id: selectedLayerId`。

`LayerControls` 里撤预览的时机从「文档一变就撤」改成「文档追上预览才撤」：

```tsx
if (preview.id !== layer.id) return
const same = (preview.x === undefined || Math.abs(preview.x - layer.transform.x) < 0.5) && ...
if (same) setLayerPreview(null)
```

原来的写法会在切换选中图层、回写中途把图层「拽回原位」一下再跳到新位置。

### 8.2 图片墙过滤

```tsx
assets.filter((asset) => asset.kind !== 'mask')
       .filter((asset) => asset.id === currentId ||
                          (asset.kind !== 'subject' && asset.kind !== 'background'))
```

当前图永远显示，其余遮罩和拆层中间产物不上墙——它们由图层面板承载。

---

## 9. 提交 8：创作页素材库

`AssetLibrary` 只负责渲染分组：封面 + 标题 + 张数/时间，可展开成网格。点封面：有 `session_id` 就跳编辑器，没有就用封面新建会话。

```tsx
const openGroup = () => {
  if (group.session_id) onOpenSession(group.session_id)
  else onOpenAsset(group.cover.id)
}
```

---

## 10. 测试

### 10.1 单元测试（`tests/test_edits.py`）

| 用例 | 断言 |
|---|---|
| `test_visible_is_absolute` | `set_visible` 切换后再设回来 |
| `test_move_accepts_absolute_and_relative` | `dx/dy` 相对、`x/y` 绝对 |
| `test_cut_object_keeps_only_masked_pixels` | 裁切框等于遮罩包围盒，保留原色 |
| `test_fill_background_replaces_masked_subject` | 洞内颜色不再是主体色且更靠近背景色；洞外不变 |
| `test_punch_clears_masked_pixels_and_keeps_the_rest` | 洞内 alpha=0，洞外不变 |
| `test_split_document_is_background_subject_and_text` | 层 id 顺序、文案、`already_split` / `already_promoted` |
| `test_mask_hash_is_stable_for_the_same_selection` | 同遮罩哈希稳定 |

### 10.2 接口测试（`tests/test_tools.py`）

| 用例 | 断言 |
|---|---|
| `test_set_layer_visible_hides_and_shows` | 显隐往返 |
| `test_noop_edit_does_not_append_history` | 修订号仍为 1，`can_undo` 为 False，历史只有 `create_session` |
| `test_noop_edit_keeps_redo_branch` | 空操作后 `can_redo` 仍为 True，重做能回放 |
| `test_split_layers_replaces_base_with_subject_and_background` | 前两层为 `background`/`subject`，无 `text-`，当前图不变；重复执行不写第二条历史 |
| `test_promote_object_creates_a_layer_and_is_idempotent` | 出现 `object-` 层、选区清空、重复提升层数不变 |
| `test_move_layer_shifts_position` | `transform.x/y` 变化 |
| `test_replace_background_after_split_keeps_subject` | 主体层 `asset_id` 不变、背景层变化、当前图不变 |
| `test_adjust_after_split_only_changes_the_target_layer` | 只有指定层 `asset_id` 变化 |

### 10.3 素材库测试（`tests/test_assets.py`）

`test_library_groups_assets_by_session_and_hides_masks`：分组标题顺序为 `['主图', '未归入会话']`，未归组素材在内，且任何分组里都不出现 `mask`。

---

## 11. 与参考实现的差异

| 点 | 参考项目 | 本项目 | 原因 |
|---|---|---|---|
| `apply_edit` 空操作判定 | 只看 `changed` | `changed` 且无新素材 | 文生图只上墙时也要进编辑记录，参考写法会把它当空操作吞掉 |
| `AdjustIn` 过滤参数 | `if value and key != _LAYER` | 同 | — |
| 调色取图 | `layer_image` | 同 | 按层取图后不再需要 `flatten(TRANSPARENT)` |
| `punch` 的 `x/y` | `int(round(x))` | 同 | — |
| 素材库过滤集合 | `MASK/SUBJECT/BACKGROUND` | 同 | — |
