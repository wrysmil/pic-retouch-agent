import { useEffect } from 'react'

import type { SessionDetail } from '@/api/sessions'
import type { SessionSelection } from '@/hooks/useSelection'
import type { SessionTools } from '@/hooks/useSessions'
import { ZOOM_STEP, useCanvasView } from '@/stores/canvasView'
import { useEditorUi } from '@/stores/editorUi'
import { toast } from '@/stores/toasts'

function editableTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false
  return Boolean(
    target.closest('input, textarea, select, [contenteditable="true"], [role="textbox"]'),
  )
}

function composing(event: KeyboardEvent) {
  return event.isComposing || event.keyCode === 229
}

/** One keyboard owner for the editor; tool state and interaction stay in sync. */
export function useEditorShortcuts({
  session,
  tools,
  picking,
}: {
  session: SessionDetail | null
  tools: SessionTools
  picking: SessionSelection
}) {
  const selectedLayerId = useEditorUi((state) => state.selectedLayerId)
  const cropOpen = useEditorUi((state) => state.cropOpen)
  const compareOpen = useEditorUi((state) => state.compareOpen)
  const selectMode = useEditorUi((state) => state.selectMode)
  const panel = useEditorUi((state) => state.panel)
  const setActiveTool = useEditorUi((state) => state.setActiveTool)
  const beginSpacePan = useEditorUi((state) => state.beginSpacePan)
  const endSpacePan = useEditorUi((state) => state.endSpacePan)
  const closeCrop = useEditorUi((state) => state.closeCrop)
  const setCompareOpen = useEditorUi((state) => state.setCompareOpen)
  const setSelectMode = useEditorUi((state) => state.setSelectMode)
  const setPanel = useEditorUi((state) => state.setPanel)
  const fit = useCanvasView((state) => state.fit)
  const stepZoom = useCanvasView((state) => state.stepZoom)
  const zoomTo = useCanvasView((state) => state.zoomTo)

  useEffect(() => {
    if (!session) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (composing(event) || editableTarget(event.target)) return

      if (event.key === 'Escape') {
        if (cropOpen) closeCrop()
        else if (compareOpen) setCompareOpen(false)
        else if (selectMode) setSelectMode(null)
        else if (panel) setPanel(null)
        return
      }

      if (event.code === 'Space') {
        if (cropOpen || compareOpen || event.repeat) return
        event.preventDefault()
        beginSpacePan()
        return
      }

      if (cropOpen || compareOpen) return

      const meta = event.metaKey || event.ctrlKey
      if (meta && event.key.toLowerCase() === 'z') {
        event.preventDefault()
        if (event.repeat || tools.busy || picking.busy) return
        if (event.shiftKey) {
          if (picking.canRedo) picking.redo()
          else if (session.can_redo) tools.redo()
        } else if (picking.canUndo) {
          picking.undo()
        } else if (session.can_undo) {
          tools.undo()
        }
        return
      }
      if (meta && event.key.toLowerCase() === 'y') {
        event.preventDefault()
        if (event.repeat || tools.busy || picking.busy) return
        if (picking.canRedo) picking.redo()
        else if (session.can_redo) tools.redo()
        return
      }

      if (event.key === 'Delete' || event.key === 'Backspace') {
        event.preventDefault()
        if (event.repeat || tools.busy) return
        if (!selectedLayerId) return
        const layer = session.document.layers.find((item) => item.id === selectedLayerId)
        if (!layer) return
        if (layer.locked) {
          toast('该图层已锁定，不能删除', 'danger')
          return
        }
        tools.invoke('delete_layer', { layer_id: selectedLayerId })
        return
      }

      if (meta || event.altKey) return
      const key = event.key.toLowerCase()
      if (!event.shiftKey && key === 'v') {
        setActiveTool('move')
        return
      }
      if (!event.shiftKey && key === 'b') {
        setActiveTool('brush')
        return
      }

      if (event.key === '0') {
        event.preventDefault()
        fit(session.document)
      } else if (event.key === '1') {
        event.preventDefault()
        zoomTo(1)
      } else if (event.key === '=' || event.key === '+') {
        event.preventDefault()
        stepZoom(ZOOM_STEP)
      } else if (event.key === '-') {
        event.preventDefault()
        stepZoom(1 / ZOOM_STEP)
      }
    }

    const onKeyUp = (event: KeyboardEvent) => {
      if (event.code === 'Space') endSpacePan()
    }
    const onBlur = () => endSpacePan()

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    window.addEventListener('blur', onBlur)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      window.removeEventListener('blur', onBlur)
      endSpacePan()
    }
  }, [
    session,
    tools,
    picking,
    selectedLayerId,
    cropOpen,
    compareOpen,
    selectMode,
    panel,
    setActiveTool,
    beginSpacePan,
    endSpacePan,
    closeCrop,
    setCompareOpen,
    setSelectMode,
    setPanel,
    fit,
    stepZoom,
    zoomTo,
  ])
}
