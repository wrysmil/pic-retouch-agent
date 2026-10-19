# Toookens 生图接入（qwen-image-2.0 / 3.0）

> 项目：pic-retouch-agent
> 主题：把 Toookens 的 `/v1/images` 生图接进「模型配置 → 运行版本」体系
> 日期：2026-10-19

## 0. 一句话概括

Toookens 的生图接口长得像 OpenAI Images，但**不是**：它用 `operation_mode` 区分文生图/图生图而不是换端点，用异步任务返回结果，并且对尺寸有模型级硬约束。所以它单列一个 adapter —— `app/providers/toookens.py`，其余部分（登记、发布、热更新、按任务锁版本）完全复用既有的模型配置体系，没有新增一套配置通道。

## 1. 为什么不直接复用已有的 adapter

| | `openai_image` | `dashscope` | `toookens`（本文） |
|---|---|---|---|
| 端点 | `/images/generations` + `/images/edits` | 两个不同 path | 统一 `/images/generations` |
| 图生图 | 另走 multipart `/images/edits` | `input.messages` 里塞 base64 | 同端点 + `operation_mode=image_to_image` |
| 参考图传递 | multipart 文件 | base64 data URL | data URL（实测上游接受） |
| 结果形态 | 同步 200 | 异步任务 + 轮询 | **两种都有**，按模型不同 |
| 尺寸约束 | 无校验 | 编辑端点限 512–2048 | 模型级白名单 + 自定义尺寸约束 |

关键差异是最后一行。`qwen-image-2.0` 的 `supports_custom_size=false`、`supported_sizes=["1024x1024"]`，而项目按 1:1 / 4:5 / 9:16 出图（1080×1080、1080×1350、1920×1080）。**如果直接把 1080×1350 透传过去，上游返回 `invalid_image_size`，整轮生成失败。** 尺寸收敛因此必须在 adapter 内完成，不能指望调用方。

## 2. 协议要点（已实测确认）

基线 `https://api.toookens.com/v1`，鉴权 `Authorization: Bearer <key>`。

### 2.1 提交

`POST /images/generations`，常用字段：

| 字段 | 说明 |
|---|---|
| `model` | 模型名，如 `qwen-image-3.0` |
| `prompt` | 提示词 |
| `size` | `1024x1024`；受模型能力约束 |
| `n` | 成品图数量 |
| `response_format` | 建议 `url` |
| `operation_mode` | `text_to_image` / `image_to_image` / `multi_reference_image` |
| `image` | 单参考图，`image_to_image` 用 |
| `reference_images` | 多参考图数组 |

### 2.2 两种成功形态都要处理

- **同步**：HTTP 200，图片在 `data[].url` / `data[].b64_json`，或 `output.image_urls`。
- **异步**：HTTP 202，带 `task_id` / `task_query_url` / `poll_after_seconds`；轮询 `GET /images/tasks/{task_id}`，`status` 为 `queued` / `dispatching` / `running` 时继续，`succeeded` 时读 `output.image_urls`，`failed` / `cancelled` 取 `error_message`。

实测 `qwen-image-3.0` 走的是**异步**路径（202 → 轮询约 15–50s 出图），所以轮询不是可选分支。

### 2.3 参考图可以直接内联

文档写的是「参考图片 URL」，但实测 `image` 与 `reference_images` 都接受 `data:image/png;base64,...`。这一点很重要：本地 MinIO 的签名 URL 在开发环境是 `localhost`，厂商根本访问不到，而内联 data URL 让参考图链路不依赖公网可达性。

## 3. 代码落点

```
app/providers/toookens.py        # 本文主角：协议适配 + 尺寸收敛 + 任务轮询
app/providers/base.py            # 既有 Protocol，未改动
      ↑
app/services/model_runtime.py    # _build_image_provider 新增 TOOOKENS 分支
      ↑
app/models/model_config.py       # AdapterType.TOOOKENS
app/schemas/admin_config.py      # 后台入参校验放宽到 toookens
frontend/src/pages/AdminModelsPage.tsx   # 适配器下拉项

scripts/register_toookens.py     # 一次性登记脚本（不发起厂商调用）
```

`param_schema` 这次终于被用起来了：`_build_image_provider` 把 `ModelDefinition.param_schema` 传给 adapter，adapter 据此知道该模型的尺寸与操作模式能力。**能力声明是数据不是代码**，厂商调整后改 schema 即可，不用改 adapter。

## 4. 能力声明与尺寸收敛

`param_schema` 里认这些键（取自模型详情接口的 `image_size_capabilities` / `supported_operation_modes`）：

```json
{
  "supported_sizes": ["1024x1024", "1536x1024", "1024x1536", "2048x2048"],
  "default_size": "auto",
  "supports_custom_size": true,
  "custom_size_constraints": {
    "minimum_pixels": 262144,
    "maximum_pixels": 4194304,
    "aspect_ratio_min": 0.125,
    "aspect_ratio_max": 8.0
  },
  "supported_operation_modes": ["text_to_image", "image_to_image", "multi_reference_image"],
  "supports_multi_reference_image": true
}
```

`_Capabilities.resolve_size()` 的收敛顺序：

1. 请求尺寸命中 `supported_sizes` → 原样使用。
2. 允许自定义且满足像素/比例约束 → 原样使用（`qwen-image-3.0` 的 1080×1350 走这条）。
3. 不允许自定义 → 在 `supported_sizes` 里挑**比例最接近**的；没有同比例就退回默认尺寸（`qwen-image-2.0` 走这条，收敛到 1024×1024）。
4. 允许自定义但超约束 → 按原比例把像素量夹到上下限内。

schema 留空时按「不限制」处理，请求尺寸直接透传，与其它 adapter 行为一致。

参考图数量也据能力分流：多图且 `supports_multi_reference_image=true` 用 `multi_reference_image`；否则**只取第一张**走 `image_to_image`，而不是报错让整轮失败。

## 5. 登记与发布

模型配置仍然只走「连接 → 模型 → 运行版本」三步，脚本只是把重复劳动固化下来：

```bash
cd backend
python scripts/register_toookens.py --text-model-slug <已登记的文本模型 slug>
```

脚本做的事：登记 slug 为 `toookens-main` 的连接（`adapter_type=toookens`，base URL `https://api.toookens.com/v1`）→ 登记 `qwen-image-3.0`（启用）与 `qwen-image-2.0`（停用备用）→ 给了文本模型就发布运行版本。**幂等**，重复跑只会补齐缺的项。密钥读 `.env` 的 `TOOOKENS_API_KEY`，不落在脚本里。

发布前需要有文本模型；只登记生图模型时项目仍处于「尚未发布运行配置」，这是预期状态。

另外别忘了白名单：`ALLOWED_PROVIDER_HOSTS` 必须含 `api.toookens.com`，否则后台保存连接时会被 `validate_provider_url` 拒掉。

### 5.1 注意：跑后端测试会清空模型配置

`tests/conftest.py` 的 session 级 fixture 在开跑时会把**整张** `model_connections` /
`model_definitions` / `runtime_config_versions` 清掉，再发布一份 mock 运行配置——而它读写的是
`.env` 里那同一个开发库。所以：

- 跑完 `pytest` 之后，这里登记的 Toookens 连接与模型都会被删掉，需要重跑一次注册脚本；
- 反过来，先登记再跑测试，下次打开后台会发现配置没了，这不是注册脚本的问题。

根治办法是把测试指向独立数据库，或让 fixture 只清理自己造的 `test_*` 行而不是全表清空。
当前未改，属于既有行为，这里只做记录。

## 6. 费用与验证

- **登记与本地单测不产生费用**：`tests/test_toookens.py` 全部走 `httpx.MockTransport`，不联网。
- **真实调用按张计费**：qwen-image-3.0 按输出像素档位计价（1K 档约 0.144 元/张，见返回体的 `estimated_billing`）。连通性测试请在确有必要时再点。
- 接入时实测覆盖了四条路径：文生图、`image_to_image`（data URL）、`multi_reference_image`（2 张）、自定义尺寸 1080×1350，均返回 `succeeded`。

## 7. 已知限制

1. `qwen-image-2.0` 固定 1024×1024，项目其它比例会被收敛成 1:1，**画面比例因此与用户所选投放比例不一致**。要按比例出图请用 `qwen-image-3.0`（本仓库默认启用）。
2. 适配器只实现了「生成/编辑/放大」，没有接任务取消（`POST /images/tasks/{id}/cancel`）与 `image_variation`、`image_edit_with_mask` 两个操作模式——项目侧暂无调用场景。
3. 结果 URL 是上游签名地址且会过期，必须立即转存；`generation.py` 既有的转存步骤已经覆盖这一点。
4. 下载结果图时用的是**不带鉴权头**的独立 client，避免把 API Key 泄露给结果 CDN 域名。
