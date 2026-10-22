import { useEffect, useMemo, useRef, useState } from 'react'

import type { LayerDocument } from '@/api/sessions'
import { useCanvasView } from '@/stores/canvasView'
import { newGuide, useEditorUi, type Guide } from '@/stores/editorUi'

function readGuides(sessionId: string): Guide[] {
  try {
    const raw = localStorage.getItem(`guides:${sessionId}`)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (item): item is Guide =>
        item &&
        typeof item.id === 'string' &&
        (item.axis === 'x' || item.axis === 'y') &&
        Number.isFinite(item.position),
    )
  } catch {
    return []
  }
}

export default function EditorRulers({
  sessionId,
  document,
  enabled = true,
}: {
  sessionId: string
  document: LayerDocument
  enabled?: boolean
}) {
  const rootRef = useRef<HTMLDivElement>(null)
  const [loadedSession, setLoadedSession] = useState<string | null>(null)
  const [pointer, setPointer] = useState<{ x: number; y: number } | null>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })
  const scale = useCanvasView((state) => state.scale)
  const x = useCanvasView((state) => state.x)
  const y = useCanvasView((state) => state.y)
  const guides = useEditorUi((state) => state.guides)
  const setGuides = useEditorUi((state) => state.setGuides)
  const addGuide = useEditorUi((state) => state.addGuide)
  const updateGuide = useEditorUi((state) => state.updateGuide)
  const removeGuide = useEditorUi((state) => state.removeGuide)

  useEffect(() => {
    const root = rootRef.current
    if (!root) return
    const observer = new ResizeObserver(([entry]) => {
      setSize({ width: entry.contentRect.width, height: entry.contentRect.height })
    })
    observer.observe(root)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    setGuides(readGuides(sessionId))
    setLoadedSession(sessionId)
  }, [sessionId, setGuides])

  useEffect(() => {
    // 加载完成前不能回写，否则会把上一个会话的参考线存进新会话。
    if (loadedSession !== sessionId) return
    localStorage.setItem(`guides:${sessionId}`, JSON.stringify(guides))
  }, [guides, loadedSession, sessionId])

  const step = scale < 0.3 ? 500 : scale < 0.55 ? 200 : scale < 1 ? 100 : scale < 2 ? 50 : 10
  const ticks = useMemo(() => {
    const xs: number[] = []
    const ys: number[] = []
    for (let value = 0; value <= document.width; value += step) {
      const screen = x + value * scale
      if (screen >= 20 && screen <= size.width) xs.push(value)
    }
    for (let value = 0; value <= document.height; value += step) {
      const screen = y + value * scale
      if (screen >= 20 && screen <= size.height) ys.push(value)
    }
    return { xs, ys }
  }, [document.height, document.width, scale, size.height, size.width, step, x, y])

  const clamp = (axis: 'x' | 'y', value: number) =>
    Math.max(0, Math.min(axis === 'x' ? document.width : document.height, value))

  const positionFromClient = (axis: 'x' | 'y', clientX: number, clientY: number) => {
    const rect = rootRef.current?.getBoundingClientRect()
    if (!rect) return 0
    const raw =
      axis === 'x' ? (clientX - rect.left - x) / scale : (clientY - rect.top - y) / scale
    return clamp(axis, raw)
  }
  const positionFromEvent = (axis: 'x' | 'y', event: React.PointerEvent) =>
    positionFromClient(axis, event.clientX, event.clientY)

  const startFromRuler = (axis: 'x' | 'y', event: React.PointerEvent) => {
    const guide = newGuide(axis, positionFromEvent(axis, event))
    addGuide(guide)
    const move = (next: PointerEvent) =>
      updateGuide(guide.id, positionFromClient(axis, next.clientX, next.clientY))
    const up = (next: PointerEvent) => {
      const position = positionFromClient(axis, next.clientX, next.clientY)
      if (position <= 0 || position >= (axis === 'x' ? document.width : document.height)) {
        removeGuide(guide.id)
      }
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up, { once: true })
  }

  return (
    <div
      ref={rootRef}
      className={`editor-rulers pointer-events-none absolute inset-0 z-10 ${
        enabled ? '' : 'hidden'
      }`}
      onPointerMove={(event) => {
        const rect = rootRef.current?.getBoundingClientRect()
        if (!rect) return
        setPointer({
          x: Math.round((event.clientX - rect.left - x) / scale),
          y: Math.round((event.clientY - rect.top - y) / scale),
        })
      }}
      onPointerLeave={() => setPointer(null)}
    >
      <div
        className="bg-paper/95 border-line pointer-events-auto absolute top-0 right-0 left-5 h-5 cursor-row-resize border-b"
        onPointerDown={(event) => startFromRuler('y', event)}
      >
        {ticks.xs.map((value) => (
          <span
            key={value}
            className="text-faint absolute top-0 h-full border-l border-current pl-1 text-[9px] leading-5"
            style={{ left: x + value * scale }}
          >
            {value}
          </span>
        ))}
      </div>
      <div
        className="bg-paper/95 border-line pointer-events-auto absolute top-5 bottom-0 left-0 w-5 cursor-col-resize border-r"
        onPointerDown={(event) => startFromRuler('x', event)}
      >
        {ticks.ys.map((value) => (
          <span
            key={value}
            className="text-faint absolute left-0 w-full border-t border-current pl-0.5 text-[9px] leading-none"
            style={{ top: y + value * scale }}
          >
            {value}
          </span>
        ))}
      </div>
      <span className="bg-paper/90 border-line text-faint pointer-events-none absolute top-0 left-5 rounded-br px-1 text-[9px] leading-5">
        px
      </span>
      {pointer && (
        <span className="bg-ink absolute top-0 left-24 rounded-b px-1.5 py-0.5 text-[9px] text-white tabular-nums">
          {pointer.x} × {pointer.y}
        </span>
      )}
      {guides.map((guide) => (
        <GuideHandle
          key={guide.id}
          guide={guide}
          scale={scale}
          x={x}
          y={y}
          onMove={(position) => updateGuide(guide.id, clamp(guide.axis, position))}
          onDelete={() => removeGuide(guide.id)}
          positionFromClient={(clientX, clientY) => positionFromClient(guide.axis, clientX, clientY)}
        />
      ))}
    </div>
  )
}

function GuideHandle({
  guide,
  scale,
  x,
  y,
  onMove,
  onDelete,
  positionFromClient,
}: {
  guide: Guide
  scale: number
  x: number
  y: number
  onMove: (position: number) => void
  onDelete: () => void
  positionFromClient: (clientX: number, clientY: number) => number
}) {
  const style =
    guide.axis === 'x'
      ? { left: x + guide.position * scale, top: 20, width: 1, height: 'calc(100% - 20px)' }
      : { top: y + guide.position * scale, left: 20, height: 1, width: 'calc(100% - 20px)' }
  return (
    <div
      role="separator"
      aria-label={guide.axis === 'x' ? '垂直参考线' : '水平参考线'}
      tabIndex={0}
      className={`pointer-events-auto absolute bg-[#5f98ad]/70 outline-none hover:bg-brand ${
        guide.axis === 'x' ? 'cursor-col-resize' : 'cursor-row-resize'
      }`}
      style={style}
      title="拖动参考线；双击删除"
      onDoubleClick={onDelete}
      onKeyDown={(event) => {
        if (event.key === 'Delete' || event.key === 'Backspace') {
          event.preventDefault()
          event.stopPropagation()
          onDelete()
        }
      }}
      onPointerDown={(event) => {
        event.stopPropagation()
        const move = (next: PointerEvent) =>
          onMove(positionFromClient(next.clientX, next.clientY))
        const up = () => {
          window.removeEventListener('pointermove', move)
          window.removeEventListener('pointerup', up)
        }
        window.addEventListener('pointermove', move)
        window.addEventListener('pointerup', up, { once: true })
      }}
    />
  )
}
