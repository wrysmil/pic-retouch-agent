import { useEffect, useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'

import Icon from '@/components/ui/Icon'
import ProgressBar from '@/components/ui/ProgressBar'
import { buttonClass } from '@/components/ui/buttonStyles'
import AiCommandBar from '@/components/editor/AiCommandBar'
import CanvasHint from '@/components/editor/CanvasHint'
import CanvasStage from '@/components/editor/CanvasStage'
import EditorToolbar from '@/components/editor/EditorToolbar'
import ImageWall from '@/components/editor/ImageWall'
import LayerPanel from '@/components/editor/LayerPanel'
import StageBar from '@/components/editor/StageBar'
import ToolRail from '@/components/editor/ToolRail'
import { useAssetLibrary } from '@/hooks/useAssets'
import { useSelection } from '@/hooks/useSelection'
import { usePatchSession, useSession, useSessionTools, useSessions } from '@/hooks/useSessions'
import { formatDateTime } from '@/lib/format'
import { ZOOM_STEP, useCanvasView } from '@/stores/canvasView'
import { useEditorUi } from '@/stores/editorUi'

export default function EditorPage() {
  const { sessionId = '' } = useParams()

  return sessionId ? <Workspace sessionId={sessionId} /> : <SessionPicker />
}

function Workspace({ sessionId }: { sessionId: string }) {
  const { data: session, isError } = useSession(sessionId)
  const patch = usePatchSession(sessionId)
  const tools = useSessionTools(sessionId)
  const picking = useSelection(sessionId, session?.revision ?? 0)

  const cropOpen = useEditorUi((state) => state.cropOpen)
  const compareOpen = useEditorUi((state) => state.compareOpen)
  const panel = useEditorUi((state) => state.panel)
  const inspectorOpen = useEditorUi((state) => state.inspectorOpen)
  const selectMode = useEditorUi((state) => state.selectMode)
  const selectedLayerId = useEditorUi((state) => state.selectedLayerId)
  const closeCrop = useEditorUi((state) => state.closeCrop)
  const setCompareOpen = useEditorUi((state) => state.setCompareOpen)
  const setSelectMode = useEditorUi((state) => state.setSelectMode)
  const setPanel = useEditorUi((state) => state.setPanel)
  const setInspectorOpen = useEditorUi((state) => state.setInspectorOpen)

  const fit = useCanvasView((state) => state.fit)
  const stepZoom = useCanvasView((state) => state.stepZoom)
  const zoomTo = useCanvasView((state) => state.zoomTo)

  const urls = useMemo(
    () => new Map((session?.assets ?? []).map((asset) => [asset.id, asset.url])),
    [session?.assets],
  )

  useEffect(() => {
    if (!session) return
    const onKey = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
        return
      }
      // Esc 一次只收一层，先退临时模式，都退完了才关右侧面板
      if (event.key === 'Escape') {
        if (cropOpen) closeCrop()
        else if (compareOpen) setCompareOpen(false)
        else if (selectMode) setSelectMode(null)
        else if (inspectorOpen) setInspectorOpen(false)
        else if (panel) setPanel(null)
        return
      }

      const meta = event.metaKey || event.ctrlKey
      if (meta && event.key.toLowerCase() === 'z') {
        event.preventDefault()
        // 按住不放会连着触发 keydown，repeat 时不再发撤销
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

      // 视图快捷键不带修饰键，避开浏览器自身的缩放
      if (meta || event.shiftKey || event.altKey) return
      if (event.key === '0') fit(session.document)
      else if (event.key === '1') zoomTo(1)
      else if (event.key === '=' || event.key === '+') stepZoom(ZOOM_STEP)
      else if (event.key === '-') stepZoom(1 / ZOOM_STEP)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [
    session,
    tools,
    picking,
    cropOpen,
    compareOpen,
    selectMode,
    panel,
    inspectorOpen,
    closeCrop,
    setCompareOpen,
    setSelectMode,
    setPanel,
    setInspectorOpen,
    fit,
    stepZoom,
    zoomTo,
  ])

  if (!session) {
    return isError ? (
      <Notice title="会话不存在" hint="链接可能已失效，回到编辑室另选一个项目。">
        <Link to="/editor" className={`${buttonClass({ variant: 'signal', size: 'lg' })} mt-5 inline-flex`}>
          选择项目
        </Link>
      </Notice>
    ) : (
      <Notice title="正在读取画布" hint="项目与素材加载中" />
    )
  }

  const freshSelection =
    picking.selection && picking.selection.revision === session.revision ? picking.selection : null
  const selectedLayer = selectedLayerId
    ? session.document.layers.find((layer) => layer.id === selectedLayerId)
    : undefined
  const scope = freshSelection
    ? '当前选区'
    : selectedLayer
      ? `当前图层 · ${selectedLayer.name}`
      : '整张图片'

  return (
    <div className="bg-shell-2 on-dark flex h-full min-h-0 flex-col">
      <EditorToolbar
        session={session}
        tools={tools}
        picking={picking}
        onRename={(title) => patch.mutate({ title })}
      />
      {tools.pending && (
        <ProgressBar value={tools.pendingProgress} tone="signal" className="h-0.5 shrink-0" />
      )}
      {tools.error && (
        <div className="border-shell-line flex shrink-0 items-start justify-between gap-3 border-b bg-[#2a1d1b] px-3 py-2 text-[10px] text-[#f19a8f]">
          <span className="flex items-start gap-1.5">
            <Icon name="alert" size={13} className="mt-0.5 shrink-0" />
            {tools.error}
            <span className="text-shell-muted ml-1 hidden sm:inline">· 可直接重试上一步</span>
          </span>
          <button
            type="button"
            onClick={tools.clearError}
            className="shrink-0 text-shell-muted hover:text-shell-ink"
            aria-label="关闭错误提示"
          >
            <Icon name="x" size={13} />
          </button>
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <ToolRail session={session} tools={tools} />

        <div className="relative flex min-h-0 min-w-0 flex-1 flex-col">
          <StageBar session={session} tools={tools} picking={picking} scope={scope} />
          <div className="relative min-h-0 flex-1">
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
            <AiCommandBar
              sessionId={session.id}
              scope={scope}
              busy={tools.pending}
              stage={tools.pendingStage}
              progress={tools.pendingProgress}
            />
          </div>
          <ImageWall
            assets={session.assets}
            currentId={session.current_asset_id}
            updatedAt={session.updated_at}
            disabled={patch.isPending || tools.busy}
            onPick={(current_asset_id) => patch.mutate({ current_asset_id })}
          />
        </div>

        {panel && (
          <div
            className={`max-lg:fixed max-lg:inset-y-0 max-lg:right-0 max-lg:z-40 max-lg:w-[min(360px,92vw)] max-lg:transition-transform max-lg:duration-200 lg:relative lg:z-auto lg:block lg:w-[304px] lg:shrink-0 ${
              inspectorOpen ? 'max-lg:translate-x-0' : 'max-lg:translate-x-full'
            }`}
          >
            <LayerPanel session={session} tools={tools} panel={panel} />
          </div>
        )}
      </div>

      {panel && inspectorOpen && (
        <button
          type="button"
          aria-label="关闭右侧面板"
          onClick={() => setInspectorOpen(false)}
          className="bg-shell/60 fixed inset-0 z-30 backdrop-blur-[1px] lg:hidden"
        />
      )}
    </div>
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
  if (cropOpen) return { mode: 'crop', text: '拖动裁剪框，点确定应用 · Esc 取消' }
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

function SessionPicker() {
  const { data: sessions = [], isPending } = useSessions()
  const { data: groups = [] } = useAssetLibrary()
  const covers = new Map<string, (typeof groups)[number]>()
  for (const group of groups) {
    if (group.session_id) covers.set(group.session_id, group)
  }

  return (
    <div className="mx-auto max-w-[1240px] px-5 py-6 md:px-8 md:py-8 xl:px-10">
      <header className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-ai-strong num text-[10px] font-medium tracking-[0.18em] uppercase">
            Editing room · 编辑室
          </p>
          <h1 className="text-ink mt-2 text-[26px] leading-tight font-semibold tracking-[-0.03em] sm:text-[32px]">
            继续一个编辑会话
          </h1>
          <p className="text-muted mt-2 max-w-xl text-[13px] leading-relaxed">
            打开最近项目进入精修，或在项目台创建新的视觉方向。
          </p>
        </div>
        <Link to="/create" className={`${buttonClass({ variant: 'signal', size: 'lg' })} inline-flex shrink-0 items-center gap-2`}>
          <Icon name="plus" size={15} />
          新建项目
        </Link>
      </header>

      {isPending ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((item) => (
            <div key={item} className="border-line bg-panel h-32 animate-pulse rounded-card border" />
          ))}
        </div>
      ) : sessions.length === 0 ? (
        <div className="border-line bg-panel flex flex-col items-center justify-center rounded-card border border-dashed px-6 py-16 text-center">
          <span className="bg-ai-soft text-ai-strong grid size-11 place-items-center rounded-full">
            <Icon name="editor" size={20} />
          </span>
          <h2 className="text-ink mt-4 text-[15px] font-semibold">还没有编辑会话</h2>
          <p className="text-muted mt-1 max-w-sm text-[12px] leading-relaxed">
            从项目台生成候选或导入一张原片后，就能进入编辑室。
          </p>
          <Link to="/create" className={buttonClass({ variant: 'outline', size: 'lg' })} >
            去项目台
          </Link>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {sessions.map((session) => {
            const group = covers.get(session.id)
            return (
              <Link
                key={session.id}
                to={`/editor/${session.id}`}
                className="group border-line bg-panel hover:border-ai-strong/60 flex min-h-32 overflow-hidden rounded-card border transition-colors duration-150"
              >
                <span className="bg-panel-2 relative w-32 shrink-0 overflow-hidden">
                  {group ? (
                    <img
                      src={group.cover.url}
                      alt=""
                      loading="lazy"
                      className="size-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
                    />
                  ) : (
                    <span className="text-faint grid size-full place-items-center">
                      <Icon name="image" size={22} />
                    </span>
                  )}
                </span>
                <span className="flex min-w-0 flex-1 flex-col justify-between p-3.5">
                  <span>
                    <span className="text-ink block truncate text-[13px] font-medium">{session.title}</span>
                    <span className="text-muted num mt-1 block text-[10px]">
                      修订 {session.revision} · {formatDateTime(session.updated_at)}
                    </span>
                  </span>
                  <span className="text-ai-strong inline-flex items-center gap-1 text-[11px] font-medium">
                    打开编辑室
                    <Icon name="arrow-right" size={12} />
                  </span>
                </span>
              </Link>
            )
          })}
        </div>
      )}
    </div>
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
    <div className="bg-shell-2 on-dark flex h-full flex-col items-center justify-center px-8 text-center">
      <span className="bg-shell-3 text-ai grid size-11 place-items-center rounded-full">
        <Icon name="editor" size={20} />
      </span>
      <h1 className="text-shell-ink mt-4 text-lg font-semibold">{title}</h1>
      <p className="mt-1 max-w-sm text-[12px] text-shell-muted">{hint}</p>
      {children}
    </div>
  )
}
