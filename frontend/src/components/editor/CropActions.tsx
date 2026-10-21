import { useCallback, useEffect } from 'react'

import type { LayerDocument } from '@/api/sessions'
import Button from '@/components/ui/Button'
import type { SessionTools } from '@/hooks/useSessions'
import { useEditorUi } from '@/stores/editorUi'

export default function CropActions({
  document,
  tools,
}: {
  document: LayerDocument
  tools: SessionTools
}) {
  const cropRect = useEditorUi((state) => state.cropRect)
  const closeCrop = useEditorUi((state) => state.closeCrop)

  const confirmCrop = useCallback(() => {
    // 读取最新选框，避免拖动结束后立即按 Enter 时提交前一帧的位置。
    const ui = useEditorUi.getState()
    if (!ui.cropOpen || !ui.cropRect || tools.busy) return
    const rect = ui.cropRect
    tools.invoke('crop_canvas', {
      rect: {
        x: rect.x / document.width,
        y: rect.y / document.height,
        width: rect.width / document.width,
        height: rect.height / document.height,
      },
    })
    ui.closeCrop()
  }, [document.width, document.height, tools])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (
        event.key !== 'Enter' ||
        event.defaultPrevented ||
        event.repeat ||
        event.isComposing ||
        event.ctrlKey ||
        event.metaKey ||
        event.altKey ||
        event.shiftKey
      ) {
        return
      }
      if (
        event.target instanceof Element &&
        event.target.closest(
          'input, textarea, select, [contenteditable="true"], [data-crop-actions] button',
        )
      ) {
        return
      }
      event.preventDefault()
      confirmCrop()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [confirmCrop])

  return (
    <div className="bg-canvas flex shrink-0 justify-center px-3 pt-2 pb-4 sm:pb-5">
      <div
        role="group"
        aria-label="裁剪操作"
        data-crop-actions
        className="border-line bg-paper shadow-panel animate-pop flex max-w-full flex-wrap items-center justify-center gap-2 rounded-[16px] border p-2"
      >
        <span className="text-muted border-line hidden items-center gap-2 border-r px-3 text-xs @min-[380px]:flex">
          <svg viewBox="0 0 24 24" fill="none" className="text-brand-strong size-4" aria-hidden>
            <path
              d="M6 3v13a2 2 0 0 0 2 2h13M3 6h13a2 2 0 0 1 2 2v13"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
            />
          </svg>
          调整裁剪范围
        </span>
        <Button
          variant="outline"
          className="min-h-10 px-4"
          title="取消裁剪 · Esc"
          onClick={closeCrop}
        >
          取消 <kbd className="ml-1 hidden text-[10px] opacity-60 @min-[300px]:inline">Esc</kbd>
        </Button>
        <Button
          variant="solid"
          className="min-h-10 px-4"
          disabled={tools.busy || !cropRect}
          title="应用裁剪，可撤销 · Enter"
          onClick={confirmCrop}
        >
          应用裁剪 <kbd className="ml-1 hidden text-[10px] opacity-60 @min-[300px]:inline">↵</kbd>
        </Button>
      </div>
    </div>
  )
}
