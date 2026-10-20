export default function CanvasHint({
  mode,
  text,
}: {
  mode: string
  text: string | null
}) {
  if (!text) return null

  return (
    <p
      // 按模式换 key：切模式重播入场动画，同一模式内刷新百分比不打断
      key={mode}
      className="bg-shell/90 border-shell-line animate-pop pointer-events-none absolute top-3 left-1/2 z-10 flex -translate-x-1/2 items-center gap-1.5 rounded-full border px-3 py-1 text-[10px] whitespace-nowrap text-shell-ink backdrop-blur"
    >
      <span className="bg-ai size-1.5 rounded-full" aria-hidden />
      {text}
    </p>
  )
}
