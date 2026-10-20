import { useMemo, useState, type CSSProperties } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import type { Asset, LibraryGroup } from '@/api/assets'
import type { SessionDetail } from '@/api/sessions'
import Icon from '@/components/ui/Icon'
import ProgressBar from '@/components/ui/ProgressBar'
import { buttonClass } from '@/components/ui/buttonStyles'
import { errorMessage } from '@/hooks/useAuth'
import { useAssetLibrary } from '@/hooks/useAssets'
import { useBatches } from '@/hooks/useBatch'
import {
  useCreateSession,
  useExportPack,
  usePatchSession,
  useSession,
  useSessionTools,
  useSessions,
} from '@/hooks/useSessions'
import { formatBytes, formatDateTime, shortTitle } from '@/lib/format'
import { KIND_LABELS, MARKETING_KINDS, defaultSelected, packable } from '@/lib/marketing'
import { toast } from '@/stores/toasts'

type DeliveryRatio = '1:1' | '4:5' | '9:16'
type ChannelFilter = 'all' | DeliveryRatio

const CHANNELS: {
  ratio: DeliveryRatio
  label: string
  scene: string
  width: number
  height: number
}[] = [
  { ratio: '1:1', label: '商品主图', scene: '商品详情', width: 1080, height: 1080 },
  { ratio: '4:5', label: '信息流', scene: '社交媒体', width: 1080, height: 1350 },
  { ratio: '9:16', label: '竖版物料', scene: '广告投放', width: 1080, height: 1920 },
]

const MAX_PACK_BYTES = 20 * 1024 * 1024

export default function MarketingPage() {
  const { sessionId = '' } = useParams()
  return sessionId ? <Workspace sessionId={sessionId} /> : <Picker />
}

function Picker() {
  const navigate = useNavigate()
  const { data: groups = [], isPending } = useAssetLibrary()
  const createSession = useCreateSession()

  const open = (group: LibraryGroup) => {
    if (group.session_id) {
      navigate(`/marketing/${group.session_id}`)
      return
    }
    createSession.mutate(
      { current_asset_id: group.cover.id },
      { onSuccess: (session) => navigate(`/marketing/${session.id}`) },
    )
  }

  return (
    <div className="mx-auto max-w-[1240px] px-5 py-6 md:px-8 md:py-8 xl:px-10">
      <header className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-ai-strong num text-[10px] font-medium tracking-[0.18em] uppercase">
            Delivery desk · 交付中心
          </p>
          <h1 className="text-ink mt-2 text-[26px] leading-tight font-semibold tracking-[-0.03em] sm:text-[32px]">
            选择要交付的项目
          </h1>
          <p className="text-muted mt-2 max-w-xl text-[13px] leading-relaxed">
            按真实比例检查渠道物料，补齐缺失尺寸，再统一打包。
          </p>
        </div>
        <Link to="/create" className={`${buttonClass({ variant: 'outline', size: 'lg' })} inline-flex shrink-0 items-center gap-2`}>
          <Icon name="plus" size={15} />
          新建项目
        </Link>
      </header>

      {isPending ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((item) => (
            <div key={item} className="border-line bg-panel h-28 animate-pulse rounded-card border" />
          ))}
        </div>
      ) : groups.length === 0 ? (
        <div className="border-line bg-panel flex flex-col items-center justify-center rounded-card border border-dashed px-6 py-16 text-center">
          <span className="bg-ai-soft text-ai-strong grid size-11 place-items-center rounded-full">
            <Icon name="delivery" size={20} />
          </span>
          <h2 className="text-ink mt-4 text-[15px] font-semibold">还没有可交付的项目</h2>
          <p className="text-muted mt-1 max-w-sm text-[12px] leading-relaxed">
            先在项目台生成候选或上传原片，完成编辑后即可检查渠道尺寸。
          </p>
          <Link to="/create" className={`${buttonClass({ variant: 'signal', size: 'lg' })} mt-5 inline-flex`}>
            去项目台
          </Link>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {groups.map((group) => (
            <button
              key={group.session_id ?? group.cover.id}
              type="button"
              onClick={() => open(group)}
              className="group border-line bg-panel hover:border-ai-strong/60 flex min-h-28 overflow-hidden rounded-card border text-left transition-colors duration-150"
            >
              <span className="bg-panel-2 relative w-32 shrink-0 overflow-hidden">
                <img
                  src={group.cover.url}
                  alt=""
                  loading="lazy"
                  className="size-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
                />
              </span>
              <span className="flex min-w-0 flex-1 flex-col justify-between p-3.5">
                <span>
                  <span className="text-ink block truncate text-[13px] font-medium">{group.title}</span>
                  <span className="text-muted num mt-1 block text-[10px]">
                    {group.assets.length} 张素材 · {formatDateTime(group.updated_at)}
                  </span>
                </span>
                <span className="text-ai-strong inline-flex items-center gap-1 text-[11px] font-medium">
                  打开交付中心
                  <Icon name="arrow-right" size={12} />
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function Workspace({ sessionId }: { sessionId: string }) {
  const { data: session, isError } = useSession(sessionId)
  const tools = useSessionTools(sessionId)
  const pack = useExportPack(sessionId)
  const patch = usePatchSession(sessionId)
  const [copy, setCopy] = useState('')
  const [picked, setPicked] = useState<string[] | null>(null)
  const [filter, setFilter] = useState<ChannelFilter>('all')

  const selected = useMemo(() => {
    if (!session) return []
    return picked ?? defaultSelected(session.assets, session.current_asset_id)
  }, [session, picked])

  if (!session) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center px-8 text-center">
        <h1 className="text-ink text-lg font-semibold">{isError ? '会话不存在' : '加载中'}</h1>
        <p className="text-muted mt-1 text-sm">
          {isError ? '回到交付中心另选一个项目。' : '正在读取画布与素材'}
        </p>
        {isError && (
          <Link to="/marketing" className={`${buttonClass({ variant: 'outline', size: 'lg' })} mt-4 inline-flex`}>
            返回交付中心
          </Link>
        )}
      </div>
    )
  }

  const current = session.assets.find((asset) => asset.id === session.current_asset_id)
  const items = session.assets.filter((asset) => packable(asset, session.current_asset_id))
  const versions = session.assets.filter(
    (asset) =>
      asset.kind !== 'mask' && asset.kind !== 'subject' && asset.kind !== 'background',
  )
  const channelStates = CHANNELS.map((channel) => ({
    channel,
    asset: findForRatio(session.assets, channel),
  }))
  const missing = channelStates.filter((item) => !item.asset)
  const shown = channelStates.filter((item) => filter === 'all' || item.channel.ratio === filter)

  const complete = channelStates.length - missing.length
  const pixelReady = channelStates.every(
    (item) =>
      !item.asset ||
      (item.asset.width >= item.channel.width && item.asset.height >= item.channel.height),
  )
  const sizesOk =
    selected.length > 0 &&
    selected.every((id) => {
      const asset = session.assets.find((item) => item.id === id)
      return asset ? asset.size_bytes <= MAX_PACK_BYTES : false
    })
  const checks = [
    {
      ok: Boolean(current),
      title: '主视觉已选定',
      detail: current
        ? `${current.width} × ${current.height} · ${KIND_LABELS[current.kind]}`
        : '尚未选择当前主视觉',
    },
    {
      ok: complete === channelStates.length,
      title: '渠道尺寸齐全',
      detail: `${complete}/${channelStates.length} 个尺寸已有真实素材`,
    },
    {
      ok: pixelReady,
      title: '输出像素达到建议值',
      detail: pixelReady
        ? `已生成的 ${complete}/${channelStates.length} 个尺寸不小于 1080 宽`
        : '部分尺寸低于建议像素，可重新生成',
    },
    {
      ok: selected.length > 0,
      title: '已选择打包文件',
      detail: selected.length ? `${selected.length} 张待打包` : '勾选要交付的素材',
    },
    {
      ok: sizesOk,
      title: '文件体积可打包',
      detail: sizesOk ? '均在 20 MB 以内' : '有素材超过 20 MB',
    },
  ]
  const passed = checks.filter((item) => item.ok).length

  const deliveryRunning = (ratio?: string) =>
    tools.isRunning('prepare_delivery_sizes', (params) => {
      const ratios = params.ratios as string[] | undefined
      return ratio ? Boolean(ratios?.includes(ratio as DeliveryRatio)) : !ratios
    })

  const download = (ids: string[]) => {
    if (!ids.length) return
    pack.mutate(ids, {
      onSuccess: ({ blob, filename }) => {
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = filename
        link.click()
        URL.revokeObjectURL(url)
        toast(`已打包 ${ids.length} 张`)
      },
    })
  }

  const exportAll = () => {
    const ids = items.map((asset) => asset.id)
    setPicked(ids)
    download(ids)
  }

  const toggle = (id: string) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setPicked([...next])
  }

  const toggleAll = () => {
    const ids = items.map((asset) => asset.id)
    setPicked(ids.every((id) => selected.includes(id)) ? [] : ids)
  }

  const generateMissing = () => {
    const ratios = missing.map((item) => item.channel.ratio)
    if (!ratios.length) return
    tools.invoke('prepare_delivery_sizes', { ratios })
  }

  return (
    <div className="mx-auto max-w-[1420px] px-5 py-6 md:px-8 md:py-8 xl:px-10">
      <header className="mb-5 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <p className="text-ai-strong num text-[10px] font-medium tracking-[0.18em] uppercase">
            Delivery desk · 交付中心
          </p>
          <h1 className="text-ink mt-2 truncate text-[24px] leading-tight font-semibold tracking-[-0.03em] sm:text-[30px]">
            {session.title}
          </h1>
          <p className="text-muted num mt-2 text-[11px]">
            画布 {session.document.width} × {session.document.height} · 修订 {session.revision} ·{' '}
            {versions.length} 个版本
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SessionSwitch currentId={sessionId} />
          <Link
            to={`/editor/${sessionId}`}
            className={`${buttonClass({ variant: 'outline', size: 'lg' })} inline-flex items-center gap-2`}
          >
            <Icon name="editor" size={15} />
            回编辑室
          </Link>
          <button
            type="button"
            disabled={tools.busy || complete === channelStates.length}
            onClick={generateMissing}
            className={`${buttonClass({ variant: 'outline', size: 'lg' })} inline-flex items-center gap-2`}
          >
            <Icon name="sparkles" size={15} />
            {complete === channelStates.length ? '尺寸已齐' : `补齐 ${missing.length} 个尺寸`}
          </button>
          <button
            type="button"
            disabled={items.length === 0 || pack.isPending}
            onClick={exportAll}
            className={`${buttonClass({ variant: 'signal', size: 'lg' })} inline-flex items-center gap-2`}
          >
            <Icon name={pack.isPending ? 'loader' : 'download'} size={15} className={pack.isPending ? 'animate-spin' : ''} />
            {pack.isPending ? '打包中…' : '导出全部'}
          </button>
        </div>
      </header>

      {tools.busy && (
        <div className="border-line bg-panel mb-4 rounded-card border px-4 py-3">
          <div className="flex items-center justify-between gap-3 text-[11px]">
            <span className="text-ink flex items-center gap-1.5">
              <Icon name="loader" size={13} className="animate-spin text-ai-strong" />
              {tools.pendingStage || '处理中'}
            </span>
            {tools.pending && <span className="num text-muted">{tools.pendingProgress}%</span>}
          </div>
          {tools.pending && (
            <ProgressBar value={tools.pendingProgress} tone="brand" className="mt-2 h-0.5 rounded-full" />
          )}
        </div>
      )}
      {tools.error && (
        <div className="border-danger/30 bg-danger/5 text-danger mb-4 flex items-start justify-between gap-3 rounded-card border px-4 py-2.5 text-[11px]">
          <span className="flex items-start gap-1.5">
            <Icon name="alert" size={14} className="mt-0.5 shrink-0" />
            {tools.error}
          </span>
          <button type="button" onClick={tools.clearError} className="shrink-0 font-medium underline">
            知道了
          </button>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)_300px]">
        <aside className="border-line bg-panel rounded-card border p-3" aria-label="主视觉版本">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h2 className="text-ink flex items-center gap-1.5 text-[12px] font-medium">
              <Icon name="layers" size={13} className="text-ai-strong" />
              主视觉版本
            </h2>
            <span className="num text-[10px] text-faint">{versions.length}</span>
          </div>
          <div className="scrollbar-slim flex gap-2 overflow-x-auto pb-1 xl:max-h-[560px] xl:flex-col xl:overflow-y-auto xl:overflow-x-hidden">
            {versions.length === 0 ? (
              <p className="text-faint text-[11px]">还没有可交付版本。</p>
            ) : (
              versions.map((asset) => {
                const active = asset.id === session.current_asset_id
                return (
                  <button
                    key={asset.id}
                    type="button"
                    disabled={patch.isPending}
                    onClick={() => {
                      patch.mutate({ current_asset_id: asset.id })
                      setPicked(null)
                    }}
                    aria-pressed={active}
                    className={`flex w-40 shrink-0 items-center gap-2 rounded-control border p-2 text-left transition-colors duration-150 disabled:opacity-50 xl:w-full ${
                      active
                        ? 'border-ink bg-soft'
                        : 'border-line hover:border-ai-strong/60'
                    }`}
                  >
                    <span className="bg-panel-2 border-line size-12 shrink-0 overflow-hidden rounded-chip border">
                      <img src={asset.url} alt="" loading="lazy" className="size-full object-cover" />
                    </span>
                    <span className="min-w-0">
                      <span className="text-ink block truncate text-[11px] font-medium">
                        {KIND_LABELS[asset.kind]}
                        {active ? ' · 当前' : ''}
                      </span>
                      <span className="text-muted num block text-[9px]">
                        {asset.width} × {asset.height}
                      </span>
                      <span className="text-faint num block text-[9px]">
                        {formatBytes(asset.size_bytes)}
                      </span>
                    </span>
                  </button>
                )
              })
            )}
          </div>
        </aside>

        <div className="min-w-0 space-y-4">
          <section className="border-line bg-panel rounded-card border p-4" aria-label="渠道预览">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-ink text-[14px] font-semibold tracking-tight">渠道尺寸预览</h2>
                <p className="text-faint mt-0.5 text-[10px]">
                  按真实比例查看当前主视觉，缺的尺寸可直接补齐
                </p>
              </div>
              <div className="bg-panel-2 border-line inline-flex rounded-control border p-0.5" role="group" aria-label="尺寸筛选">
                {(
                  [
                    { id: 'all', label: '全部' },
                    { id: '1:1', label: '1:1' },
                    { id: '4:5', label: '4:5' },
                    { id: '9:16', label: '9:16' },
                  ] as const
                ).map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    aria-pressed={filter === item.id}
                    onClick={() => setFilter(item.id)}
                    className={`num rounded-[7px] px-2.5 py-1.5 text-[10px] font-medium transition-colors duration-150 ${
                      filter === item.id ? 'bg-panel text-ink shadow-control' : 'text-muted hover:text-ink'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            <div
              className={`mt-4 flex items-end gap-3 overflow-x-auto pb-2 ${
                shown.length === 1
                  ? 'max-w-sm lg:grid lg:grid-cols-1 lg:overflow-visible'
                  : 'lg:grid lg:grid-cols-3 lg:overflow-visible'
              }`}
            >
              {shown.map(({ channel, asset }) => (
                <ChannelCard
                  key={channel.ratio}
                  channel={channel}
                  asset={asset}
                  running={deliveryRunning(channel.ratio)}
                  disabled={tools.busy}
                  onGenerate={() =>
                    tools.invoke('prepare_delivery_sizes', { ratios: [channel.ratio] })
                  }
                />
              ))}
            </div>
          </section>

          <section className="border-line bg-panel rounded-card border p-4" aria-label="生成营销物料">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <h2 className="text-ink text-[14px] font-semibold tracking-tight">生成营销物料</h2>
                <p className="text-faint mt-0.5 text-[10px]">
                  以当前画布为参考，结果进入图片墙，不改动画布
                </p>
              </div>
              <span className="text-faint text-[10px]">生成后可在上方版本列表选用</span>
            </div>
            <input
              value={copy}
              onChange={(event) => setCopy(event.target.value)}
              disabled={tools.busy}
              placeholder="可选：海报文案或补充要求，例如「新品首发 限时 8 折」"
              className="border-line text-ink placeholder:text-faint focus:border-ai-strong rounded-control mt-3 w-full border bg-transparent px-3 py-2 text-[12px] outline-none transition-colors"
            />
            <div className="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-4">
              {MARKETING_KINDS.map((item) => {
                const running = tools.isRunning('generate_marketing', (params) => params.kind === item.id)
                return (
                  <div key={item.id} className="border-line rounded-control border p-3">
                    <p className="text-ink text-[12px] font-medium">{item.label}</p>
                    <p className="text-faint mt-1 min-h-8 text-[10px] leading-relaxed">{item.hint}</p>
                    <button
                      type="button"
                      disabled={tools.busy}
                      onClick={() =>
                        tools.invoke('generate_marketing', {
                          kind: item.id,
                          caption: copy.trim() || undefined,
                        })
                      }
                      className={`${buttonClass({ variant: 'outline', size: 'sm' })} mt-2 w-full`}
                    >
                      {running ? '生成中…' : '生成'}
                    </button>
                  </div>
                )
              })}
            </div>
          </section>

          <FileList
            session={session}
            items={items}
            selected={selected}
            disabled={pack.isPending || tools.busy}
            packing={pack.isPending}
            onToggle={toggle}
            onToggleAll={toggleAll}
            onDownload={() => download(selected)}
            error={pack.isError ? errorMessage(pack.error) : null}
          />
        </div>

        <aside className="space-y-4">
          <section className="border-line bg-panel rounded-card border p-4" aria-label="交付检查">
            <div className="flex items-start justify-between gap-2 border-b border-line pb-3">
              <div>
                <h2 className="text-ink text-[14px] font-semibold tracking-tight">交付检查</h2>
                <p className="text-faint mt-0.5 text-[10px]">只检查当前素材可确认的事实</p>
              </div>
              <span className="num text-ink text-[18px] font-semibold tracking-tight">
                {passed}/{checks.length}
              </span>
            </div>
            <ul className="mt-3 space-y-3">
              {checks.map((check) => (
                <li key={check.title} className="flex items-start gap-2.5">
                  <span
                    className={`mt-0.5 grid size-5 shrink-0 place-items-center rounded-full ${
                      check.ok ? 'bg-ai-soft text-ai-strong' : 'bg-signal-soft text-signal-ink'
                    }`}
                  >
                    <Icon name={check.ok ? 'check' : 'alert'} size={12} />
                  </span>
                  <div className="min-w-0">
                    <p className="text-ink text-[11px] font-medium">{check.title}</p>
                    <p className="text-muted mt-0.5 text-[10px] leading-relaxed">{check.detail}</p>
                  </div>
                </li>
              ))}
            </ul>
            <button
              type="button"
              disabled={selected.length === 0 || pack.isPending}
              onClick={() => download(selected)}
              className={`${buttonClass({ variant: 'signal', size: 'lg' })} mt-4 w-full`}
            >
              {pack.isPending ? '打包中…' : `生成交付包 · ${selected.length} 张`}
            </button>
            <p className="text-faint mt-2 text-center text-[9px]">包内含 manifest.json，尺寸与文件信息可追溯</p>
          </section>

          <BatchList />
        </aside>
      </div>
    </div>
  )
}

function ChannelCard({
  channel,
  asset,
  running,
  disabled,
  onGenerate,
}: {
  channel: (typeof CHANNELS)[number]
  asset?: Asset
  running: boolean
  disabled: boolean
  onGenerate: () => void
}) {
  return (
    <div className="w-[78vw] shrink-0 sm:w-[46vw] lg:w-auto">
      <div
        className={`border-line bg-panel-2 relative h-[260px] w-full overflow-hidden rounded-control border sm:h-[300px] lg:h-auto lg:[aspect-ratio:var(--frame-ratio)] ${
          asset ? '' : 'border-dashed'
        }`}
        style={{ '--frame-ratio': `${channel.width} / ${channel.height}` } as CSSProperties}
      >
        {asset ? (
          <>
            <img src={asset.url} alt="" className="size-full object-contain" />
            <span className="bg-shell/65 num absolute right-1.5 bottom-1.5 rounded-full px-1.5 py-0.5 text-[9px] text-white">
              {asset.width} × {asset.height}
            </span>
          </>
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-3 text-center">
            <span className="border-line text-faint grid size-9 place-items-center rounded-full border">
              <Icon name="image" size={16} />
            </span>
            <p className="text-faint text-[10px]">还没有这个尺寸</p>
            <button
              type="button"
              disabled={disabled}
              onClick={onGenerate}
              className={`${buttonClass({ variant: 'outline', size: 'sm' })} inline-flex items-center gap-1`}
            >
              <Icon name={running ? 'loader' : 'sparkles'} size={11} className={running ? 'animate-spin' : ''} />
              {running ? '生成中…' : '生成此尺寸'}
            </button>
          </div>
        )}
      </div>

      <div className="mt-1.5 flex min-h-9 items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-ink flex items-center gap-1.5 truncate text-[11px] font-medium">
            {channel.label}
            {asset && (
              <span className="bg-ai-soft text-ai-strong shrink-0 rounded-full px-1.5 py-0.5 text-[9px]">
                已有
              </span>
            )}
          </p>
          <p className="text-faint num truncate text-[9px]">
            {channel.ratio} · {channel.width}×{channel.height} · {channel.scene}
          </p>
        </div>
        {asset ? (
          <button
            type="button"
            disabled={disabled}
            onClick={onGenerate}
            className="text-faint hover:text-ink inline-flex shrink-0 items-center gap-1 text-[9px] transition-colors"
          >
            <Icon name={running ? 'loader' : 'refresh'} size={10} className={running ? 'animate-spin' : ''} />
            {running ? '生成中' : '重出'}
          </button>
        ) : (
          <span className="text-faint shrink-0 text-[9px]">待生成</span>
        )}
      </div>
    </div>
  )
}

function FileList({
  session,
  items,
  selected,
  disabled,
  packing,
  onToggle,
  onToggleAll,
  onDownload,
  error,
}: {
  session: SessionDetail
  items: Asset[]
  selected: string[]
  disabled: boolean
  packing: boolean
  onToggle: (id: string) => void
  onToggleAll: () => void
  onDownload: () => void
  error: string | null
}) {
  const allSelected = items.length > 0 && items.every((asset) => selected.includes(asset.id))

  return (
    <section className="border-line bg-panel rounded-card border p-4" aria-label="交付文件">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-ink text-[14px] font-semibold tracking-tight">交付文件</h2>
          <p className="text-faint mt-0.5 text-[10px]">勾选要进入导出包的文件</p>
        </div>
        <div className="flex items-center gap-2">
          {items.length > 0 && (
            <button
              type="button"
              disabled={disabled}
              onClick={onToggleAll}
              className={buttonClass({ variant: 'outline', size: 'sm' })}
            >
              {allSelected ? '取消全选' : '全选'}
            </button>
          )}
          <button
            type="button"
            disabled={disabled || selected.length === 0}
            onClick={onDownload}
            className={`${buttonClass({ variant: 'signal', size: 'sm' })} inline-flex items-center gap-1`}
          >
            <Icon name={packing ? 'loader' : 'download'} size={12} className={packing ? 'animate-spin' : ''} />
            {packing ? '处理中…' : `打包 ${selected.length} 张`}
          </button>
        </div>
      </div>
      {error && <p className="text-danger mt-2 text-[11px]">{error}</p>}
      {items.length === 0 ? (
        <p className="text-faint mt-4 text-[11px]">还没有可交付素材，先在编辑室完成一次导出。</p>
      ) : (
        <ul className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {items.map((asset) => {
            const active = selected.includes(asset.id)
            return (
              <li key={asset.id}>
                <button
                  type="button"
                  onClick={() => onToggle(asset.id)}
                  aria-pressed={active}
                  className={`w-full overflow-hidden rounded-control border-2 text-left transition-colors duration-150 ${
                    active
                      ? 'border-ink bg-soft'
                      : 'border-line bg-panel hover:border-ai-strong/60'
                  }`}
                >
                  <span className="bg-panel-2 relative block aspect-square">
                    <img src={asset.url} alt="" className="size-full object-contain" />
                    <span
                      className={`absolute top-1.5 left-1.5 grid size-5 place-items-center rounded-full border-2 ${
                        active
                          ? 'border-signal bg-signal text-signal-ink'
                          : 'border-white/90 bg-ink/30 text-transparent'
                      }`}
                      aria-hidden
                    >
                      <Icon name="check" size={11} />
                    </span>
                  </span>
                  <span className="block px-2 py-1.5">
                    <span className="text-ink num block text-[10px]">
                      {asset.width} × {asset.height}
                    </span>
                    <span className="text-faint num block truncate text-[9px]">
                      {KIND_LABELS[asset.kind]} · {formatBytes(asset.size_bytes)}
                      {asset.id === session.current_asset_id ? ' · 当前' : ''}
                    </span>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

function BatchList() {
  const { data: batches = [], isPending } = useBatches()
  const recent = batches.slice(0, 4)

  return (
    <section className="border-line bg-panel rounded-card border p-4" aria-label="最近批量任务">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-ink flex items-center gap-1.5 text-[12px] font-medium">
          <Icon name="batch" size={13} className="text-ai-strong" />
          最近批量任务
        </h2>
        <Link to="/batch" className="text-ai-strong inline-flex items-center gap-1 text-[10px]">
          批量生产
          <Icon name="arrow-right" size={11} />
        </Link>
      </div>
      {isPending ? (
        <p className="text-faint mt-3 text-[10px]">加载中…</p>
      ) : recent.length === 0 ? (
        <p className="text-faint mt-3 text-[10px] leading-relaxed">
          还没有批量任务。多张图需要同一套处理时，从批量生产开始。
        </p>
      ) : (
        <ul className="mt-2 space-y-1.5">
          {recent.map((item) => {
            const failed = item.items.filter((entry) => entry.status === 'failed').length
            const done = item.items.filter((entry) => entry.status === 'succeeded').length
            return (
              <li key={item.run.id}>
                <Link
                  to={`/batch/${item.run.id}`}
                  className="hover:bg-soft flex items-center justify-between gap-2 rounded-chip px-2 py-1.5 transition-colors"
                >
                  <span className="min-w-0">
                    <span className="text-ink block truncate text-[10px]">
                      {item.items.length} 张 · {statusLabel(item.run.status)}
                      {failed ? ` · ${failed} 张失败` : done ? ` · ${done} 张完成` : ''}
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
      )}
    </section>
  )
}

function SessionSwitch({ currentId }: { currentId: string }) {
  const navigate = useNavigate()
  const { data: sessions = [] } = useSessions()
  if (sessions.length < 2) return null
  return (
    <select
      value={currentId}
      onChange={(event) => navigate(`/marketing/${event.target.value}`)}
      className="border-line text-ink rounded-control max-w-44 shrink-0 truncate border bg-transparent px-2 py-2 text-[11px]"
      aria-label="切换项目"
    >
      {sessions.map((item) => (
        <option key={item.id} value={item.id}>
          {shortTitle(item.title)}
        </option>
      ))}
    </select>
  )
}

function findForRatio(assets: Asset[], channel: (typeof CHANNELS)[number]): Asset | undefined {
  const target = channel.width / channel.height
  const matches = assets.filter(
    (asset) =>
      asset.kind !== 'mask' &&
      asset.kind !== 'subject' &&
      asset.kind !== 'background' &&
      Math.abs(asset.width / asset.height - target) < 0.02,
  )
  return matches.sort((a, b) => score(b) - score(a))[0]
}

function score(asset: Asset) {
  if (asset.kind === 'export') return 4
  if (asset.kind === 'marketing') return 3
  if (asset.kind === 'generated') return 2
  return 1
}

function statusLabel(status: string) {
  if (status === 'succeeded') return '已完成'
  if (status === 'failed') return '失败'
  if (status === 'running') return '处理中'
  if (status === 'canceled') return '已取消'
  return '等待中'
}
