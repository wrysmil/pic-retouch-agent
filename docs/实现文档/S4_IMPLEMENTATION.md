# S4 实现文档：落地页拆组件、统一视觉规范

> 项目：pic-retouch-agent
> 里程碑：S4
> 日期：2026-09-23

## 1. 仓库状态变化

| 提交 | 内容 |
|---|---|
| S1–S3（已存在） | 脚手架 / 基础设施 / 账号体系 / 素材上传 |
| **S4（本里程碑）** | 落地页拆 8 个区块组件 + `BrandMark` 品牌标识 + 视觉令牌扩展 + `promptDraft` 草稿 + AuthPage/WorkbenchLayout 品牌化 |

零新增依赖、零后端变更。

## 2. 前端文件变化

### 2.1 新增文件

| 文件 | 职责 |
|---|---|
| [src/components/BrandMark.tsx](frontend/src/components/BrandMark.tsx) | 品牌标识：ink 底 + accent 折角方块 SVG；`sm`/`md` 两档；children 为可选文字 |
| [src/components/landing/LandingHeader.tsx](frontend/src/components/landing/LandingHeader.tsx) | 吸顶页头：品牌链接 + 按登录态切换的右侧入口 |
| [src/components/landing/LandingHero.tsx](frontend/src/components/landing/LandingHero.tsx) | 首屏：光晕 + 网格 + 徽章 + 标题高亮 + `PromptComposer` + 场景 chip + 事实 + 分批入场 |
| [src/components/landing/PromptComposer.tsx](frontend/src/components/landing/PromptComposer.tsx) | 受控输入面板：Enter 提交 / Shift+Enter 换行 / 中文合成 `isComposing` 判断；附件与提交按钮 |
| [src/components/landing/CapabilityShowcase.tsx](frontend/src/components/landing/CapabilityShowcase.tsx) | 四张能力卡（数据驱动 `CAPABILITIES` 数组 + `previews` 示意图） |
| [src/components/landing/previews.tsx](frontend/src/components/landing/previews.tsx) | 四个 CSS 拼贴示意图：`CandidatesPreview` / `SelectionPreview` / `LayersPreview` / `ExportsPreview` |
| [src/components/landing/DeliverySteps.tsx](frontend/src/components/landing/DeliverySteps.tsx) | 交付四步：横排（桌面）/ 纵排（移动端） |
| [src/components/landing/StartBanner.tsx](frontend/src/components/landing/StartBanner.tsx) | 深色 CTA 横幅：径向高光 + 按登录态跳转 |
| [src/components/landing/LandingFooter.tsx](frontend/src/components/landing/LandingFooter.tsx) | 页脚：品牌 + 产品说明 |
| [src/lib/promptDraft.ts](frontend/src/lib/promptDraft.ts) | sessionStorage 草稿读写：`savePromptDraft` / `readPromptDraft`，隐私模式静默降级 |

### 2.2 修改文件

| 文件 | 变更 |
|---|---|
| [src/pages/LandingPage.tsx](frontend/src/pages/LandingPage.tsx) | 由单文件大页改为区块组装：Header + Hero + Capabilities + Steps + Banner + Footer；`start()` 写草稿 + `navigate` |
| [src/pages/AuthPage.tsx](frontend/src/pages/AuthPage.tsx) | 卡入 `rounded-panel` + `shadow-panel`；加 `BrandMark` 与 `bg-glow`；注册标题改"创建账号"；输入圆角改令牌 |
| [src/layouts/WorkbenchLayout.tsx](frontend/src/layouts/WorkbenchLayout.tsx) | 品牌区换 `BrandMark size="sm"`；名称改"AI 修图智能体" |
| [src/index.css](frontend/src/index.css) | 令牌：`--radius-panel: 26px`、`--shadow-lift`、`--shadow-panel`、`--animate-rise` + `@keyframes rise`；`@utility bg-glow`、`@utility bg-grid`；`prefers-reduced-motion` 关闭动画 |

### 2.3 组件树

```
LandingPage
├─ LandingHeader         account: string | null
│   └─ BrandMark
├─ LandingHero           initialPrompt / submitLabel / onStart
│   ├─ PromptComposer    value / onChange / onSubmit / onAttach / submitLabel / placeholder / inputRef
│   └─ 场景 chip ×5 → pick(prompt)
├─ CapabilityShowcase    CAPABILITIES[×4] {title, desc, preview}
│   └─ previews.{Candidates,Selection,Layers,Exports}
├─ DeliverySteps         STEPS[×4]
├─ StartBanner           label / to
└─ LandingFooter
    └─ BrandMark

AuthPage / WorkbenchLayout ── BrandMark（复用）
```

### 2.4 关键决策与理由

| 决策 | 理由 |
|---|---|
| `PromptComposer` 为受控受假组件，不关心提交去向 | Hero 只负责采集与跳转，S5 接真实文生图时 `onStart` 换成发起生成即可，面板零改动 |
| `Enter` 提交判 `event.nativeEvent.isComposing` | 中文输入法候选框里按 Enter 是选词，不应触发提交 |
| 高亮"可上架"用 `absolute` 块 `top:[14%] bottom:[8%] -skew-x-6` | CJK 字身占满字框，超高块覆盖整个字高才像马克笔而非删除线（视觉细节） |
| `previews.tsx` 全样式拼贴、`aria-hidden` | 零图片请求、随主题自适应；示意图是装饰，不给读屏噪音 |
| 部分比例如 `-top-1`、`bg-ink/12` 直接内联穿透 | Tailwind v4 对任意微调值内联可读，不强行抽令牌（全局设计令牌只存语义关键值） |
| `lead` CTA 文案按登录态 | 未登录去注册（`/auth`），登录直接进工作台（`/create`），减少一步 |
| Hero 容器 `max-w-4xl` + 子元素自行收窄 | 让 14 字标题在桌面端稳定单行，输入面板/正文按需更窄 |
| 动画批量 `style={{ animationDelay: '40ms' }}` 递增 | 逐区块上浮的电梯感；配合 `both` 填充回退，延迟期元素保持透明不闪 |
| 令牌存全局、示意色内联 | 颜色体系（ink/brand/accent）是设计契约存令牌；示意图里的装饰渐变是插图不是契约 |

### 2.5 视觉令牌扩展（index.css）

```css
--radius-panel: 26px;
--shadow-lift: 0 20px 46px -18px rgb(20 26 20 / 0.18);
--shadow-panel: 0 28px 72px -26px rgb(20 26 20 / 0.3);
--animate-rise: rise 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
/* @keyframes rise { from { opacity: 0; transform: translate3d(0, 14px, 0) } to { opacity: 1; transform: none } } */

@utility bg-glow { 双径向渐变光晕 }
@utility bg-grid { 56px 网格 + mask 下淡出 }
```

## 3. 状态管理

| 状态 | 位置 | 来源 |
|---|---|---|
| 需求草稿 | `sessionStorage['retouch:prompt-draft']` | Hero 提交写入、LandingPage 初始值回填 |
| 场景 chip 选中 | Hero 内 `useState(prompt)` | 点选覆盖 + 聚焦输入框 |
| 当前用户 | react-query `['auth', 'me']`（既有） | LandingHeader / StartBanner 做登录态分支 |

## 4. 完成度矩阵（S4 增量）

| 模块 | 状态 |
|---|---|
| `BrandMark` + 三处接入 | ✓ 完成 |
| `LandingHeader` / `LandingFooter` | ✓ 完成 |
| `LandingHero` + `PromptComposer` + 场景 chip | ✓ 完成 |
| `CapabilityShowcase` + `previews`（四个示意图） | ✓ 完成 |
| `DeliverySteps` / `StartBanner` | ✓ 完成 |
| `promptDraft`（sessionStorage 草稿） | ✓ 完成 |
| 视觉令牌（panel/lift/shadows/rise/glow/grid/reduced-motion） | ✓ 完成 |
| AuthPage / WorkbenchLayout 品牌化 | ✓ 完成 |
| `tsc -b` + `oxlint` 通过 | ✓ 完成 |

## 5. 验证步骤

```bash
cd frontend
npm run lint          # oxlint 全绿
npm run build         # tsc -b + vite build 通过

# 手工（前后端 dev 状态）
# 未登录访问 / → Hero + 能力卡 + 步骤 + CTA + 页脚完整；
# 输入一句话 → 点"免费开始" → /auth；回 / 草稿回填；
# 已登录访问 / → CTA 为"进入工作台"，点击进 /create；
# 点场景 chip → 输入框填充；能力卡 hover 上浮；
# 登录页出现品牌 + 大面板；注册标题为"创建账号"；
# 工作台首栏为 BrandMark 图标 + "AI 修图智能体"。
```

## 6. 已知问题 / 后续清理

| 编号 | 描述 | 归属 |
|---|---|---|
| K1 | 草稿存本地 `sessionStorage`，换标签/清缓存即丢 | 可接受——草稿本意是"本页不重打" |
| K2 | Hero 的提交目前只跳转，不触发任何生成请求 | S5 接文生图时替换 `onStart` 实现 |
| K3 | `previews.tsx` 的装饰色为内联硬编码，不含在主题令牌内 | 有意为之（插图非契约）；若改浅色主题需单独适配 |
| K4 | 动效仅 CSS，无 JS 视差 | 保持纯粹，后续如需再引入 |

## 7. 后续路线图

1. **S5+ 编辑**：Hero 输入面板接真实文生图（`onStart` → 生成 API）；`/create` 成为候选选择页
2. **S10 导出**：能力卡"物料包交付"示意图呼应真实导出产物
3. 任何新页面直接复用 `BrandMark` 与区块组件，视觉自动一致