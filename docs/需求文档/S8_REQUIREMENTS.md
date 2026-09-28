# S8 需求文档：用品牌图层标替换默认 favicon

> 项目：pic-retouch-agent（AI 修图智能体）
> 里程碑：S8 — 品牌 favicon
> 日期：2026-09-24
> 前置里程碑：S7（已完成）
> 后续里程碑：S9+（真实编辑等）

## 1. 背景与目标

浏览器标签页、收藏夹、移动端主屏幕目前显示的是脚手架默认的紫色 v 字图标，与 S4 定下的品牌视觉（ink 深底 + accent 折角图层符号）完全脱节。

S8 统一站外触点：

1. **favicon 品牌化**：SVG favicon 换成与 `BrandMark` 同源的品牌图层标（32×32，深底 + `#d9ff6e` 折角描边 + 圆点台标）。
2. **缩放兼容**：补 32×32 PNG（传统浏览器/favicon 缓存）与 apple-touch-icon PNG（iOS/Android 主屏幕）。
3. **组件对齐**：`BrandMark` 图标补上圆点，与 favicon 视觉一致。

## 2. 用户与场景

| 角色 | 场景 |
|---|---|
| 浏览器用户 | 标签页与收藏夹显示品牌图层标，一眼认出产品 |
| 移动端用户 | 把站点"添加到主屏幕"后得到同源图标（apple-touch-icon） |
| 品牌一致性 | 站内品牌标识、favicon、主屏幕图标三处同形 |

## 3. 功能需求

### 3.1 图标文件 F1

- **F1.1** `public/favicon.svg` 替换为品牌图层标：32×32 viewBox、`#171917` 深底盘 rx=8、居中折角方块（`#d9ff6e` 描边）+ L 形角标 + 圆点台标。
- **F1.2** 新增 `public/favicon-32.png`（32×32）与 `public/apple-touch-icon.png`（180×180 语义）两个二进制 PNG。

### 3.2 HTML 挂载 F2

- **F2.1** `index.html` 补 `<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png" />`。
- **F2.2** 补 `<link rel="apple-touch-icon" href="/apple-touch-icon.png" />`。

### 3.3 组件对齐 F3

- **F3.1** `BrandMark.tsx` 的 SVG 图标补 `<circle cx="15.5" cy="3.5" r="1.55" fill="currentColor" />`（圆点台标），与 favicon 同形。

## 4. 非功能需求

| 编号 | 类别 | 描述 |
|---|---|---|
| NFR1 | 兼容 | SVG（现代浏览器）+ PNG 32（传统缓存）+ apple-touch（移动主屏）覆盖主流触达 |
| NFR2 | 视觉一致 | favicon 与 `BrandMark` 共享同一图形语言（深底 + 折角方块 + 圆点） |

## 5. 验收标准

| 编号 | 描述 |
|---|---|
| AC1 | 浏览器标签页/收藏夹显示新品牌图层标，不再是紫色 v 字 |
| AC2 | `/favicon.svg`、`/favicon-32.png`、`/apple-touch-icon.png` 在 build 后可访问 |
| AC3 | `BrandMark` 图标出现圆点台标，与 favicon 同形 |
| AC4 | `npm run build`（含 `tsc -b`）+ lint 通过；后端测试不受影响 |

## 6. 范围与非范围

**本里程碑范围**：

- `public/favicon.svg` 替换、`public/favicon-32.png` / `public/apple-touch-icon.png` 新增
- `index.html` 两行 link
- `BrandMark.tsx` 一个圆点

**本里程碑非范围**：

- 任何后端 / 数据变更
- 深色主题适配（favicon 深底，适用当前浅色 + 深色主题）

## 7. 后续依赖

- 无。品牌图形语言已闭环（站内 + 站外 + 主屏幕同源），后续页面直接复用 `BrandMark`。