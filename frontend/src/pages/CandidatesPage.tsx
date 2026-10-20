import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import type { Asset } from '@/api/assets'
import Icon from '@/components/ui/Icon'
import ProgressBar from '@/components/ui/ProgressBar'
import { buttonClass } from '@/components/ui/buttonStyles'
import { useRun } from '@/hooks/useRun'
import { useCreateSession } from '@/hooks/useSessions'
import { formatBytes } from '@/lib/format'
import { readProjectTitle, saveProjectTitle, savePromptDraft } from '@/lib/promptDraft'

export default function CandidatesPage() {
  const { runId = '' } = useParams()
  const navigate = useNavigate()
  const [picked, setPicked] = useState<string | null>(null)
  const { status, progress, stage, error, prompt, candidates, notFound } = useRun(runId || null)
  const createSession = useCreateSession()

  const backToBrief = () => {
    if (prompt) savePromptDraft(prompt)
    navigate('/create')
  }

  // 采用一张进入编辑，同批其余候选一并带进会话图片墙
  const adopt = () => {
    if (!picked) return
    createSession.mutate(
      {
        current_asset_id: picked,
        asset_ids: candidates.map((asset) => asset.id),
        title: readProjectTitle() || prompt || undefined,
      },
      {
        onSuccess: (session) => {
          saveProjectTitle('')
          navigate(`/editor/${session.id}`)
        },
      },
    )
  }

  if (notFound) {
    return (
      <Centered
        icon="alert"
        title="任务不存在"
        hint="链接可能已失效，回到项目台重新开始。"
        action={
          <Link to="/create" className={`${buttonClass({ variant: 'signal', size: 'lg' })} inline-flex`}>
            回到项目台
          </Link>
        }
      />
    )
  }

  if (status === 'failed' || status === 'canceled') {
    return (
      <Centered
        icon="alert"
        title={status === 'canceled' ? '生成已取消' : '这次生成没有完成'}
        hint={error ?? '未知原因'}
        action={
          <>
            <button
              type="button"
              onClick={backToBrief}
              className={`${buttonClass({ variant: 'signal', size: 'lg' })} inline-flex items-center gap-2`}
            >
              <Icon name="refresh" size={15} />
              带着简报重试
            </button>
            <Link to="/create" className={buttonClass({ variant: 'outline', size: 'lg' })}>
              回到项目台
            </Link>
          </>
        }
      />
    )
  }

  if (status !== 'succeeded') {
    return <Progress percent={progress} stage={stage} prompt={prompt} />
  }

  const selected = candidates.find((asset) => asset.id === picked)

  return (
    <div className="mx-auto max-w-[1420px] px-5 pt-6 pb-28 md:px-8 md:pt-8 xl:px-10">
      <header className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <p className="text-ai-strong num text-[10px] font-medium tracking-[0.18em] uppercase">
            Direction review · 候选方向
          </p>
          <h1 className="text-ink mt-2 text-[26px] leading-tight font-semibold tracking-[-0.03em] sm:text-[32px]">
            选出这次的主视觉
          </h1>
          <p className="text-muted mt-2 max-w-2xl text-[13px] leading-relaxed">
            {prompt ? `“${prompt}”` : '本批候选图已完成。'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="border-line text-muted num rounded-full border px-2.5 py-1 text-[10px]">
            {candidates.length} 张候选
          </span>
          <button
            type="button"
            onClick={backToBrief}
            className={`${buttonClass({ variant: 'outline', size: 'lg' })} inline-flex items-center gap-2`}
          >
            <Icon name="undo" size={15} />
            调整简报
          </button>
        </div>
      </header>

      {candidates.length === 0 ? (
        <Centered
          icon="image"
          title="没有可用候选"
          hint="这次任务没有返回图片，带着简报重试或换一种描述。"
          action={
            <button
              type="button"
              onClick={backToBrief}
              className={`${buttonClass({ variant: 'signal', size: 'lg' })} inline-flex`}
            >
              重新描述
            </button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {candidates.map((asset, index) => (
            <Candidate
              key={asset.id}
              asset={asset}
              index={index}
              selected={picked === asset.id}
              onSelect={() => setPicked(asset.id)}
            />
          ))}
        </div>
      )}

      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-panel/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:pl-[208px] xl:pl-[232px]">
        <div className="mx-auto flex max-w-[1420px] flex-wrap items-center gap-3 px-5 py-3 md:px-8 xl:px-10">
          <div className="min-w-0 flex-1">
            <p className="text-ink truncate text-[12px] font-medium">
              {selected ? `已选第 ${candidates.indexOf(selected) + 1} 张` : '点选一张候选作为当前主视觉'}
            </p>
            <p className="text-faint mt-0.5 text-[10px]">
              其余候选会保留在编辑室图片墙，随时可切换
            </p>
          </div>
          <button
            type="button"
            disabled={!picked || createSession.isPending}
            onClick={adopt}
            className={`${buttonClass({ variant: 'signal', size: 'lg' })} inline-flex shrink-0 items-center gap-2`}
          >
            {createSession.isPending ? (
              <Icon name="loader" size={15} className="animate-spin" />
            ) : (
              <Icon name="arrow-right" size={15} />
            )}
            {createSession.isPending ? '打开中…' : '进入编辑室'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Candidate({
  asset,
  index,
  selected,
  onSelect,
}: {
  asset: Asset
  index: number
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`group bg-panel block overflow-hidden rounded-card border text-left transition-colors duration-150 ${
        selected
          ? 'border-ink shadow-lift'
          : 'border-line hover:border-ai-strong/70'
      }`}
    >
      <div className="bg-panel-2 relative aspect-square">
        <img
          src={asset.url}
          alt={`候选图 ${index + 1}`}
          loading="lazy"
          className="size-full object-contain"
        />
        <span className="num bg-panel/90 text-ink absolute top-2 left-2 rounded-full px-2 py-0.5 text-[10px] font-medium">
          {String(index + 1).padStart(2, '0')}
        </span>
        {selected && (
          <span className="bg-signal text-signal-ink absolute top-2 right-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold">
            <Icon name="check" size={11} />
            已选
          </span>
        )}
      </div>
      <div className="flex items-center justify-between gap-2 px-3 py-2">
        <span className="text-muted num text-[10px]">
          {asset.width} × {asset.height} · {asset.image_format.toUpperCase()}
        </span>
        <span className="text-faint num text-[10px]">{formatBytes(asset.size_bytes)}</span>
      </div>
    </button>
  )
}

function Progress({
  percent,
  stage,
  prompt,
}: {
  percent: number
  stage: string
  prompt: string | null
}) {
  return (
    <div className="mx-auto flex min-h-[70vh] max-w-2xl flex-col justify-center px-6 py-16">
      <p className="text-ai-strong num text-[10px] font-medium tracking-[0.18em] uppercase">
        Rendering · 生成中
      </p>
      <h1 className="text-ink mt-3 text-[26px] leading-tight font-semibold tracking-[-0.03em] sm:text-[32px]">
        正在展开视觉方向
      </h1>
      {prompt && <p className="text-muted mt-3 line-clamp-3 text-sm leading-relaxed">{prompt}</p>}
      <div className="mt-7">
        <div className="text-muted num mb-2 flex items-center justify-between text-[11px]">
          <span>{stage || '任务已提交，正在排队'}</span>
          <span>{percent}%</span>
        </div>
        <ProgressBar value={percent} tone="brand" className="h-1 rounded-full" />
      </div>
      <p className="text-faint mt-4 text-[11px]">
        页面会在完成后自动展示候选，可以离开再回来。
      </p>
    </div>
  )
}

function Centered({
  icon,
  title,
  hint,
  action,
}: {
  icon: 'alert' | 'image'
  title: string
  hint: string
  action?: React.ReactNode
}) {
  return (
    <div className="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center px-6 py-16 text-center">
      <span className="bg-ai-soft text-ai-strong grid size-11 place-items-center rounded-full">
        <Icon name={icon} size={20} />
      </span>
      <h1 className="text-ink mt-4 text-xl font-semibold tracking-tight">{title}</h1>
      <p className="text-muted mt-2 text-sm leading-relaxed">{hint}</p>
      {action && <div className="mt-5 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  )
}
