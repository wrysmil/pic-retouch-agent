/** 用文字与颜色共同标记 AI 操作，低对比度或禁用状态下也能辨认。 */
export default function AiBadge() {
  return (
    <span className="border-ai-line bg-ai-soft text-ai-ink inline-flex shrink-0 items-center rounded-[4px] border px-1 py-px text-[10px] leading-none font-semibold tracking-wide">
      AI
    </span>
  )
}
