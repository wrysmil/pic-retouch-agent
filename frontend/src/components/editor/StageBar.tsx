import type { SessionDetail } from '@/api/sessions'
import Button from '@/components/ui/Button'
import Icon from '@/components/ui/Icon'
import type { SessionSelection } from '@/hooks/useSelection'
import type { SessionTools } from '@/hooks/useSessions'
import { ZOOM_STEP, useCanvasView } from '@/stores/canvasView'
import { useEditorUi, type CropRatio } from '@/stores/editorUi'

const CROP_RATIOS: { value: CropRatio; label: string }[] = [
  { value: 'free', label: '自由' },
  { value: '1:1', label: '1:1' },
  { value: '4:5', label: '4:5' },
  { value: '9:16', label: '9:16' },
  { value: '16:9', label: '16:9' },
]

/** 画布上沿：作用范围、当前模式的动作和缩放；不再与项目操作挤在一行。 */
export default function StageBar({
  session,
  tools,
  picking,
  scope,
}: {
  session: SessionDetail
  tools: SessionTools
  picking: SessionSelection
  scope: string
}) {
  const ui = useEditorUi()
  const scale = useCanvasView((state) => state.scale)
  const fit = useCanvasView((state) => state.fit)
  const stepZoom = useCanvasView((state) => state.stepZoom)
  const zoomTo = useCanvasView((state) => state.zoomTo)

  const running = (tool: string) => (tools.isRunning(tool) ? tools.pendingProgress : null)

  const confirmCrop = () => {
    if (!ui.cropRect) return
    tools.invoke('crop_canvas', {
      rect: {
        x: ui.cropRect.x / session.document.width,
        y: ui.cropRect.y / session.document.height,
        width: ui.cropRect.width / session.document.width,
        height: ui.cropRect.height / session.document.height,
      },
    })
    ui.closeCrop()
  }

  return (
    <div className="border-shell-line bg-shell-2 flex shrink-0 flex-wrap items-center justify-between gap-2 border-b px-3 py-2">
      <div className="flex min-w-0 flex-wrap items-center gap-1.5">
        {ui.selectMode ? (
          <>
            <span className="text-signal mr-1 hidden text-[10px] sm:inline">选区</span>
            <Button
              size="sm"
              tone="dark"
              active={ui.selectMode === 'point'}
              title="点击物体生成选区"
              onClick={() => ui.setSelectMode(ui.selectMode === 'point' ? null : 'point')}
            >
              点选
            </Button>
            <Button
              size="sm"
              tone="dark"
              active={ui.selectMode === 'brush'}
              title="涂抹出选区"
              onClick={() => ui.setSelectMode(ui.selectMode === 'brush' ? null : 'brush')}
            >
              笔刷
            </Button>
            <Button
              size="sm"
              tone="dark"
              disabled={tools.busy || picking.busy || !picking.selection}
              progress={running('erase_region')}
              title={picking.selection ? '消除选中区域' : '先点选或涂抹'}
              onClick={() =>
                tools.invoke('erase_region', {
                  mask_asset_id: picking.selection?.maskId,
                  revision: session.revision,
                  layer_id: ui.selectedLayerId,
                })
              }
            >
              消除
            </Button>
            <Button
              size="sm"
              tone="dark"
              disabled={!picking.selection}
              active={ui.panel === 'replace'}
              title={picking.selection ? '按描述替换选区' : '先点选或涂抹'}
              onClick={() => ui.setPanel(ui.panel === 'replace' ? null : 'replace')}
            >
              替换
            </Button>
            <Button
              size="sm"
              tone="dark"
              disabled={tools.busy || picking.busy || !picking.selection}
              progress={running('promote_object_to_layer')}
              title={picking.selection ? '把选区提升为独立图层，可撤销' : '先点选或涂抹'}
              onClick={() =>
                tools.invoke('promote_object_to_layer', {
                  mask_asset_id: picking.selection?.maskId,
                  revision: session.revision,
                })
              }
            >
              成层
            </Button>
            <Button
              size="sm"
              tone="dark"
              disabled={!picking.selection || picking.busy}
              title="清除当前选区"
              onClick={picking.clear}
            >
              清除
            </Button>
            <Button
              size="sm"
              tone="dark"
              title="退出选择 Esc"
              onClick={() => ui.setSelectMode(null)}
            >
              完成
            </Button>
          </>
        ) : ui.cropOpen ? (
          <>
            <span className="text-signal mr-1 hidden text-[10px] sm:inline">裁剪</span>
            {CROP_RATIOS.map((item) => (
              <Button
                key={item.value}
                size="sm"
                tone="dark"
                active={ui.cropRatio === item.value}
                title={item.value === 'free' ? '自由裁剪' : `按 ${item.label} 裁剪`}
                onClick={() => ui.setCropRatio(item.value, session.document)}
              >
                {item.label}
              </Button>
            ))}
            <Button size="sm" tone="dark" variant="signal" title="按当前框裁剪画布，可撤销" onClick={confirmCrop}>
              确定
            </Button>
            <Button size="sm" tone="dark" title="退出裁剪 Esc" onClick={ui.closeCrop}>
              取消
            </Button>
          </>
        ) : (
          <div className="flex min-w-0 items-center gap-2">
            <span className="text-[10px] text-shell-muted">作用范围</span>
            <span className="max-w-[36vw] truncate text-[11px] font-medium text-shell-ink sm:max-w-64">
              {scope}
            </span>
            {ui.compareOpen && (
              <span className="text-ai hidden items-center gap-1 text-[10px] sm:inline-flex">
                <Icon name="compare" size={12} />
                拖动分割线对比上一版
              </span>
            )}
          </div>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-1">
        <Button
          variant="icon"
          size="sm"
          tone="dark"
          title="缩小 -"
          onClick={() => stepZoom(1 / ZOOM_STEP)}
        >
          <Icon name="zoom-out" size={15} />
        </Button>
        <button
          type="button"
          title="实际像素 · 按 1"
          onClick={() => zoomTo(1)}
          className="num text-shell-muted hover:text-shell-ink min-h-8 w-11 rounded-chip text-[10px] transition-colors"
        >
          {Math.round(scale * 100)}%
        </button>
        <Button
          variant="icon"
          size="sm"
          tone="dark"
          title="放大 +"
          onClick={() => stepZoom(ZOOM_STEP)}
        >
          <Icon name="zoom-in" size={15} />
        </Button>
        <Button
          variant="icon"
          size="sm"
          tone="dark"
          title="适应窗口 · 按 0，画布内双击同样生效"
          onClick={() => fit(session.document)}
        >
          <Icon name="fit" size={15} />
        </Button>
      </div>
    </div>
  )
}
