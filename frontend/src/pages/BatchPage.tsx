import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import type { Asset } from '@/api/assets'
import { isTerminal } from '@/api/runs'
import ImageDropzone from '@/components/ImageDropzone'
import Icon from '@/components/ui/Icon'
import ProgressBar from '@/components/ui/ProgressBar'
import { buttonClass } from '@/components/ui/buttonStyles'
import { useAssetLibrary, useUploadAsset } from '@/hooks/useAssets'
import { errorMessage } from '@/hooks/useAuth'
import { useBatch, useBatches, useCreateBatch, useExportBatch } from '@/hooks/useBatch'
import {
  BATCH_STEPS,
  EMPTY_DRAFT,
  EXPAND_RATIOS,
  type BatchDraft,
  type BatchTool,
  draftReady,
  operationsOf,
} from '@/lib/batch'
import { formatDateTime } from '@/lib/format'
import { toast } from '@/stores/toasts'

const MAX_IMAGES = 20

export default function BatchPage() {
  const { runId = '' } = useParams()
  return runId ? <Watch runId={runId} /> : <Compose />
}

function Compose() {
  const navigate = useNavigate()
  const create = useCreateBatch()
  const upload = useUploadAsset()
  const { data: groups = [] } = useAssetLibrary()
  const { data: history = [] } = useBatches()
  const [assets, setAssets] = useState<Asset[]>([])
  const [draft, setDraft] = useState<BatchDraft>(EMPTY_DRAFT)
  const blocked = draftReady(draft, assets.length)
  const libraryAssets = useMemo(() => {
    const seen = new Set<string>()
    const list: Asset[] = []
    for (const asset of groups.flatMap((group) => group.assets)) {
      if (asset.kind === 'mask' || seen.has(asset.id)) continue
      seen.add(asset.id)
      list.push(asset)
    }
    return list.slice(0, 16)
  }, [groups])
  const selectedSteps = draft.selected
    .map((id) => BATCH_STEPS.find((step) => step.id === id))
    .filter((step): step is (typeof BATCH_STEPS)[number] => Boolean(step))

  const add = (asset: Asset) =>
    setAssets((current) =>
      current.some((item) => item.id === asset.id) || current.length >= MAX_IMAGES
        ? current
        : [...current, asset],
    )

  const start = () => {
    if (blocked) return
    create.mutate(
      {
        asset_ids: assets.map((asset) => asset.id),
        operations: operationsOf(draft),
        formats: draft.formats,
      },
      { onSuccess: (run) => navigate(`/batch/${run.id}`) },
    )
  }

  return (
    <div className="mx-auto max-w-[1240px] px-5 py-6 md:px-8 md:py-8 xl:px-10">
      <header className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-ai-strong num text-[10px] font-medium tracking-[0.18em] uppercase">
            Batch production · 批量任务
          </p>
          <h1 className="text-ink mt-2 text-[26px] leading-tight font-semibold tracking-[-0.03em] sm:text-[32px]">
            一次处理一组图片
          </h1>
          <p className="text-muted mt-2 max-w-xl text-[13px] leading-relaxed">
            对多张图走同一套像素处理，最多 {MAX_IMAGES} 张；提交后可在任务页查看真实进度与失败原因。
          </p>
        </div>
        <Link to="/marketing" className={`${buttonClass({ variant: 'outline', size: 'lg' })} inline-flex shrink-0 items-center gap-2`}>
          <Icon name="delivery" size={15} />
          回交付中心
        </Link>
      </header>

      <StepIndicator count={assets.length} steps={draft.selected.length} ready={!blocked} />

      <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-4">
          <section className="border-line bg-panel rounded-card border p-4" aria-labelledby="batch-step-1">
            <SectionHead
              id="batch-step-1"
              index="01"
              title="选择图片"
              hint={`已选 ${assets.length} / ${MAX_IMAGES} 张`}
            />
            <ImageDropzone
              multiple
              compact
              disabled={upload.isPending || assets.length >= MAX_IMAGES}
              hint={`JPG / PNG / WebP，最多 ${MAX_IMAGES} 张`}
              label="拖入多张图片，或点击选择"
              onFile={(file) =>
                upload.mutate(file, {
                  onSuccess: add,
                  onError: (error) => toast(errorMessage(error), 'danger'),
                })
              }
            />

            {assets.length > 0 && (
              <ul className="mt-3 flex flex-wrap gap-2">
                {assets.map((asset) => (
                  <li key={asset.id} className="relative">
                    <img
                      src={asset.url}
                      alt=""
                      className="border-line bg-panel-2 size-16 rounded-control border object-cover"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        setAssets((current) => current.filter((item) => item.id !== asset.id))
                      }
                      className="bg-shell text-shell-ink hover:bg-danger absolute -top-1.5 -right-1.5 grid size-5 place-items-center rounded-full transition-colors"
                      aria-label="移除这张图"
                    >
                      <Icon name="x" size={11} />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {groups.length > 0 && (
              <div className="border-line mt-4 border-t pt-3">
                <p className="text-faint mb-2 text-[10px]">从素材库添加</p>
                <ul className="scrollbar-slim flex gap-2 overflow-x-auto pb-1">
                  {libraryAssets.map((asset) => {
                      const active = assets.some((item) => item.id === asset.id)
                      return (
                        <li key={asset.id}>
                          <button
                            type="button"
                            onClick={() => add(asset)}
                            aria-pressed={active}
                            className={`block overflow-hidden rounded-control border-2 transition-colors ${
                              active ? 'border-ai-strong' : 'border-transparent hover:border-line-strong'
                            }`}
                            title={active ? '已在任务中' : '添加到任务'}
                          >
                            <img
                              src={asset.url}
                              alt=""
                              loading="lazy"
                              className="bg-panel-2 size-14 object-cover"
                            />
                          </button>
                        </li>
                      )
                    })}
                </ul>
              </div>
            )}
          </section>

          <Pipeline draft={draft} onChange={setDraft} />
        </div>

        <aside className="min-w-0 space-y-4">
          <section className="border-line bg-panel rounded-card border p-4 xl:sticky xl:top-6" aria-labelledby="batch-step-3">
            <SectionHead id="batch-step-3" index="03" title="检查并执行" hint="确认后立即开始" />
            <dl className="space-y-2 text-[11px]">
              <SummaryRow label="图片" value={`${assets.length} 张`} />
              <SummaryRow
                label="处理步骤"
                value={selectedSteps.length ? selectedSteps.map((step) => step.label).join(' → ') : '未选择'}
              />
              <SummaryRow label="导出格式" value={draft.formats.map((item) => item.toUpperCase()).join(' / ') || '未选择'} />
              {draft.selected.includes('prepare_delivery_sizes') && (
                <SummaryRow label="投放尺寸" value={draft.delivery.join(' / ') || '未选择'} />
              )}
            </dl>
            <div className="border-line mt-3 border-t pt-3">
              <button
                type="button"
                disabled={Boolean(blocked) || create.isPending}
                onClick={start}
                className={`${buttonClass({ variant: 'signal', size: 'lg' })} w-full`}
              >
                {create.isPending ? '提交中…' : '开始处理'}
              </button>
              {blocked ? (
                <p className="text-faint mt-2 text-[10px] leading-relaxed">{blocked}</p>
              ) : (
                <p className="text-faint mt-2 text-[10px] leading-relaxed">
                  提交后处理在后台继续，可随时离开此页。
                </p>
              )}
              {create.isError && (
                <p className="text-danger mt-2 text-[10px]">{errorMessage(create.error)}</p>
              )}
            </div>
          </section>

          {history.length > 0 && (
            <section className="border-line bg-panel rounded-card border p-4">
              <h2 className="text-ink mb-2 flex items-center gap-1.5 text-[12px] font-medium">
                <Icon name="history" size={13} className="text-ai-strong" />
                最近任务
              </h2>
              <ul className="space-y-1.5">
                {history.slice(0, 5).map((item) => {
                  const failed = item.items.filter((entry) => entry.status === 'failed').length
                  return (
                    <li key={item.run.id}>
                      <Link
                        to={`/batch/${item.run.id}`}
                        className="hover:bg-soft flex items-center justify-between gap-2 rounded-chip px-2 py-1.5 transition-colors"
                      >
                        <span className="min-w-0">
                          <span className="text-ink block truncate text-[10px]">
                            {item.items.length} 张 · {statusLabel(item.run.status)}
                            {failed ? ` · ${failed} 张失败` : ''}
                          </span>
                          <span className="text-faint num block text-[9px]">
                            {formatDateTime(item.created_at)}
                          </span>
                        </span>
                        <Icon name="chevron-right" size={12} className="text-faint shrink-0" />
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </section>
          )}
        </aside>
      </div>
    </div>
  )
}

function Watch({ runId }: { runId: string }) {
  const { data, live, isError } = useBatch(runId)
  const pack = useExportBatch(runId)
  const done = live.status && isTerminal(live.status)
  const items = data?.items ?? []
  const succeeded = items.filter((item) => item.status === 'succeeded').length
  const failed = items.filter((item) => item.status === 'failed').length

  const download = () =>
    pack.mutate(undefined, {
      onSuccess: ({ blob, filename }) => {
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = filename
        link.click()
        URL.revokeObjectURL(url)
        toast(`已打包 ${succeeded} 张`)
      },
    })

  if (!data && isError) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center px-8 text-center">
        <h1 className="text-ink text-lg font-semibold">任务不存在</h1>
        <Link to="/batch" className={`${buttonClass({ variant: 'outline', size: 'lg' })} mt-4 inline-flex`}>
          返回批量任务
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-[1240px] px-5 py-6 md:px-8 md:py-8 xl:px-10">
      <header className="mb-5 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-ai-strong num text-[10px] font-medium tracking-[0.18em] uppercase">
            Batch progress · 任务进度
          </p>
          <h1 className="text-ink mt-2 text-[26px] leading-tight font-semibold tracking-[-0.03em] sm:text-[30px]">
            {done ? (failed ? '处理完成，有失败项' : '批量处理完成') : '正在批量处理'}
          </h1>
          <p className="text-muted mt-2 text-[12px]">
            {live.stage || (done ? '任务已结束' : '任务已提交')}
            {!done ? ` · ${live.progress}%` : ''}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/batch"
            className={`${buttonClass({ variant: 'outline', size: 'lg' })} inline-flex items-center gap-2`}
          >
            <Icon name="plus" size={15} />
            新任务
          </Link>
          <button
            type="button"
            disabled={!done || succeeded === 0 || pack.isPending}
            onClick={download}
            className={`${buttonClass({ variant: 'signal', size: 'lg' })} inline-flex items-center gap-2`}
          >
            <Icon name={pack.isPending ? 'loader' : 'download'} size={15} className={pack.isPending ? 'animate-spin' : ''} />
            {pack.isPending ? '打包中…' : `打包 ${succeeded} 张`}
          </button>
        </div>
      </header>

      {!done && (
        <div className="border-line bg-panel mb-4 rounded-card border p-4">
          <div className="text-muted num mb-2 flex items-center justify-between text-[10px]">
            <span>{live.stage || '排队中'}</span>
            <span>{live.progress}%</span>
          </div>
          <ProgressBar value={live.progress} tone="brand" className="h-1 rounded-full" />
        </div>
      )}

      {done && failed > 0 && (
        <div className="border-danger/30 bg-danger/5 mb-4 flex flex-col gap-2 rounded-card border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-danger flex items-start gap-1.5 text-[11px]">
            <Icon name="alert" size={14} className="mt-0.5 shrink-0" />
            {failed} 张处理失败；已成功的 {succeeded} 张仍可打包。失败项不会自动重试。
          </p>
          <Link to="/batch" className={`${buttonClass({ variant: 'outline', size: 'sm' })} shrink-0`}>
            用相同素材重新发起
          </Link>
        </div>
      )}

      {live.error && <p className="text-danger mb-3 text-[12px]">{live.error}</p>}
      {pack.isError && <p className="text-danger mb-3 text-[12px]">{errorMessage(pack.error)}</p>}

      <div className="mb-4 grid grid-cols-3 gap-2">
        <CountCard label="已完成" value={succeeded} />
        <CountCard label="失败" value={failed} tone="danger" />
        <CountCard label="总计" value={items.length || '—'} />
      </div>

      <ul className="space-y-2.5">
        {items.map((item) => (
          <li key={item.source.id} className="border-line bg-panel rounded-card border p-3">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <img
                src={item.source.url}
                alt=""
                className="bg-panel-2 border-line size-16 shrink-0 rounded-control border object-contain"
              />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={item.status} />
                  <span className="text-muted num text-[10px]">
                    {item.source.width} × {item.source.height}
                  </span>
                  {item.outputs.length > 0 && (
                    <span className="text-faint num text-[10px]">· {item.outputs.length} 张结果</span>
                  )}
                </div>
                {item.error && (
                  <p className="text-danger mt-1 text-[11px] leading-relaxed">{item.error}</p>
                )}
                {item.status === 'failed' && (
                  <Link to="/batch" className="text-ai-strong mt-1 inline-flex items-center gap-1 text-[10px]">
                    <Icon name="refresh" size={11} />
                    新建任务重试
                  </Link>
                )}
              </div>
              <div className="flex shrink-0 flex-wrap gap-1.5">
                {item.outputs.slice(0, 6).map((output) => (
                  <img
                    key={output.id}
                    src={output.url}
                    alt=""
                    title={`${output.width} × ${output.height}`}
                    className="border-line bg-panel-2 size-12 rounded-chip border object-cover"
                  />
                ))}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Pipeline({
  draft,
  onChange,
}: {
  draft: BatchDraft
  onChange: (draft: BatchDraft) => void
}) {
  const toggle = (id: BatchTool) => {
    const selected = draft.selected.includes(id)
      ? draft.selected.filter((item) => item !== id)
      : [...draft.selected, id]
    onChange({ ...draft, selected })
  }

  const toggleFormat = (fmt: 'png' | 'jpg') => {
    const formats = draft.formats.includes(fmt)
      ? draft.formats.filter((item) => item !== fmt)
      : [...draft.formats, fmt]
    onChange({ ...draft, formats })
  }

  const toggleDelivery = (ratio: '1:1' | '4:5' | '9:16') => {
    const delivery = draft.delivery.includes(ratio)
      ? draft.delivery.filter((item) => item !== ratio)
      : [...draft.delivery, ratio]
    onChange({ ...draft, delivery })
  }

  return (
    <section className="border-line bg-panel rounded-card border p-4" aria-labelledby="batch-step-2">
      <SectionHead
        id="batch-step-2"
        index="02"
        title="处理步骤"
        hint={`已选 ${draft.selected.length} 步，按勾选顺序执行`}
      />
      <ul className="grid gap-2 sm:grid-cols-2">
        {BATCH_STEPS.map((step) => {
          const on = draft.selected.includes(step.id)
          return (
            <li
              key={step.id}
              className={`rounded-control border p-3 transition-colors duration-150 ${
                on ? 'border-ai-strong/50 bg-ai-soft/40' : 'border-line'
              }`}
            >
              <button
                type="button"
                onClick={() => toggle(step.id)}
                aria-pressed={on}
                className="flex w-full cursor-pointer items-start gap-2.5 text-left"
              >
                <span
                  className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border ${
                    on ? 'border-ai-strong bg-ai text-white' : 'border-line-strong text-transparent'
                  }`}
                >
                  <Icon name="check" size={11} />
                </span>
                <span className="min-w-0">
                  <span className="text-ink flex items-center gap-1.5 text-[12px] font-medium">
                    {step.label}
                  </span>
                  <span className="text-muted mt-0.5 block text-[10px]">{step.hint}</span>
                </span>
              </button>
              {on && step.id === 'replace_background' && (
                <input
                  value={draft.prompt}
                  onChange={(event) => onChange({ ...draft, prompt: event.target.value })}
                  placeholder="例如：浅木色桌面，晨光"
                  className="border-line text-ink placeholder:text-faint focus:border-ai-strong mt-2.5 w-full rounded-chip border bg-transparent px-2.5 py-1.5 text-[11px] outline-none"
                />
              )}
              {on && step.id === 'adjust_image' && (
                <div className="mt-2.5 grid grid-cols-3 gap-2">
                  <Slider
                    label="亮度"
                    value={draft.brightness}
                    onChange={(brightness) => onChange({ ...draft, brightness })}
                  />
                  <Slider
                    label="对比"
                    value={draft.contrast}
                    onChange={(contrast) => onChange({ ...draft, contrast })}
                  />
                  <Slider
                    label="饱和"
                    value={draft.saturation}
                    onChange={(saturation) => onChange({ ...draft, saturation })}
                  />
                </div>
              )}
              {on && step.id === 'upscale_image' && (
                <div className="mt-2.5 flex gap-1.5">
                  {([2, 4] as const).map((scale) => (
                    <button
                      key={scale}
                      type="button"
                      onClick={() => onChange({ ...draft, scale })}
                      className={`rounded-chip px-2.5 py-1 text-[10px] ${
                        draft.scale === scale
                          ? 'bg-ink text-white'
                          : 'border-line text-muted border'
                      }`}
                    >
                      {scale} 倍
                    </button>
                  ))}
                </div>
              )}
              {on && step.id === 'expand_canvas' && (
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {EXPAND_RATIOS.map((ratio) => (
                    <button
                      key={ratio}
                      type="button"
                      onClick={() => onChange({ ...draft, expandRatio: ratio })}
                      className={`num rounded-chip px-2.5 py-1 text-[10px] ${
                        draft.expandRatio === ratio
                          ? 'bg-ink text-white'
                          : 'border-line text-muted border'
                      }`}
                    >
                      {ratio}
                    </button>
                  ))}
                </div>
              )}
              {on && step.id === 'prepare_delivery_sizes' && (
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {(['1:1', '4:5', '9:16'] as const).map((ratio) => (
                    <button
                      key={ratio}
                      type="button"
                      onClick={() => toggleDelivery(ratio)}
                      className={`num rounded-chip px-2.5 py-1 text-[10px] ${
                        draft.delivery.includes(ratio)
                          ? 'bg-ink text-white'
                          : 'border-line text-muted border'
                      }`}
                    >
                      {ratio}
                    </button>
                  ))}
                </div>
              )}
            </li>
          )
        })}
      </ul>

      <div className="border-line mt-3 flex flex-wrap items-center gap-2 border-t pt-3">
        <span className="text-muted text-[10px]">导出格式</span>
        {(['png', 'jpg'] as const).map((fmt) => {
          const on = draft.formats.includes(fmt)
          return (
            <button
              key={fmt}
              type="button"
              aria-pressed={on}
              onClick={() => toggleFormat(fmt)}
              className={`inline-flex items-center gap-1 rounded-chip border px-2.5 py-1 text-[10px] transition-colors ${
                on ? 'border-ai-strong bg-ai-soft text-brand-strong' : 'border-line text-muted'
              }`}
            >
              <Icon name={on ? 'check' : 'plus'} size={11} />
              {fmt.toUpperCase()}
            </button>
          )
        })}
      </div>
    </section>
  )
}

function StepIndicator({ count, steps, ready }: { count: number; steps: number; ready: boolean }) {
  const items = [
    { index: '01', label: '选图', done: count > 0 },
    { index: '02', label: '步骤', done: steps > 0 },
    { index: '03', label: '执行', done: count > 0 && steps > 0 && ready },
  ]
  return (
    <ol className="border-line bg-panel flex overflow-hidden rounded-card border">
      {items.map((item, index) => (
        <li
          key={item.index}
          className={`flex min-h-12 flex-1 items-center justify-center gap-2 text-[11px] ${
            index < items.length - 1 ? 'border-line border-r' : ''
          } ${item.done ? 'text-ink' : 'text-faint'}`}
        >
          <span
            className={`num grid size-6 place-items-center rounded-full text-[9px] ${
              item.done ? 'bg-ai-soft text-ai-strong' : 'bg-panel-2 text-faint'
            }`}
          >
            {item.done ? <Icon name="check" size={12} /> : item.index}
          </span>
          <span className="font-medium">{item.label}</span>
        </li>
      ))}
    </ol>
  )
}

function SectionHead({
  id,
  index,
  title,
  hint,
}: {
  id: string
  index: string
  title: string
  hint: string
}) {
  return (
    <div className="mb-3 flex items-end justify-between gap-2">
      <h2 id={id} className="text-ink flex items-center gap-2 text-[14px] font-semibold tracking-tight">
        <span className="num text-ai-strong text-[10px]">{index}</span>
        {title}
      </h2>
      <span className="text-faint num text-[10px]">{hint}</span>
    </div>
  )
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-muted shrink-0">{label}</dt>
      <dd className="text-ink text-right">{value}</dd>
    </div>
  )
}

function CountCard({
  label,
  value,
  tone = 'default',
}: {
  label: string
  value: number | string
  tone?: 'default' | 'danger'
}) {
  return (
    <div className="border-line bg-panel rounded-card border px-3 py-2.5">
      <p className="text-faint text-[10px]">{label}</p>
      <p
        className={`num mt-0.5 text-[20px] font-semibold tracking-tight ${
          tone === 'danger' ? 'text-danger' : 'text-ink'
        }`}
      >
        {value}
      </p>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const style =
    status === 'succeeded'
      ? 'bg-ai-soft text-ai-strong'
      : status === 'failed'
        ? 'bg-danger/10 text-danger'
        : status === 'running'
          ? 'bg-signal-soft text-signal-ink'
          : 'bg-soft text-muted'

  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${style}`}>
      {statusLabel(status)}
    </span>
  )
}

function Slider({
  label,
  value,
  onChange,
}: {
  label: string
  value: number
  onChange: (value: number) => void
}) {
  return (
    <label className="text-faint block text-[10px]">
      {label}
      <input
        type="range"
        min={-1}
        max={1}
        step={0.05}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-1 w-full"
      />
    </label>
  )
}

function statusLabel(status: string) {
  if (status === 'succeeded') return '已完成'
  if (status === 'failed') return '失败'
  if (status === 'running') return '处理中'
  if (status === 'canceled') return '已取消'
  return '等待中'
}
