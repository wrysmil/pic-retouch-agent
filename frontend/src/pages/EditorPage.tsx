import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import CanvasHint from '@/components/editor/CanvasHint'
import CanvasStage from '@/components/editor/CanvasStage'
import ChatIcon from '@/components/editor/ChatIcon'
import CropActions from '@/components/editor/CropActions'
import EditorRulers from '@/components/editor/EditorRulers'
import EditorToolbar from '@/components/editor/EditorToolbar'
import ImageWall from '@/components/editor/ImageWall'
import LayerPanel from '@/components/editor/LayerPanel'
import SessionSidebar from '@/components/editor/SessionSidebar'
import ProgressBar from '@/components/ui/ProgressBar'
import { buttonClass } from '@/components/ui/buttonStyles'
import { useEditorShortcuts } from '@/hooks/useEditorShortcuts'
import { useMountTransition } from '@/hooks/useMountTransition'
import { useSelection } from '@/hooks/useSelection'
import { usePatchSession, useSession, useSessionTools } from '@/hooks/useSessions'
import { useEditorUi } from '@/stores/editorUi'
import '@/components/editor/editor-chat.css'

// 与 index.css 的 slide-out 时长保持一致
const PANEL_EXIT_MS = 200

export default function EditorPage() {
  const { sessionId = '' } = useParams()
  const [mobileView, setMobileView] = useState<'chat' | 'canvas'>('chat')

  return (
    // 编辑器自成一屏：不让工具条或画布把外层 main 撑出滚动条，否则画布会被滚出视口
    <div className="editor-shell flex h-full overflow-hidden" data-mobile-view={mobileView}>
      <div className="editor-mobile-tabs" role="group" aria-label="编辑工作区切换">
        <button
          aria-pressed={mobileView === 'chat'}
          aria-controls="editor-conversation"
          onClick={() => setMobileView('chat')}
        >
          <ChatIcon name="spark" />
          对话
        </button>
        <button
          aria-pressed={mobileView === 'canvas'}
          aria-controls="editor-canvas"
          onClick={() => setMobileView('canvas')}
        >
          <ChatIcon name="image" />
          查看画布
        </button>
      </div>
      <SessionSidebar activeId={sessionId} onShowCanvas={() => setMobileView('canvas')} />
      <div className="editor-main flex min-h-0 min-w-0 flex-1" id="editor-canvas">
        {sessionId ? (
          <Workspace sessionId={sessionId} />
        ) : (
          <Notice title="选择一个会话" hint="从左侧打开历史对话，或回到创作页开始新的一张。">
            <CreateLink />
          </Notice>
        )}
      </div>
    </div>
  )
}

function Workspace({ sessionId }: { sessionId: string }) {
  const { data: session, isError } = useSession(sessionId)
  const patch = usePatchSession(sessionId)
  const tools = useSessionTools(sessionId)
  const picking = useSelection(sessionId, session?.revision ?? 0)

  const cropOpen = useEditorUi((state) => state.cropOpen)
  const compareOpen = useEditorUi((state) => state.compareOpen)
  const panel = useEditorUi((state) => state.panel)
  const selectMode = useEditorUi((state) => state.selectMode)
  const guidesEnabled = useEditorUi((state) => state.guidesEnabled)
  const heldPanel = useMountTransition(panel, PANEL_EXIT_MS)

  const urls = useMemo(
    () => new Map((session?.assets ?? []).map((asset) => [asset.id, asset.url])),
    [session?.assets],
  )

  useEditorShortcuts({ session: session ?? null, tools, picking })

  if (!session) {
    return isError ? (
      <Notice title="会话不存在" hint="链接可能已失效，回到创作页新建一个。">
        <CreateLink />
      </Notice>
    ) : (
      <Notice title="加载中" hint="正在读取会话状态" />
    )
  }

  return (
    <>
      <div className="flex min-w-0 flex-1 flex-col">
        <EditorToolbar
          session={session}
          tools={tools}
          picking={picking}
          onRename={(title) => patch.mutate({ title })}
        />
        {tools.pending && (
          <ProgressBar value={tools.pendingProgress} tone="brand" className="h-0.5 shrink-0" />
        )}

        <div className="relative flex min-h-0 min-w-0 flex-1">
          <div className="@container relative flex min-h-0 min-w-0 flex-1 flex-col">
            <div className="relative min-h-0 flex-1">
              <EditorRulers
                sessionId={session.id}
                document={session.document}
                enabled={guidesEnabled}
              />
              <CanvasStage
                document={session.document}
                previous={session.previous_document}
                urls={urls}
                selection={picking.selection}
                onPoint={picking.busy ? undefined : picking.addPoint}
                onStroke={picking.busy ? undefined : picking.addStroke}
                onMove={(layer_id, x, y) => tools.invoke('move_layer', { layer_id, x, y })}
                onScale={(layer_id, scale, x, y) =>
                  tools.invoke('scale_layer', { layer_id, scale_x: scale, scale_y: scale, x, y })
                }
                onEditText={(layer_id, text) => tools.invoke('set_layer_text', { layer_id, text })}
              />
              <CanvasHint
                {...canvasHint({
                  busy: tools.busy,
                  pending: tools.pending,
                  stage: tools.pendingStage,
                  progress: tools.pendingProgress,
                  cropOpen,
                  compareOpen,
                  selectMode,
                  picking: picking.busy,
                })}
              />
            </div>
            {cropOpen && <CropActions document={session.document} tools={tools} />}
          </div>
          {heldPanel && (
            <div
              className={`shadow-panel w-72 shrink-0 max-[960px]:absolute max-[960px]:inset-y-0 max-[960px]:right-0 max-[960px]:z-20 ${
                heldPanel.exiting ? 'animate-slide-out' : 'animate-slide-in'
              }`}
            >
              <LayerPanel session={session} tools={tools} panel={heldPanel.value} />
            </div>
          )}
        </div>

        <ImageWall
          assets={session.assets}
          currentId={session.current_asset_id}
          disabled={patch.isPending || tools.busy}
          onPick={(current_asset_id) => patch.mutate({ current_asset_id })}
        />
      </div>
    </>
  )
}

/** 提示按模式分组，这样切模式会重播一次入场，但进度百分比刷新不会。 */
function canvasHint({
  busy,
  pending,
  stage,
  progress,
  cropOpen,
  compareOpen,
  selectMode,
  picking,
}: {
  busy: boolean
  pending: boolean
  stage: string
  progress: number
  cropOpen: boolean
  compareOpen: boolean
  selectMode: 'point' | 'brush' | null
  picking: boolean
}) {
  // 撤销、重做没有任务进度，只说在忙
  if (busy) {
    return { mode: 'busy', text: pending ? `${stage || '处理中'} · ${progress}%` : '处理中' }
  }
  if (cropOpen) return { mode: 'crop', text: '拖动裁剪框 · 在下方应用或取消' }
  if (compareOpen) return { mode: 'compare', text: '拖动画布上的圆点对比上一版 · Esc 退出' }
  if (selectMode === 'point') {
    return picking
      ? { mode: 'point-busy', text: '正在识别选区…' }
      : { mode: 'point', text: '点击物体建立选区，可连续点选 · Esc 退出' }
  }
  if (selectMode === 'brush') {
    return { mode: 'brush', text: '按住圈出要改的区域，松手即选中圈内 · Esc 退出' }
  }
  return { mode: 'idle', text: null }
}

function CreateLink() {
  return (
    <Link to="/create" className={`${buttonClass({ variant: 'solid' })} mt-5 px-4 py-2 text-sm`}>
      去创作
    </Link>
  )
}

function Notice({
  title,
  hint,
  children,
}: {
  title: string
  hint: string
  children?: React.ReactNode
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-8 text-center">
      <h1 className="text-ink text-lg font-semibold">{title}</h1>
      <p className="text-muted mt-1 max-w-sm text-sm">{hint}</p>
      {children}
    </div>
  )
}
