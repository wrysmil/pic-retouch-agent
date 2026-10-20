import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import AssetLibrary from '@/components/AssetLibrary'
import ImageDropzone from '@/components/ImageDropzone'
import Icon from '@/components/ui/Icon'
import { buttonClass } from '@/components/ui/buttonStyles'
import { errorMessage } from '@/hooks/useAuth'
import { useAssetLibrary, useUploadAsset } from '@/hooks/useAssets'
import { useCreateSession } from '@/hooks/useSessions'
import { toast } from '@/stores/toasts'

type Filter = 'all' | 'session' | 'orphan'

export default function LibraryPage() {
  const navigate = useNavigate()
  const { data: groups = [], isPending, isError, refetch } = useAssetLibrary()
  const upload = useUploadAsset()
  const createSession = useCreateSession()
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<Filter>('all')

  const filtered = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    return groups.filter((group) => {
      if (filter === 'session' && !group.session_id) return false
      if (filter === 'orphan' && group.session_id) return false
      if (!keyword) return true
      return (
        group.title.toLowerCase().includes(keyword) ||
        group.assets.some((asset) => asset.id.toLowerCase().includes(keyword))
      )
    })
  }, [groups, query, filter])

  const totalAssets = groups.reduce((sum, group) => sum + group.assets.length, 0)

  const openEditor = (assetId: string) =>
    createSession.mutate(
      { current_asset_id: assetId },
      { onSuccess: (session) => navigate(`/editor/${session.id}`) },
    )

  return (
    <div className="mx-auto max-w-[1420px] px-5 py-6 md:px-8 md:py-8 xl:px-10">
      <header className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-ai-strong num text-[10px] font-medium tracking-[0.18em] uppercase">
            Asset library · 素材库
          </p>
          <h1 className="text-ink mt-2 text-[26px] leading-tight font-semibold tracking-[-0.03em] sm:text-[32px]">
            所有原片与生成结果
          </h1>
          <p className="text-muted mt-2 max-w-xl text-[13px] leading-relaxed">
            按编辑会话组织素材；未归组的原片会在打开时创建新的编辑会话。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-muted num text-[11px]">
            {groups.length} 组 · {totalAssets} 张
          </span>
          <Link to="/create" className={`${buttonClass({ variant: 'signal', size: 'lg' })} inline-flex items-center gap-2`}>
            <Icon name="plus" size={15} />
            新建项目
          </Link>
        </div>
      </header>

      <div className="mb-5 grid items-start gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.42fr)]">
        <div className="border-line bg-panel rounded-card border p-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <label className="border-line focus-within:border-ai-strong flex min-h-10 flex-1 items-center gap-2 rounded-control border px-3 transition-colors">
              <Icon name="search" size={15} className="text-faint shrink-0" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="搜索项目名称"
                aria-label="搜索素材"
                className="text-ink placeholder:text-faint min-w-0 flex-1 bg-transparent text-[12px] outline-none"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  aria-label="清除搜索"
                  className="text-faint hover:text-ink"
                >
                  <Icon name="x" size={13} />
                </button>
              )}
            </label>
            <div className="bg-panel-2 border-line inline-flex shrink-0 rounded-control border p-0.5" role="group" aria-label="素材范围">
              {(
                [
                  { id: 'all', label: '全部' },
                  { id: 'session', label: '编辑会话' },
                  { id: 'orphan', label: '未归组' },
                ] as const
              ).map((item) => (
                <button
                  key={item.id}
                  type="button"
                  aria-pressed={filter === item.id}
                  onClick={() => setFilter(item.id)}
                  className={`rounded-[7px] px-2.5 py-1.5 text-[11px] font-medium transition-colors duration-150 ${
                    filter === item.id ? 'bg-panel text-ink shadow-control' : 'text-muted hover:text-ink'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="border-line bg-panel rounded-card border p-3">
          <ImageDropzone
            compact
            label="上传到素材库"
            hint="JPG / PNG / WebP，单张不超过 20 MB"
            disabled={upload.isPending}
            onFile={(file) =>
              upload.mutate(file, {
                onSuccess: () => toast('已加入素材库'),
                onError: (error) => toast(errorMessage(error), 'danger'),
              })
            }
          />
        </div>
      </div>

      {isPending ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((item) => (
            <div key={item} className="border-line bg-panel h-28 animate-pulse rounded-card border" />
          ))}
        </div>
      ) : isError ? (
        <Empty
          title="素材读取失败"
          hint="检查网络或稍后重试。"
          action={
            <button type="button" onClick={() => void refetch()} className={buttonClass({ variant: 'outline', size: 'lg' })}>
              重新加载
            </button>
          }
        />
      ) : filtered.length === 0 ? (
        <Empty
          title={query || filter !== 'all' ? '没有匹配的素材' : '素材库还是空的'}
          hint={
            query || filter !== 'all'
              ? '换个关键词或切回全部素材。'
              : '上传一张原片，或从项目台生成第一组候选。'
          }
          action={
            query || filter !== 'all' ? (
              <button
                type="button"
                onClick={() => {
                  setQuery('')
                  setFilter('all')
                }}
                className={buttonClass({ variant: 'outline', size: 'lg' })}
              >
                查看全部素材
              </button>
            ) : (
              <Link to="/create" className={buttonClass({ variant: 'outline', size: 'lg' })}>
                去项目台
              </Link>
            )
          }
        />
      ) : (
        <AssetLibrary
          groups={filtered}
          onOpenSession={(sessionId) => navigate(`/editor/${sessionId}`)}
          onOpenAsset={openEditor}
        />
      )}
    </div>
  )
}

function Empty({
  title,
  hint,
  action,
}: {
  title: string
  hint: string
  action?: React.ReactNode
}) {
  return (
    <div className="border-line bg-panel flex flex-col items-center justify-center rounded-card border border-dashed px-6 py-16 text-center">
      <span className="bg-ai-soft text-ai-strong grid size-11 place-items-center rounded-full">
        <Icon name="library" size={20} />
      </span>
      <h2 className="text-ink mt-4 text-[15px] font-semibold">{title}</h2>
      <p className="text-muted mt-1 max-w-sm text-[12px] leading-relaxed">{hint}</p>
      {action && <div className="mt-5 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  )
}
