# S8 实现文档：用品牌图层标替换默认 favicon

> 项目：pic-retouch-agent
> 里程碑：S8
> 日期：2026-09-24

## 1. 仓库状态变化

| 提交 | 内容 |
|---|---|
| S1–S7（已存在） | 脚手架 / 基础设施 / 账号体系 / 素材上传 / 品牌化 / 文生图链路 / 测试清理 / 启动入口 |
| **S8（本里程碑）** | 品牌 favicon 替换 + 缩放 PNG + `BrandMark` 圆点对齐 |

纯前端、无依赖变更。5 个文件（3 文本 + 2 二进制）。

## 2. 变更详情

### 2.1 `frontend/public/favicon.svg`（替换）

从默认紫色 R 字图标换成与 `BrandMark` 同源的品牌图层标：

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none">
  <rect width="32" height="32" rx="8" fill="#171917"/>
  <g transform="translate(4 4)">
    <rect x="3.5" y="3.5" width="12" height="12" rx="3.5" stroke="#d9ff6e" stroke-width="2"/>
    <path d="M8.5 20.5H17A3.5 3.5 0 0 0 20.5 17V8.5" stroke="#d9ff6e" stroke-width="2" stroke-linecap="round"/>
    <circle cx="15.5" cy="3.5" r="1.55" fill="#d9ff6e"/>
  </g>
</svg>
```

深底盘 `#171917`（品牌 ink）+ accent 折角方块 + L 形角标 + 圆点台标。32×32 保证小尺寸标签页可辨。

### 2.2 二进制 PNG（从参考 S8 提交导出）

- `frontend/public/favicon-32.png`（657 字节，32×32）——传统浏览器 / favicon 缓存
- `frontend/public/apple-touch-icon.png`（2899 字节）——iOS/Android 添加到主屏幕

### 2.3 `frontend/index.html`

```html
<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" />
```

### 2.4 `frontend/src/components/BrandMark.tsx`

SVG 图标内补一个圆点（`currentColor`，随名称文字色）：

```tsx
<circle cx="15.5" cy="3.5" r="1.55" fill="currentColor" />
```

## 3. 关键决策与理由

| 决策 | 理由 |
|---|---|
| SVG + PNG32 + apple-touch 三件套 | 现代浏览器走矢量；部分传统解析/缓存只认 PNG；移动主屏幕必须 apple-touch |
| favicon 深底 + 浅色描边 | 深色小图标在暗色标签页下仍清晰；`BrandMark` 组件用 `currentColor` 主题自适应 |
| 图形与 `BrandMark` 完全同源 | 站内 / 标签页 / 主屏幕三处同形，品牌记忆统一 |

## 4. 验证

```bash
cd frontend
npm run lint && npm run build      # dist 下产出 favicon.svg / favicon-32.png / apple-touch-icon.png
python -m http.server / 用 dev server 打开 → 标签页显示品牌图层标
```

## 5. 后续清理

无遗留。品牌图形语言闭环，后续页面复用 `BrandMark` 即自动一致。