import { useEffect, useState } from 'react'

import type { Asset } from '@/api/assets'
import { ACTION_LABELS, type Layer, type SessionDetail } from '@/api/sessions'
import AgentConversation from '@/components/editor/AgentConversation'
import { BackgroundForm, ExpandForm, ReplaceForm } from '@/components/editor/GenerateEdits'
import Button from '@/components/ui/Button'
import Icon, { type IconName } from '@/components/ui/Icon'
import { useSessionHistory, type SessionTools } from '@/hooks/useSessions'
import { formatBytes, formatDateTime } from '@/lib/format'
import { wallOnly } from '@/lib/layers'
import { useEditorUi, type Panel } from '@/stores/editorUi'

const ADJUST_FIELDS: { key: string; label: string; min?: number }[] = [
  { key: 'brightness', label: '亮度' },
  { key: 'contrast', label: '对比度' },
  { key: 'highlights', label: '高光' },
  { key: 'shadows', label: '阴影' },
  { key: 'temperature', label: '色温' },
  { key: 'tint', label: '色调' },
  { key: 'saturation', label: '饱和度' },
  { key: 'vibrance', label: '自然饱和度' },
  { key: 'sharpness', label: '锐化' },
  { key: 'clarity', label: '清晰度' },
  { key: 'vignette', label: '晕影', min: 0 },
]

const REORDER_LABELS = {
  top: '置顶',
  up: '上移',
  down: '下移',
  bottom: '置底',
} as const

type Tab = 'director' | 'layers' | 'properties'

const TOOL_PANELS: Panel[] = ['adjust', 'background', 'expand', 'replace']

export default function LayerPanel({
  session,
  tools,
  panel,
}: {
  session: SessionDetail
  tools: SessionTools
  panel: Exclude<Panel, null>
}) {
  const setPanel = useEditorUi((state) => state.setPanel)
  const tab: Tab =
    panel === 'director' ? 'director' : panel === 'layers' ? 'layers' : 'properties'
  const title =
    panel === 'adjust'
      ? '调色'
      : panel === 'background'
        ? '换背景'
        : panel === 'expand'
          ? '扩图'
          : panel === 'replace'
            ? '局部替换'
            : tab === 'director'
              ? 'AI 导演'
              : tab === 'layers'
                ? '图层'
                : '属性与工具'

  const openTab = (next: Tab) => {
    if (next === 'properties') {
      if (TOOL_PANELS.includes(panel)) return
      setPanel('properties')
      return
    }
    setPanel(next)
  }

  return (
    <aside className="border-shell-line bg-shell-2 on-dark flex h-full w-full flex-col border-l lg:w-[304px] lg:shrink-0">
      <header className="border-shell-line shrink-0 border-b px-3 py-3">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="num text-[9px] tracking-[0.16em] text-shell-muted uppercase">Inspector</p>
            <h1 className="text-shell-ink mt-0.5 truncate text-[13px] font-semibold">{title}</h1>
          </div>
          <button
            type="button"
            onClick={() => setPanel(null)}
            aria-label="关闭面板"
            title="关闭面板"
            className="text-shell-muted hover:bg-shell-3 hover:text-shell-ink grid size-8 shrink-0 place-items-center rounded-control transition-colors"
          >
            <Icon name="x" size={16} />
          </button>
        </div>
        <div
          className="bg-shell border-shell-line mt-2.5 grid grid-cols-3 rounded-control border p-0.5"
          role="tablist"
          aria-label="右侧面板"
        >
          {(
            [
              { id: 'director' as const, label: 'AI 导演', icon: 'message' as const },
              { id: 'layers' as const, label: '图层', icon: 'layers' as const },
              { id: 'properties' as const, label: '属性', icon: 'sliders' as const },
            ] satisfies { id: Tab; label: string; icon: IconName }[]
          ).map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              onClick={() => openTab(item.id)}
              className={`flex min-h-8 items-center justify-center gap-1 rounded-[7px] text-[10px] font-medium transition-colors duration-150 ${
                tab === item.id
                  ? 'bg-shell-3 text-shell-ink'
                  : 'text-shell-muted hover:text-shell-ink'
              }`}
            >
              <Icon name={item.icon} size={12} />
              {item.label}
            </button>
          ))}
        </div>
      </header>

      <div className="relative min-h-0 flex-1 overflow-hidden">
        <div className={`h-full ${tab === 'director' ? 'block' : 'hidden'}`}>
          <DirectorPane session={session} />
        </div>
        <div className={`scrollbar-dark h-full overflow-y-auto ${tab === 'layers' ? 'block' : 'hidden'}`}>
          <LayersPane session={session} tools={tools} />
        </div>
        <div className={`scrollbar-dark h-full overflow-y-auto ${tab === 'properties' ? 'block' : 'hidden'}`}>
          <PropertiesPane session={session} tools={tools} panel={panel} />
        </div>
      </div>
    </aside>
  )
}

function DirectorPane({ session }: { session: SessionDetail }) {
  const ui = useEditorUi()
  const selectedLayerId = ui.selectedLayerId
  const selection = ui.selection
  const freshSelection = selection && selection.revision === session.revision ? selection : null
  const selected = selectedLayerId
    ? session.document.layers.find((layer) => layer.id === selectedLayerId)
    : undefined
  const thumb = selected?.asset_id
    ? session.assets.find((asset) => asset.id === selected.asset_id)
    : undefined

  const scope = freshSelection
    ? '当前选区'
    : selected
      ? `当前图层 · ${selected.name}`
      : '整张图片'

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-shell-line shrink-0 border-b p-3">
        <div className="border-shell-line bg-shell rounded-control border p-3">
          <div className="flex items-center justify-between gap-2">
            <span className="num text-[9px] tracking-[0.1em] text-shell-muted">当前上下文</span>
            <span className="bg-ai/15 text-ai rounded-full px-2 py-0.5 text-[9px]">
              {freshSelection ? '选区' : selected ? '图层' : '整图'}
            </span>
          </div>
          <div className="mt-2 flex items-center gap-2.5">
            {freshSelection ? (
              <span className="bg-checker border-shell-line size-10 shrink-0 overflow-hidden rounded-chip border">
                <img src={freshSelection.maskUrl} alt="" className="size-full object-cover" />
              </span>
            ) : thumb ? (
              <span className="bg-shell-3 border-shell-line size-10 shrink-0 overflow-hidden rounded-chip border">
                <img src={thumb.url} alt="" className="size-full object-cover" />
              </span>
            ) : (
              <span className="bg-shell-3 border-shell-line text-ai grid size-10 shrink-0 place-items-center rounded-chip border">
                <Icon name={selected?.kind === 'text' ? 'type' : 'image'} size={16} />
              </span>
            )}
            <div className="min-w-0">
              <p className="truncate text-[11px] font-medium text-shell-ink">
                {freshSelection ? '已识别的编辑区域' : (selected?.name ?? '整张图片')}
              </p>
              <p className="mt-0.5 truncate text-[10px] text-shell-muted">
                {freshSelection
                  ? `${freshSelection.markers.length} 个标点 · 只改选区内部`
                  : selected
                    ? selected.kind === 'text'
                      ? '文字图层'
                      : selected.locked
                        ? '图像图层 · 已锁定'
                        : '图像图层'
                    : '没有选中图层，作用于整张图'}
              </p>
            </div>
          </div>
          <div className="mt-2.5 flex items-start gap-1.5 border-t border-shell-line pt-2.5 text-[10px] leading-relaxed text-shell-muted">
            <Icon name="shield" size={12} className="mt-0.5 shrink-0 text-signal" />
            <span>多步修改会先列出计划，确认后才执行；每次结果都可撤销。</span>
          </div>
          <div className="mt-2 text-[10px] text-shell-muted">
            作用范围：<span className="text-shell-ink">{scope}</span>
          </div>
        </div>
      </div>

      <AgentConversation sessionId={session.id} />
    </div>
  )
}

function LayersPane({ session, tools }: { session: SessionDetail; tools: SessionTools }) {
  const { data: history = [] } = useSessionHistory(session.id)
  const selectedLayerId = useEditorUi((state) => state.selectedLayerId)
  const selectLayer = useEditorUi((state) => state.selectLayer)
  const selection = useEditorUi((state) => state.selection)
  const includeText = useEditorUi((state) => state.splitIncludeText)
  const setIncludeText = useEditorUi((state) => state.setSplitIncludeText)
  const selected =
    session.document.layers.find((layer) => layer.id === selectedLayerId) ??
    session.document.layers.at(-1)

  return (
    <div>
      <Section title="图层" icon="layers">
        <label className="mb-2 flex items-center gap-1.5 text-[10px] text-shell-muted">
          <input
            type="checkbox"
            checked={includeText}
            disabled={tools.busy}
            onChange={(event) => setIncludeText(event.target.checked)}
            className="accent-ai"
          />
          同时拆出文字
        </label>
        <div className="mb-2.5 flex gap-1.5">
          <Button
            variant="outline"
            size="sm"
            tone="dark"
            block
            disabled={tools.busy}
            progress={tools.isRunning('split_layers') ? tools.pendingProgress : null}
            title={includeText ? '拆成背景、主体和文字，可撤销' : '拆成背景和主体，可撤销'}
            onClick={() => tools.invoke('split_layers', { include_text: includeText })}
          >
            拆层
          </Button>
          <Button
            variant="outline"
            size="sm"
            tone="dark"
            block
            disabled={tools.busy || !selection}
            progress={tools.isRunning('promote_object_to_layer') ? tools.pendingProgress : null}
            title={selection ? '把选区提升为独立图层，可撤销' : '先点选或涂抹'}
            onClick={() =>
              tools.invoke('promote_object_to_layer', {
                mask_asset_id: selection?.maskId,
                revision: session.revision,
              })
            }
          >
            成层
          </Button>
        </div>
        <ul className="space-y-1">
          {[...session.document.layers].reverse().map((layer) => (
            <LayerRow
              key={layer.id}
              layer={layer}
              active={selected?.id === layer.id}
              disabled={tools.busy}
              thumb={
                layer.asset_id
                  ? session.assets.find((asset) => asset.id === layer.asset_id)
                  : undefined
              }
              onSelect={() => selectLayer(layer.id)}
              onToggleVisible={() =>
                tools.invoke('set_layer_visible', { layer_id: layer.id, visible: !layer.visible })
              }
            />
          ))}
        </ul>
      </Section>

      {selected?.kind === 'text' && (
        <Section title="文字" icon="type">
          <p className="mb-2.5 text-[10px] leading-relaxed text-shell-muted">
            改文案、字号或颜色。失焦写入，可用 ⌘Z 撤销。画布上双击文字层也可改。
          </p>
          <TextForm
            layer={selected}
            disabled={tools.busy}
            onCommit={(params) =>
              tools.invoke('set_layer_text', { layer_id: selected.id, ...params })
            }
          />
        </Section>
      )}

      {selected && (
        <Section title="变换" icon="move">
          <p className="mb-2.5 text-[10px] leading-relaxed text-shell-muted">
            选中图层后拖角缩放、拖动画布移动。滑杆也可改，松手写入，可用 ⌘Z 撤销。
          </p>
          <LayerControls
            layer={selected}
            disabled={tools.busy}
            onOpacity={(opacity) =>
              tools.invoke('set_layer_opacity', { layer_id: selected.id, opacity })
            }
            onScale={(scale) =>
              tools.invoke('scale_layer', {
                layer_id: selected.id,
                scale_x: scale,
                scale_y: scale,
              })
            }
            onRotate={(rotation) =>
              tools.invoke('rotate_layer', { layer_id: selected.id, rotation })
            }
            onReorder={(place) => tools.invoke('reorder_layer', { layer_id: selected.id, place })}
          />
        </Section>
      )}

      <Section title="编辑记录" icon="history">
        {history.length === 0 ? (
          <p className="text-[10px] text-shell-muted">暂无记录</p>
        ) : (
          <ol className="space-y-1.5">
            {history.map((entry) => (
              <li key={entry.seq} className="flex items-baseline justify-between gap-2 text-[10px]">
                <span className="text-shell-ink">{ACTION_LABELS[entry.action] ?? entry.action}</span>
                <span className="num shrink-0 text-shell-muted">{formatDateTime(entry.created_at)}</span>
              </li>
            ))}
          </ol>
        )}
      </Section>
    </div>
  )
}

function PropertiesPane({
  session,
  tools,
  panel,
}: {
  session: SessionDetail
  tools: SessionTools
  panel: Exclude<Panel, null>
}) {
  const selectedLayerId = useEditorUi((state) => state.selectedLayerId)
  const selection = useEditorUi((state) => state.selection)
  const setPanel = useEditorUi((state) => state.setPanel)
  const includeText = useEditorUi((state) => state.splitIncludeText)
  const current = session.assets.find((asset) => asset.id === session.current_asset_id)
  const onlyToWall = wallOnly(session.document)
  const inTool = TOOL_PANELS.includes(panel)

  return (
    <div>
      {inTool && (
        <div className="border-shell-line border-b px-4 py-2.5">
          <button
            type="button"
            onClick={() => setPanel('properties')}
            className="inline-flex items-center gap-1 text-[10px] text-shell-muted transition-colors hover:text-shell-ink"
          >
            <Icon name="arrow-left" size={12} />
            返回更多工具
          </button>
        </div>
      )}

      {panel === 'adjust' && (
        <AdjustForm
          disabled={tools.busy}
          onApply={(params) => tools.invoke('adjust_image', { ...params, layer_id: selectedLayerId })}
        />
      )}
      {panel === 'background' && (
        <BackgroundForm
          disabled={tools.busy}
          wallOnly={onlyToWall}
          onApply={(params) => tools.invoke('replace_background', params)}
        />
      )}
      {panel === 'expand' && (
        <ExpandForm
          disabled={tools.busy}
          wallOnly={onlyToWall}
          onApply={(params) => tools.invoke('expand_canvas', params)}
        />
      )}
      {panel === 'replace' && (
        <ReplaceForm
          disabled={tools.busy || !selection}
          onApply={(params) =>
            tools.invoke('replace_region', {
              ...params,
              mask_asset_id: selection?.maskId,
              revision: session.revision,
              layer_id: selectedLayerId,
            })
          }
        />
      )}

      {!inTool && (
        <Section title="更多工具" icon="wand">
          <p className="mb-2.5 text-[10px] leading-relaxed text-shell-muted">
            低频操作集中在这里，不占用画布上沿。
          </p>
          <div className="grid grid-cols-2 gap-1.5">
            <Button
              variant="outline"
              size="sm"
              tone="dark"
              block
              disabled={tools.busy}
              progress={
                tools.isRunning('flip_layer', (params) => params.direction === 'horizontal')
                  ? tools.pendingProgress
                  : null
              }
              onClick={() =>
                tools.invoke('flip_layer', {
                  direction: 'horizontal',
                  layer_id: selectedLayerId,
                })
              }
            >
              水平翻转
            </Button>
            <Button
              variant="outline"
              size="sm"
              tone="dark"
              block
              disabled={tools.busy}
              progress={
                tools.isRunning('flip_layer', (params) => params.direction === 'vertical')
                  ? tools.pendingProgress
                  : null
              }
              onClick={() =>
                tools.invoke('flip_layer', {
                  direction: 'vertical',
                  layer_id: selectedLayerId,
                })
              }
            >
              垂直翻转
            </Button>
            <Button
              variant="outline"
              size="sm"
              tone="dark"
              block
              disabled={tools.busy}
              progress={tools.isRunning('upscale_image') ? tools.pendingProgress : null}
              title={
                onlyToWall
                  ? '放大到两倍，已拆层所以结果只进图片墙'
                  : '把当前画布放大到两倍'
              }
              onClick={() => tools.invoke('upscale_image', { scale: 2 })}
            >
              超分 2×
            </Button>
            <Button
              variant="outline"
              size="sm"
              tone="dark"
              block
              disabled={tools.busy}
              progress={tools.isRunning('split_layers') ? tools.pendingProgress : null}
              title="拆成背景和主体，文字需额外勾选，可撤销"
              onClick={() => tools.invoke('split_layers', { include_text: includeText })}
            >
              拆层
            </Button>
            <Button
              variant="outline"
              size="sm"
              tone="dark"
              block
              disabled={tools.busy}
              onClick={() => setPanel('expand')}
            >
              扩图
            </Button>
            <Button
              variant="outline"
              size="sm"
              tone="dark"
              block
              disabled={tools.busy}
              onClick={() => setPanel('background')}
            >
              换背景
            </Button>
          </div>
        </Section>
      )}

      <Section title="画布属性" icon="file-image">
        <Properties document={session.document} current={current} revision={session.revision} />
      </Section>
    </div>
  )
}

function LayerRow({
  layer,
  active,
  disabled,
  thumb,
  onSelect,
  onToggleVisible,
}: {
  layer: Layer
  active: boolean
  disabled: boolean
  thumb?: Asset
  onSelect: () => void
  onToggleVisible: () => void
}) {
  return (
    <li
      className={`flex items-center rounded-control border transition-colors duration-150 ${
        active
          ? 'border-ai/45 bg-ai/10'
          : 'border-shell-line hover:border-shell-line hover:bg-shell-3/60'
      } ${layer.visible ? '' : 'opacity-50'}`}
    >
      <button
        type="button"
        onClick={onSelect}
        className="flex min-w-0 flex-1 items-center gap-2 px-2 py-1.5 text-left"
      >
        <span className="bg-shell-3 border-shell-line size-8 shrink-0 overflow-hidden rounded-chip border">
          {thumb ? (
            <img src={thumb.url} alt="" className="size-full object-cover" />
          ) : (
            <span className="text-ai grid size-full place-items-center">
              <Icon name={layer.kind === 'text' ? 'type' : 'image'} size={13} />
            </span>
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[11px] font-medium text-shell-ink">{layer.name}</span>
          <span className="block truncate text-[9px] text-shell-muted">
            {layer.kind === 'text' ? layer.text || '文字' : layer.locked ? '已锁定' : '图像'}
          </span>
        </span>
        <span className="num shrink-0 text-[9px] text-shell-muted">
          {Math.round(layer.opacity * 100)}%
        </span>
      </button>
      <Button
        variant="icon"
        size="sm"
        tone="dark"
        disabled={disabled}
        title={layer.visible ? '隐藏图层' : '显示图层'}
        onClick={onToggleVisible}
        className="mr-1 shrink-0"
      >
        <Icon name={layer.visible ? 'eye' : 'eye-off'} size={14} />
      </Button>
    </li>
  )
}

const TEXT_FIELD =
  'border-shell-line bg-shell-3 text-shell-ink placeholder:text-shell-muted focus:border-ai/60 w-full resize-none rounded-control border px-2.5 py-1.5 text-[11px] leading-relaxed outline-none'

function toHex6(value: string) {
  const raw = value.replace('#', '')
  if (raw.length === 3) return `#${[...raw].map((ch) => ch + ch).join('')}`
  return `#${raw.padEnd(6, '0')}`.slice(0, 7)
}

function TextForm({
  layer,
  disabled,
  onCommit,
}: {
  layer: Layer
  disabled: boolean
  onCommit: (params: { text: string; font_size: number; fill: string }) => void
}) {
  const [text, setText] = useState(layer.text || '')
  const [fontSize, setFontSize] = useState(layer.font_size ?? 24)
  const [fill, setFill] = useState(toHex6(layer.fill ?? '#141414'))
  const setLayerPreview = useEditorUi((state) => state.setLayerPreview)

  useEffect(() => {
    setText(layer.text || '')
    setFontSize(layer.font_size ?? 24)
    setFill(toHex6(layer.fill ?? '#141414'))
  }, [layer.id, layer.text, layer.font_size, layer.fill])

  const current = {
    text: layer.text || '',
    font_size: layer.font_size ?? 24,
    fill: toHex6(layer.fill ?? '#141414'),
  }

  const commit = (next: { text: string; font_size: number; fill: string }) => {
    if (
      next.text === current.text &&
      next.font_size === current.font_size &&
      next.fill.toLowerCase() === current.fill.toLowerCase()
    ) {
      return
    }
    onCommit(next)
  }

  return (
    <div className="space-y-3">
      <textarea
        rows={3}
        value={text}
        disabled={disabled}
        className={TEXT_FIELD}
        onChange={(event) => {
          const next = event.target.value
          setText(next)
          setLayerPreview({ id: layer.id, text: next })
        }}
        onBlur={() => commit({ text, font_size: fontSize, fill })}
        onKeyDown={(event) => {
          if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
            event.preventDefault()
            commit({ text, font_size: fontSize, fill })
          }
        }}
      />
      <SliderField
        label="字号"
        value={fontSize}
        origin={layer.font_size ?? 24}
        min={8}
        max={120}
        step={1}
        format={(value) => `${Math.round(value)}`}
        disabled={disabled}
        onInput={(value) => {
          setFontSize(value)
          setLayerPreview({ id: layer.id, font_size: value })
        }}
        onCommit={(value) => {
          setFontSize(value)
          commit({ text, font_size: value, fill })
        }}
      />
      <label className="flex items-center justify-between gap-2 text-[10px]">
        <span className="text-shell-muted">颜色</span>
        <input
          type="color"
          value={fill}
          disabled={disabled}
          className="border-shell-line h-7 w-12 cursor-pointer rounded border bg-transparent p-0"
          onChange={(event) => {
            const next = event.target.value
            setFill(next)
            setLayerPreview({ id: layer.id, fill: next })
            commit({ text, font_size: fontSize, fill: next })
          }}
        />
      </label>
    </div>
  )
}

function LayerControls({
  layer,
  disabled,
  onOpacity,
  onScale,
  onRotate,
  onReorder,
}: {
  layer: Layer
  disabled: boolean
  onOpacity: (value: number) => void
  onScale: (value: number) => void
  onRotate: (value: number) => void
  onReorder: (place: 'top' | 'bottom' | 'up' | 'down') => void
}) {
  const preview = useEditorUi((state) => state.layerPreview)
  const setLayerPreview = useEditorUi((state) => state.setLayerPreview)
  const scale = Math.abs(layer.transform.scale_x)

  // 文档追上预览后再撤；一收到新值就撤会把图层先拽回原位再跳到新位置
  useEffect(() => {
    if (!preview || preview.id !== layer.id) return
    const same =
      (preview.opacity === undefined || preview.opacity === layer.opacity) &&
      (preview.scale === undefined || Math.abs(preview.scale - scale) < 0.001) &&
      (preview.rotation === undefined || preview.rotation === layer.transform.rotation) &&
      (preview.x === undefined || Math.abs(preview.x - layer.transform.x) < 0.5) &&
      (preview.y === undefined || Math.abs(preview.y - layer.transform.y) < 0.5) &&
      (preview.text === undefined || preview.text === (layer.text || '')) &&
      (preview.font_size === undefined || preview.font_size === (layer.font_size ?? 24)) &&
      (preview.fill === undefined ||
        preview.fill.toLowerCase() === (layer.fill ?? '#141414').toLowerCase())
    if (same) setLayerPreview(null)
  }, [
    preview,
    scale,
    setLayerPreview,
    layer.id,
    layer.opacity,
    layer.transform.scale_x,
    layer.transform.rotation,
    layer.transform.x,
    layer.transform.y,
  ])

  useEffect(() => () => setLayerPreview(null), [setLayerPreview])

  return (
    <div className="space-y-3">
      <SliderField
        label="透明度"
        value={layer.opacity}
        origin={1}
        min={0}
        max={1}
        step={0.01}
        format={(value) => `${Math.round(value * 100)}%`}
        disabled={disabled}
        onInput={(opacity) => setLayerPreview({ id: layer.id, opacity })}
        onCommit={onOpacity}
      />
      <SliderField
        label="图层缩放"
        value={scale}
        origin={1}
        min={0.1}
        max={8}
        step={0.05}
        format={(value) => `${Math.round(value * 100)}%`}
        disabled={disabled}
        onInput={(value) => setLayerPreview({ id: layer.id, scale: value })}
        onCommit={onScale}
      />
      <SliderField
        label="旋转"
        value={layer.transform.rotation}
        origin={0}
        min={-180}
        max={180}
        step={1}
        format={(value) => `${Math.round(value)}°`}
        disabled={disabled}
        onInput={(rotation) => setLayerPreview({ id: layer.id, rotation })}
        onCommit={onRotate}
      />
      <div className="grid grid-cols-4 gap-1">
        {(['top', 'up', 'down', 'bottom'] as const).map((place) => (
          <Button
            key={place}
            variant="outline"
            size="sm"
            tone="dark"
            block
            disabled={disabled}
            onClick={() => onReorder(place)}
          >
            {REORDER_LABELS[place]}
          </Button>
        ))}
      </div>
    </div>
  )
}

function AdjustForm({
  disabled,
  onApply,
}: {
  disabled: boolean
  onApply: (params: Record<string, number>) => void
}) {
  const [values, setValues] = useState<Record<string, number>>({})
  const setAdjustPreview = useEditorUi((state) => state.setAdjustPreview)
  const touched = Object.keys(values).length > 0

  useEffect(() => () => setAdjustPreview(null), [setAdjustPreview])

  const clear = () => {
    setValues({})
    setAdjustPreview(null)
  }

  return (
    <Section title="调色" icon="palette">
      <p className="mb-2.5 text-[10px] leading-relaxed text-shell-muted">
        拖动即在画布预览，锐化与清晰度需应用后可见。点应用写入新版本，可撤销。
      </p>
      <div className="space-y-2.5">
        {ADJUST_FIELDS.map((field) => (
          <SliderField
            key={field.key}
            label={field.label}
            value={values[field.key] ?? 0}
            origin={0}
            min={field.min ?? -1}
            max={1}
            step={0.05}
            format={(value) => value.toFixed(2)}
            disabled={disabled}
            onInput={(value) => setAdjustPreview({ ...values, [field.key]: value })}
            onCommit={(value) => {
              const next = { ...values, [field.key]: value }
              setValues(next)
              setAdjustPreview(next)
            }}
          />
        ))}
        <div className="flex gap-2">
          <Button variant="outline" size="md" tone="dark" block disabled={disabled || !touched} onClick={clear}>
            重置
          </Button>
          <Button
            variant="signal"
            size="md"
            tone="dark"
            block
            disabled={disabled || !touched}
            title={touched ? '写入当前调色，可撤销' : '先拖动滑杆再应用'}
            onClick={() => {
              onApply(values)
              clear()
            }}
          >
            应用
          </Button>
        </div>
      </div>
    </Section>
  )
}

function SliderField({
  label,
  value,
  origin,
  min,
  max,
  step,
  format,
  disabled,
  onInput,
  onCommit,
}: {
  label: string
  value: number
  origin: number
  min: number
  max: number
  step: number
  format: (value: number) => string
  disabled: boolean
  onInput: (value: number) => void
  onCommit: (value: number) => void
}) {
  const [draft, setDraft] = useState<number | null>(null)

  const commit = () => {
    if (draft !== null && draft !== value) onCommit(draft)
    setDraft(null)
  }

  return (
    <label
      className="block select-none"
      title="双击复位"
      onDoubleClick={() => {
        setDraft(null)
        if (value !== origin) onCommit(origin)
      }}
    >
      <span className="mb-1 flex justify-between text-[10px]">
        <span className="text-shell-muted">{label}</span>
        <span className="num text-shell-ink">{format(draft ?? value)}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        value={draft ?? value}
        onChange={(event) => {
          const next = Number(event.target.value)
          setDraft(next)
          onInput(next)
        }}
        onPointerDown={(event) => event.currentTarget.setPointerCapture(event.pointerId)}
        onPointerUp={commit}
        onLostPointerCapture={commit}
      />
    </label>
  )
}

function Properties({
  document,
  current,
  revision,
}: {
  document: { width: number; height: number }
  current: Asset | undefined
  revision: number
}) {
  const rows: [string, string][] = [
    ['画布', `${document.width} × ${document.height}`],
    ['修订号', String(revision)],
  ]
  if (current) {
    rows.push(['格式', current.image_format.toUpperCase()])
    rows.push(['大小', formatBytes(current.size_bytes)])
    rows.push(['透明通道', current.has_alpha ? '有' : '无'])
  }

  return (
    <dl className="space-y-1.5 text-[10px]">
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-2">
          <dt className="text-shell-muted">{label}</dt>
          <dd className="num text-shell-ink">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function Section({
  title,
  icon,
  children,
}: {
  title: string
  icon: IconName
  children: React.ReactNode
}) {
  return (
    <section className="border-shell-line border-b px-4 py-4 last:border-b-0">
      <h2 className="mb-2.5 flex items-center gap-1.5 text-[11px] font-medium text-shell-ink">
        <Icon name={icon} size={13} className="text-ai" />
        {title}
      </h2>
      {children}
    </section>
  )
}
