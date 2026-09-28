# S4 需求文档：落地页拆组件、统一视觉规范

> 项目：pic-retouch-agent（AI 修图智能体）
> 里程碑：S4 — 落地页组件化 + 品牌视觉规范
> 日期：2026-09-23
> 前置里程碑：S1、S2、S3（已完成）
> 后续里程碑：S5+（编辑、导出、批量）

## 1. 背景与目标

S2 / S3 的落地页是在一个 `LandingPage.tsx` 里手写整页，能力卡只有文字没有示意图；登录页、工作台各自实现了一套品牌字样（字母 R 图标），视觉上不统一。S4 做一次纯前端的重构与规范化：

1. **拆组件**：把单文件落地页拆成可复用的区块组件（Hero、能力卡、步骤、CTA、页脚）。
2. **统一视觉**：抽出 `BrandMark`（品牌标识）供落地页 / 登录页 / 工作台共用一处；补齐全站圆角与阴影令牌（`radius-panel`、`shadow-lift`、`shadow-panel`）。
3. **强化转化**：Hero 加入需求输入面板 + 场景示例 + 分批入场动画；能力卡配 CSS 拼贴示意图；CTA 收尾；未登录的用户把需求草稿带到登录页。

**为什么这一里程碑独立**：全部是前端、零后端 API 变更，可与 S3 并行开发；落地页是买家第一屏，"像样的产品页"决定转化质量。

## 2. 用户与场景

| 角色 | 场景 |
|---|---|
| 首次访问者 | 看到产品定位 → 输入一句需求 → 点"提交" → 去注册 |
| 回访未登录者 | 上次输入的草稿在同一个标签页回填，不用重打 |
| 已登录用户 | 落地页任意 CTA 直接进工作台 |
| 运营/设计师 | 在能力卡上"看得见"四种能力的界面示意 |

## 3. 功能需求

### 3.1 品牌标识 F1

- **F1.1** 新增 `BrandMark` 组件：ink 底 + accent 描边图层符号（`L` 形折角方块），带 `sm` / `md` 两档尺寸，children 为可选文字。
- **F1.2** 落地页头部、页脚、登录页卡片、工作台侧边栏首部统一使用 `BrandMark`（替换原有的 `R` 字母块）。
- **F1.3** 工作台名称统一为"AI 修图智能体"（替换原"修图智能体"）。

### 3.2 落地页 Hero F2

- **F2.1** 顶部氛围：光晕（`bg-glow`）+ 下淡出网格（`bg-grid`）。
- **F2.2** 徽章（"面向电商运营与内容创作者"）、14 字标题（"一句话，交付**可上架**的商品物料"，高亮"可上架"）、副文案。
- **F2.3** 需求输入面板 `PromptComposer`：受控 textarea，Enter 提交、Shift+Enter 换行、支持中文输入法合成（`isComposing` 判断）；附带"上传商品图"按钮与提交按钮。
- **F2.4** 5 个场景示例 chip：商品主图 / 场景氛围图 / 模特上身 / 促销海报 / 多尺寸物料，点击填充到输入框。
- **F2.5** 3 条事实（无需设计经验 / 支持 JPG·PNG·WebP / 1:1·4:5·9:16 一次导出）。
- **F2.6** 各区块按 40ms 间隔分批上浮入场（`animate-rise`）；`prefers-reduced-motion` 下动画关闭。

### 3.3 能力展示 F3

- **F3.1** 四张能力卡，每张配一个**纯 CSS 拼贴的界面示意图**（不依赖图片资源）：
  1. 一句话生成 → 四宫格候选，其中一张选中打勾
  2. 主体级编辑 → 选区框 + 虚线 + 悬浮指令标签
  3. 语义图层 → 三行图层列表（文字/主体/背景，缩进 + 渐变色块）
  4. 物料包交付 → 1:1 / 4:5 / 9:16 三个比例缩略图
- **F3.2** 卡片 hover 提亮（`shadow-lift`）。

### 3.4 交付四步 F4

- **F4.1** 描述需求 → 挑选方向 → 局部精修 → 导出物料，四步横排（桌面）/ 纵排（移动端）。

### 3.5 首屏 CTA + 页脚 F5

- **F5.1** 深色收尾横幅 `StartBanner`："把商品图交给智能体"，按钮按登录态跳 `/create` 或 `/auth`。
- **F5.2** 页脚 `LandingFooter`：品牌标识 + 一行产品说明。
- **F5.3** 顶部 `LandingHeader`：左侧品牌（链接回首页）；右侧已登录显示 `{用户名} · 进入工作台`，未登录显示"登录"。

### 3.6 需求草稿 F6

- **F6.1** 落地页提交时把输入框文本写入 `sessionStorage`（键 `retouch:prompt-draft`）。
- **F6.2** 落地页初始值从同键回填（同标签页内刷新不丢）。
- **F6.3** 隐私模式下 storage 不可写时静默跳过，不影响主流程。

### 3.7 登录页视觉统一 F7

- **F7.1** 登录 / 注册卡包装进 `rounded-panel` + 大阴影面板；左上品牌标识。
- **F7.2** 页面上方复用 `bg-glow`。
- **F7.3** 注册模式标题由"注册"改为"创建账号"；输入圆角统一为 `rounded-control`。

## 4. 非功能需求

| 编号 | 类别 | 描述 |
|---|---|---|
| NFR1 | 可访问 | 示意图全部 `aria-hidden`（装饰性）；键盘焦点样式沿用 `:focus-visible` 令牌 |
| NFR2 | 可访问 | `prefers-reduced-motion: reduce` 时动画 / 过渡时长压到 0.01ms |
| NFR3 | 一致 | 设计令牌集中定义在 `@theme`（颜色、圆角、阴影、动画），组件不写死新颜色值 |
| NFR4 | 可测 | 纯前端变更，无 API 变化；构建（`tsc -b`）+ lint 通过即可 |
| NFR5 | 性能 | 示意图全部 CSS/SVG 拼贴，零图片请求 |

## 5. 视觉令牌（新增）

| 令牌 | 值 | 用途 |
|---|---|---|
| `--radius-panel` | `26px` | 大面板（登录卡、提交面板、横幅） |
| `--shadow-lift` | `0 20px 46px -18px rgb(20 26 20/0.18)` | 能力卡 hover 上浮 |
| `--shadow-panel` | `0 28px 72px -26px rgb(20 26 20/0.3)` | 登录卡 / 输入面板 |
| `--animate-rise` | `rise 0.7s cubic-bezier(.22,1,.36,1) both` | 入场动画（含 `@keyframes rise`） |
| `.bg-glow` | 双径向渐变光晕 | Hero / 登录页顶部氛围 |
| `.bg-grid` | 1px 网格 + 下淡出 mask | Hero 背景底纹 |

组件用到的既有令牌：`text-ink` / `text-muted` / `text-faint` / `border-line` / `border-line-strong` / `bg-paper` / `bg-ink` / `bg-soft` / `bg-canvas` / `bg-accent` / `bg-brand` / `bg-brand-soft` / `text-brand-strong` / `text-white` / `shadow-control` / `rounded-card` / `rounded-control`。

## 6. 技术约束

纯前端重构，零新增 npm 依赖。沿用：React 19 + react-router v7 + @tanstack/react-query + Tailwind v4（`@utility` 定义 `bg-glow` / `bg-grid`）。

## 7. 验收标准

| 编号 | 描述 |
|---|---|
| AC1 | `/` 显示组件化落地页：页头（品牌 + 登录/进入工作台）、Hero（标题高亮 + 输入面板 + 5 场景 chip + 3 事实）、四张带示意图的能力卡、四步流程、深色 CTA 横幅、页脚 |
| AC2 | 输入一句话 → 点提交 → 未登录跳 `/auth`；该草稿在回跳 `/` 后回填 |
| AC3 | 已登录访问 `/` → 输入面板提交按钮与 CTA 均为"进入工作台"，点击直接进 `/create` |
| AC4 | 点任一场景 chip → 输入框填充对应文案 |
| AC5 | 登录页显示品牌标识 + 大面板卡片；注册模式标题为"创建账号" |
| AC6 | 侧边栏统一使用 `BrandMark` 图标与"AI 修图智能体"名称 |
| AC7 | 能力卡 hover 出现上浮阴影；`prefers-reduced-motion` 下无动画 |
| AC8 | `npm run build`（含 `tsc -b`）通过；`npm run lint` 通过 |
| AC9 | 后端（S3 已合入）`pytest` 全绿，前端改动未触碰后端 |

## 8. 范围与非范围

**本里程碑范围**：

- `BrandMark` 组件 + 三处接入（落地页、登录页、工作台）
- `landing/` 七个区块组件（Hero / PromptComposer / CapabilityShowcase / previews / DeliverySteps / StartBanner / LandingHeader / LandingFooter）+ `previews.tsx` 示意图
- `promptDraft.ts` sessionStorage 草稿
- 视觉令牌：`radius-panel`、`shadow-lift`、`shadow-panel`、`animate-rise`、`bg-glow`、`bg-grid`、reduced-motion 关闭动画
- AuthPage / WorkbenchLayout 品牌化

**本里程碑非范围**：

- 任何后端 / API / 数据库变更
- 真实文生图接入（落地页输入面板只做采集与跳转，不做生成请求）
- 素材上传的真实链路（S3 已完成）
- 深色主题
- 多语言 / i18n
- 图片预加载与懒加载策略（首屏无图片，天然轻量）

## 9. 后续依赖

- **S5+ 编辑**：Hero 输入面板的"提交"将成为真实文生图入口（对接 S3 后的生成 API），届时 `onStart(prompt)` 从 `navigate` 改为发起生成请求
- **S10 导出**：能力卡"物料包交付"示意图将呼应真实的多尺寸导出产物
- 后续任何需要品牌标识的页面直接复用 `BrandMark`，视觉自动一致