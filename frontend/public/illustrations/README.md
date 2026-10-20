# 映造：展示插画与商品示例图

来源：2026-10-21 使用内置 ImageGen 生成。图片为 AI 生成的展示素材，不是当前后端模型的实测输出。无外部图库链接，不依赖远程图片服务。

- `studio-companion.webp`：960 × 960，23,704 字节；首页、登录页、创作页共用。
- `product-scenes.webp`：1024 × 1024，60,456 字节；同一陶瓷杯的四种摄影场景，CSS 按四宫格切换背景坐标。
- `product-mug.webp`：512 × 512，8,226 字节；从四宫格右上角切出，用于尺寸预览，object-contain 保留完整商品。

原始输出保存在 Codex generated_images 中；项目使用以上 WebP。切图与压缩用于前端资源导出，未修改图片内容。

## 小助手生成提示词

Use case: stylized-concept. Asset type: original decorative illustration for a premium AI photo retouching web app. Create a single refined 3D editorial still life on a perfectly plain warm ivory background (#f8f9f5). A small friendly anthropomorphic camera/photo editing assistant in matte cream ceramic, with a teal blue-green lens and two tiny expressive dark eyes, short rounded feet and one tiny arm holding a lime-green magic editing wand. Beside it two overlapping rounded rectangular blank photo frames with miniature abstract pastel landscape shapes (soft blue sky, green hills, pale peach sun). One small floating lime sparkle. Minimal, sculptural, sophisticated, charming rather than childish, no busy scene. Entire subject centered and fully visible with generous empty margins, grounded soft ambient contact shadows, gentle studio lighting, high quality tactile matte 3D render. Palette cream, muted teal, sage and a restrained lime accent matching a calm creative tool. Square composition. No text, no letters, no logos, no watermark, no interface, no background scenery.

## 商品摄影生成提示词

Use case: product-mockup. Asset type: a photographic 2-by-2 contact sheet used as a web image sprite for four AI product photography examples. Create ONE square image divided into EXACTLY FOUR EQUALLY SIZED SQUARE PHOTOGRAPHS in a perfect 2x2 grid, no gutters, no borders, no text. Every square shows the SAME beautiful small off-white ceramic coffee mug with a thick gently curved pale sage green handle, smooth matte glaze and subtly rounded body, no logo, no writing. The product must be fully visible, modest sized, centered in each square with sufficient empty space around it. TOP LEFT photograph: mug on warm ivory seamless studio backdrop and stone plinth, soft natural side light, calm premium product advertising. TOP RIGHT: same mug in sage green minimalist studio with pale green geometric pedestal and a soft shadow, still neutral off-white mug with sage handle. BOTTOM LEFT: same mug on a soft beige linen tabletop next to window, warm morning light and small soft plant shadow, very restrained. BOTTOM RIGHT: same mug on pale peach sand-color studio surface with subtle arch-shaped sunlight. Photorealistic professional commercial product photography, convincing ceramic texture, clean editorial compositions, elegant calm muted colors, consistent product shape across all four images. Absolutely no lettering, no labels, no watermarks, no people, no UI, no icons. Ensure the 4 cells meet precisely at the central horizontal and vertical lines.
