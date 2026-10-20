import { useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import type { Asset, LibraryGroup } from '@/api/assets'
import AssetLibrary from '@/components/AssetLibrary'
import GenerateForm from '@/components/GenerateForm'
import Icon from '@/components/ui/Icon'
import { buttonClass } from '@/components/ui/buttonStyles'
import { errorMessage } from '@/hooks/useAuth'
import { useAssetLibrary, useUploadAsset } from '@/hooks/useAssets'
import { useGenerate } from '@/hooks/useRun'
import { useCreateSession } from '@/hooks/useSessions'
import { formatDateTime } from '@/lib/format'
import { KIND_LABELS, ratioLabel } from '@/lib/marketing'
import { readPromptDraft, savePromptDraft } from '@/lib/promptDraft'

export default function CreatePage() {
  const navigate = useNavigate()
  const { data: groups = [], isPending, isError, refetch } = useAssetLibrary()
  const upload = useUploadAsset()
  const generate = useGenerate()
  const createSession = useCreateSession()

  const openEditor = (assetId: string) =>
    createSession.mutate(
      { current_asset_id: assetId },
      { onSuccess: (session) => navigate(`/editor/${session.id}`) },
    )

  const flatten = useMemo(() => uniqueAssets(groups), [groups])
  // 方向板优先展示高分辨率素材，避免小图标或草稿占据主位
  const boardAssets = useMemo(() => {
    const large = flatten.filter((asset) => Math.min(asset.width, asset.height) >= 480)
    return [...(large.length ? large : flatten)]
      .sort((a, b) => b.width * b.height - a.width * a.height)
      .slice(0, 3)
  }, [flatten])
  const projects = useMemo(
    () =>
      groups
        .filter((group): group is LibraryGroup & { session_id: string } => Boolean(group.session_id))
        .slice()
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
    [groups],
  )

  const openGroup = (group: LibraryGroup) => {
    if (group.session_id) navigate(`/editor/${group.session_id}`)
    else openEditor(group.cover.id)
  }

  const openAsset = (asset: Asset) => {
    const owner = groups.find((group) => group.assets.some((item) => item.id === asset.id))
    if (owner?.session_id) navigate(`/editor/${owner.session_id}`)
    else openEditor(asset.id)
  }

  return (
    <div className="mx-auto max-w-[1420px] px-5 py-6 md:px-8 md:py-8 xl:px-10">
      <header className="mb-6 flex flex-col gap-4 md:mb-7 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <p className="text-ai-strong num text-[10px] font-medium tracking-[0.18em] uppercase">
            Project desk · 项目台
          </p>
          <h1 className="text-ink mt-2 max-w-2xl text-[26px] leading-[1.16] font-semibold tracking-[-0.03em] text-balance sm:text-[32px] lg:text-[36px]">
            让一张商品图，长成一整套品牌视觉。
          </h1>
          <p className="text-muted mt-2 max-w-xl text-[13px] leading-relaxed sm:text-sm">
            先确定商品、渠道与视觉方向，再进入编辑室精修，最后统一检查并交付。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-muted num hidden text-[11px] sm:inline">
            {projects.length ? `${projects.length} 个最近项目 · ${flatten.length} 张素材` : '等待第一个项目'}
          </span>
          <Link
            to="/library"
            className={`${buttonClass({ variant: 'outline', size: 'lg' })} inline-flex items-center gap-2`}
          >
            <Icon name="upload" size={15} />
            导入素材
          </Link>
          <button
            type="button"
            onClick={() =>
              document
                .getElementById('project-brief-panel')
                ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
            }
            className={`${buttonClass({ variant: 'signal', size: 'lg' })} inline-flex items-center gap-2`}
          >
            <Icon name="plus" size={15} />
            新建项目
          </button>
        </div>
      </header>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.06fr)_minmax(340px,0.94fr)]">
        <section id="project-brief-panel" aria-label="新项目简报">
          <GenerateForm
            defaultPrompt={readPromptDraft()}
            pending={generate.isPending}
            importing={upload.isPending || createSession.isPending}
            onImport={(file) =>
              upload.mutate(file, { onSuccess: (asset) => openEditor(asset.id) })
            }
            onSubmit={(input) =>
              generate.mutate(input, {
                onSuccess: (run) => {
                  savePromptDraft('')
                  navigate(`/candidates/${run.id}`)
                },
              })
            }
          />
          {generate.isError && (
            <p className="text-danger mt-2 flex items-center gap-1.5 text-xs">
              <Icon name="alert" size={14} />
              {errorMessage(generate.error)}
            </p>
          )}
          {upload.isError && (
            <p className="text-danger mt-2 flex items-center gap-1.5 text-xs">
              <Icon name="alert" size={14} />
              {errorMessage(upload.error)}
            </p>
          )}
        </section>

        <DirectionBoard
          assets={boardAssets}
          loading={isPending}
          onOpen={openAsset}
          onOpenAll={() => navigate('/library')}
        />
      </div>

      <section className="mt-8" aria-labelledby="recent-projects">
        <SectionHead
          id="recent-projects"
          title="继续最近的项目"
          hint="按最后编辑时间排列，点开即回到编辑室"
          action={
            <Link to="/library" className="text-muted hover:text-ink inline-flex items-center gap-1 text-[11px]">
              全部素材
              <Icon name="arrow-right" size={13} />
            </Link>
          }
        />
        {isPending ? (
          <SkeletonProjects />
        ) : isError ? (
          <EmptyState
            icon="alert"
            title="素材读取失败"
            hint="检查网络或稍后再试。"
            action={
              <button
                type="button"
                onClick={() => void refetch()}
                className={`${buttonClass({ variant: 'outline', size: 'lg' })} inline-flex items-center gap-2`}
              >
                <Icon name="refresh" size={15} />
                重新加载
              </button>
            }
          />
        ) : projects.length === 0 ? (
          <EmptyState
            icon="folder"
            title="还没有进行中的项目"
            hint="导入一张原片，或在上方写清视觉方向开始第一个项目。"
            action={
              <Link to="/library" className={`${buttonClass({ variant: 'outline', size: 'lg' })} inline-flex items-center gap-2`}>
                <Icon name="image-plus" size={15} />
                打开素材库
              </Link>
            }
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {projects.slice(0, 6).map((group) => (
              <button
                key={group.session_id}
                type="button"
                onClick={() => openGroup(group)}
                className="group border-line bg-panel hover:border-ai-strong/60 flex min-h-24 items-stretch overflow-hidden rounded-card border text-left transition-colors duration-150"
              >
                <span className="bg-panel-2 relative w-28 shrink-0 overflow-hidden sm:w-32">
                  <img
                    src={group.cover.url}
                    alt=""
                    loading="lazy"
                    className="size-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
                  />
                </span>
                <span className="flex min-w-0 flex-1 flex-col justify-between p-3">
                  <span className="min-w-0">
                    <span className="text-ink block truncate text-[13px] font-medium">{group.title}</span>
                    <span className="text-muted num mt-1 block text-[10px]">
                      {group.assets.length} 张素材 · {formatDateTime(group.updated_at)}
                    </span>
                  </span>
                  <span className="text-ai-strong mt-2 inline-flex items-center gap-1 text-[11px] font-medium">
                    继续编辑
                    <Icon name="arrow-right" size={12} />
                  </span>
                </span>
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="mt-9" aria-labelledby="library-heading">
        <SectionHead
          id="library-heading"
          title="素材库"
          hint="上传原片、生成结果和最近编辑会话"
          action={
            <Link to="/library" className="text-muted hover:text-ink inline-flex items-center gap-1 text-[11px]">
              查看全部
              <Icon name="arrow-right" size={13} />
            </Link>
          }
        />
        {isPending ? (
          <p className="text-muted text-xs">加载中…</p>
        ) : groups.length === 0 ? (
          <p className="text-faint text-xs">还没有素材，先描述画面或上传一张图片。</p>
        ) : (
          <AssetLibrary
            groups={groups.slice(0, 8)}
            onOpenSession={(sessionId) => navigate(`/editor/${sessionId}`)}
            onOpenAsset={openEditor}
          />
        )}
      </section>
    </div>
  )
}

function DirectionBoard({
  assets,
  loading,
  onOpen,
  onOpenAll,
}: {
  assets: Asset[]
  loading: boolean
  onOpen: (asset: Asset) => void
  onOpenAll: () => void
}) {
  return (
    <section className="border-line bg-panel flex flex-col overflow-hidden rounded-card border" aria-label="视觉方向板">
      <header className="border-line flex items-center justify-between gap-2 border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Icon name="grid" size={15} className="text-ai-strong" />
          <h2 className="text-ink text-[12px] font-medium">视觉方向板</h2>
        </div>
        <button type="button" onClick={onOpenAll} className="text-faint hover:text-ink text-[10px] transition-colors">
          来自最近素材
        </button>
      </header>

      {loading ? (
        <div className="grid flex-1 grid-cols-2 grid-rows-[1.35fr_0.65fr] gap-2 p-3">
          <div className="bg-panel-2 animate-pulse rounded-control" />
          <div className="bg-panel-2 animate-pulse rounded-control" />
          <div className="bg-panel-2 animate-pulse rounded-control" />
        </div>
      ) : assets.length === 0 ? (
        <div className="grid flex-1 place-items-center px-6 py-12 text-center">
          <div>
            <span className="bg-ai-soft text-ai-strong mx-auto grid size-10 place-items-center rounded-full">
              <Icon name="image" size={18} />
            </span>
            <p className="text-ink mt-3 text-[13px] font-medium">方向板还空着</p>
            <p className="text-muted mt-1 text-[11px] leading-relaxed">
              上传原片或生成第一批候选后，这里会展示真实素材与比例。
            </p>
          </div>
        </div>
      ) : (
        <div className="grid flex-1 grid-cols-2 grid-rows-[1.35fr_0.65fr] gap-2 p-3">
          {[...assets, ...Array.from({ length: Math.max(0, 3 - assets.length) }, () => null)].map(
            (asset, index) =>
              asset ? (
                <button
                  key={asset.id}
                  type="button"
                  onClick={() => onOpen(asset)}
                  className={`group bg-checker relative overflow-hidden rounded-control border border-line text-left ${
                    index === 0 ? 'row-span-2' : ''
                  }`}
                >
                  <img
                    src={asset.url}
                    alt=""
                    loading="lazy"
                    className="size-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
                  />
                  <span className="bg-shell/70 absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 px-2.5 py-2 text-[10px] text-white">
                    <span className="truncate">{KIND_LABELS[asset.kind]}</span>
                    <span className="num shrink-0 rounded-full bg-white/20 px-1.5 py-0.5">
                      {ratioLabel(asset.width, asset.height)}
                    </span>
                  </span>
                </button>
              ) : (
                <div
                  key={`slot-${index}`}
                  className={`border-line bg-panel-2/40 text-faint grid place-items-center rounded-control border border-dashed ${
                    index === 0 ? 'row-span-2' : ''
                  }`}
                >
                  <div className="text-center">
                    <Icon name="sparkles" size={16} className="mx-auto text-ai-strong" />
                    <p className="mt-1 text-[10px]">待生成</p>
                  </div>
                </div>
              ),
          )}
        </div>
      )}

      <footer className="border-line text-muted flex items-center justify-between gap-2 border-t px-4 py-2.5 text-[10px]">
        <span>选定方向后，可在编辑室继续精修</span>
        <span className="text-ai-strong inline-flex items-center gap-1">
          <Icon name="sparkles" size={11} />
          真实素材
        </span>
      </footer>
    </section>
  )
}

function SectionHead({
  id,
  title,
  hint,
  action,
}: {
  id?: string
  title: string
  hint?: string
  action?: React.ReactNode
}) {
  return (
    <div className="mb-3 flex items-end justify-between gap-3">
      <div>
        <h2 id={id} className="text-ink text-[15px] font-semibold tracking-tight">
          {title}
        </h2>
        {hint && <p className="text-faint mt-0.5 text-[11px]">{hint}</p>}
      </div>
      {action}
    </div>
  )
}

function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon: 'folder' | 'alert' | 'image'
  title: string
  hint: string
  action?: React.ReactNode
}) {
  return (
    <div className="border-line bg-panel flex flex-col items-center justify-center rounded-card border border-dashed px-6 py-10 text-center">
      <span className="bg-ai-soft text-ai-strong grid size-10 place-items-center rounded-full">
        <Icon name={icon} size={18} />
      </span>
      <p className="text-ink mt-3 text-[13px] font-medium">{title}</p>
      <p className="text-muted mt-1 max-w-sm text-[11px] leading-relaxed">{hint}</p>
      {action && <div className="mt-4 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  )
}

function SkeletonProjects() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {[0, 1, 2].map((item) => (
        <div key={item} className="border-line bg-panel h-24 animate-pulse rounded-card border" />
      ))}
    </div>
  )
}

function uniqueAssets(groups: LibraryGroup[]): Asset[] {
  const seen = new Set<string>()
  const list: Asset[] = []
  for (const asset of [...groups.map((group) => group.cover), ...groups.flatMap((group) => group.assets)]) {
    if (seen.has(asset.id)) continue
    if (asset.kind === 'mask' || asset.kind === 'subject' || asset.kind === 'background') continue
    seen.add(asset.id)
    list.push(asset)
  }
  return list.sort((a, b) => b.created_at.localeCompare(a.created_at))
}
