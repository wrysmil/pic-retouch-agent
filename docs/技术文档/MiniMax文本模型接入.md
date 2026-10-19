# MiniMax 文本模型接入（M3.1-Flash）

> 项目：pic-retouch-agent
> 主题：把 MiniMax 的 `/v1/chat/completions` 接进「模型配置 → 运行版本」的文本槽位
> 日期：2026-10-19

## 0. 一句话概括

MiniMax 提供 OpenAI 兼容接口，所以文本槽位不需要新的客户端实现——真正要处理的是它的**三个厂商默认行为**：思考强制开启（关掉会 400）、思考深度默认 `max`（交互式规划太慢）、以及把思考内容内联进 `content`（会污染给用户看的规划正文）。这三件事收敛在 `model_runtime` 的一小段参数拼装里，其余全部复用既有体系。

## 1. 接入参数

| 字段 | 值 |
| --- | --- |
| `base_url` | `https://api.minimax.cn/v1` |
| 端点 | `POST /v1/chat/completions` |
| `model` | `MiniMax-M3.1-Flash`（备用 `MiniMax-M3`） |
| 鉴权 | `Authorization: Bearer <key>` |

订阅 Key（`sk-cp-` 开头，来自「订阅管理 → M Plan」）与按量付费 Key 走**同一个** base_url，实测可用。注意订阅 Key 可以在有额度之前就存在，所以「key 有效」不等于「额度可用」。

## 2. 为什么这套接口和本项目的规划器特别契合

MiniMax 文档反复强调一条约束：多轮 Function Call 时必须把**完整的 assistant 消息（含 `reasoning_content`）**回传，否则思维链会断。这条约束对很多 Agent 框架是个坑（LangChain 默认不会保留 `reasoning_content`），但对本项目**不适用**：

`app/agent/graph.py` 的 `_plan` 每次只发两条全新消息（System + Human），注释写得很明确——「每次都是全新的两条消息，不带历史，模型对上一轮无记忆」。工具是由项目自己执行并推进的，不存在把工具结果喂回模型的多轮对话。所以「回传 reasoning」这条约束在这里没有落点，不需要为它写适配代码。

## 3. 三个厂商差异怎么处理

### 3.1 思考不能关，但可以调浅

`MiniMax-M3.1-Flash` 强制开启 thinking，传 `thinking: {"type": "disabled"}` 或 `reasoning_effort: "none"` 直接 **400**：

```text
model "MiniMax-M3.1-Flash" requires adaptive thinking; thinking.type="disabled"
(including reasoning.effort=none) is not allowed (2013)
```

所以适配层**只下发合法档位**：`param_schema.reasoning_effort` 不在 `low/medium/high/xhigh/max` 里就整体不下发，交给厂商默认，绝不把 `none` 或空值送出去。

更进一步：厂商对 M3.1-Flash 的默认档是 `max`。对「选工具 + 填参数」这种交互式规划，`max` 的思考开销换不来等比例的收益，注册脚本默认写 `medium`，可用 `--reasoning-effort` 调整。

### 3.2 思考内容会内联进 content

不拆分时，思考以 `<think>` 标签留在 `content` 里；而 `graph.py` 的 `_text_of(message)` 会把它当成规划正文直接显示给用户。因此适配层固定发 `reasoning_split: true`，让思考走独立的 `reasoning_content`，`content` 只剩最终回答。

### 3.3 base_url 两种写法都要认

管理员可能填域名（`https://api.minimax.cn`），也可能把文档里的完整 POST 地址整段粘进来（`.../v1/chat/completions`）。ChatOpenAI 只认到版本路径，多一段少一段都会 404，所以 `_resolve_minimax_base` 做归一化：去掉尾段 `/chat/completions`，路径为空则补 `/v1`。

## 4. 代码落点

```
app/services/model_runtime.py    # _resolve_minimax_base / _planner_options / 生图槽位拒收
app/models/model_config.py       # AdapterType.MINIMAX
app/schemas/admin_config.py      # 后台入参接受 minimax
frontend/src/api/adminConfig.ts  # AdapterType 联合类型（漏了会 tsc 报错）
frontend/src/pages/AdminModelsPage.tsx

scripts/register_minimax.py      # 一次性登记（不发起厂商调用）
tests/test_minimax.py            # 离线单测：协议参数拼装 + 后台入参
```

`_planner_options(adapter, param_schema)` 是这次唯一新增的行为分支，其它 adapter 拿到的仍是空 dict，行为不变（有单测钉住）。

## 5. 实测结论

两轮真实调用都在接入时跑通，共约 1000 token：

1. **裸 HTTP**：`reasoning_effort=low` + `reasoning_split=true` + 一个工具定义 → HTTP 200，`finish_reason=tool_calls`，工具参数是合法 JSON，`content` 干净无 `<think>`。
2. **完整 langchain 链路**：按 `_build_planner` 的构造方式（`temperature=0` + 上一步选项）建 `ChatOpenAI`，用 `bind_tools` 绑全部项目工具后 `ainvoke` → HTTP 200，`msg.tool_calls` 被正确解析成 `{name, args, id}`，正是 `_plan()` 消费的结构。

要点：**`temperature=0` 被接受**（MiniMax 允许 `[0,2]`），所以 `_build_planner` 里那个全局的 `temperature=0` 不必为 MiniMax 特判。

> 质量提示：`low` 档下模型对「把背景换成纯白色」选了 `split_layers` 而不是 `replace_background`。当时用的是简化版系统提示词，不代表项目真实提示词下的表现，但说明**档位调太低会影响工具选择**；默认给 `medium` 就是这个原因。

## 6. 登记与发布

```bash
cd backend
python scripts/register_minimax.py --image-model-slug qwen-image-3.0
```

脚本登记 `minimax-main` 连接 → `MiniMax-M3.1-Flash`（启用）/ `MiniMax-M3`（停用备用）→ 若给了生图模型就发布运行版本。幂等，只读写本地库，**不产生费用**。密钥读 `.env` 的 `MINIMAX_API_KEY`。

白名单同样要放行：`ALLOWED_PROVIDER_HOSTS` 需含 `api.minimax.cn`。

## 7. 注意

1. **跑后端测试会清空模型配置**，包括这里登记的连接与运行版本（原因见 [Toookens 生图接入](Toookens生图接入.md) 第 5.1 节）。跑完测试要重跑两个注册脚本。`tests/test_minimax.py` 是纯函数用例，可以加 `--noconftest` 避免清库。
2. 模型 slug 用了 `MiniMax-M3.1-Flash`（含大写与点），绕过了后台 `^[a-z0-9_\-]+$` 的 slug 规则——脚本直接调服务层所以能落库，但**这个 slug 无法通过后台界面再次创建或编辑**。`qwen-image-3.0` 同样如此。纯展示层面无影响，要统一规范的话两个脚本一起改。
3. MiniMax 只承担文本槽位；绑到生图槽位会被明确拒绝（`minimax 适配器只支持文本模型…`），而不是抛出含糊的「不支持的 adapter」。
