import type { SessionDetail } from '@/api/sessions'
import Icon, { type IconName } from '@/components/ui/Icon'
import type { SessionTools } from '@/hooks/useSessions'
import { useEditorUi } from '@/stores/editorUi'

/** 编辑室左侧高频工具轨；低频工具收进右侧“属性 / 更多”。 */
export default function ToolRail({ session, tools }: { session: SessionDetail; tools: SessionTools }) {
  const ui = useEditorUi()
  const selectedLayerId = ui.selectedLayerId

  const removing = tools.isRunning('remove_background')

  return (
    <nav
      className="border-shell-line bg-shell on-dark grid shrink-0 grid-cols-8 gap-1 border-b p-2 lg:flex lg:w-[68px] lg:flex-col lg:overflow-visible lg:border-r lg:border-b-0 lg:py-3"
      aria-label="编辑工具"
    >
      <RailTool
        icon="select"
        label="选择"
        active={ui.selectMode === 'point'}
        disabled={tools.busy}
        onClick={() => ui.setSelectMode(ui.selectMode === 'point' ? null : 'point')}
      />
      <RailTool
        icon="brush"
        label="笔刷"
        active={ui.selectMode === 'brush'}
        disabled={tools.busy}
        onClick={() => ui.setSelectMode(ui.selectMode === 'brush' ? null : 'brush')}
      />
      <RailTool
        icon="crop"
        label="裁剪"
        active={ui.cropOpen}
        disabled={tools.busy}
        onClick={() => ui.openCrop(session.document)}
      />

      <span className="bg-shell-line my-1 hidden h-px w-full lg:block" aria-hidden />

      <RailTool
        icon="eraser"
        label="去背景"
        progress={removing ? tools.pendingProgress : null}
        disabled={tools.busy}
        onClick={() => tools.invoke('remove_background', { layer_id: selectedLayerId })}
      />
      <RailTool
        icon="image"
        label="换背景"
        active={ui.panel === 'background'}
        disabled={tools.busy}
        onClick={() => ui.setPanel(ui.panel === 'background' ? null : 'background')}
      />
      <RailTool
        icon="sliders"
        label="调色"
        active={ui.panel === 'adjust'}
        disabled={tools.busy}
        onClick={() => ui.setPanel(ui.panel === 'adjust' ? null : 'adjust')}
      />
      <RailTool
        icon="layers"
        label="图层"
        active={ui.panel === 'layers'}
        onClick={() => ui.setPanel(ui.panel === 'layers' ? null : 'layers')}
      />
      <RailTool
        icon="more"
        label="更多"
        active={ui.panel === 'properties'}
        onClick={() => ui.setPanel(ui.panel === 'properties' ? null : 'properties')}
      />
    </nav>
  )
}

function RailTool({
  icon,
  label,
  active,
  disabled,
  progress = null,
  onClick,
}: {
  icon: IconName
  label: string
  active?: boolean
  disabled?: boolean
  progress?: number | null
  onClick: () => void
}) {
  const running = progress !== null
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      aria-busy={running || undefined}
      title={label}
      className={`relative flex h-12 w-full min-w-0 shrink-0 flex-col items-center justify-center gap-0.5 rounded-control transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-35 lg:h-[54px] ${
        active || running
          ? 'bg-shell-3 text-shell-ink'
          : 'text-shell-muted hover:bg-shell-2 hover:text-shell-ink'
      }`}
    >
      <Icon name={icon} size={18} />
      <span className="text-[9px] leading-none">{label}</span>
      {active && (
        <span className="bg-signal absolute top-2 bottom-2 left-0 hidden w-0.5 rounded-full lg:block" aria-hidden />
      )}
      {running && (
        <span className="bg-signal absolute inset-x-2 bottom-1 h-0.5 overflow-hidden rounded-full">
          <span
            className="bg-signal/80 block h-full"
            style={{ width: `${Math.max(4, Math.min(100, progress ?? 0))}%` }}
          />
        </span>
      )}
    </button>
  )
}
