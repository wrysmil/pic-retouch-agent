import { useEffect, useRef, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import type { DraftStep, PlanStep, StepStatus, Turn } from '@/api/agent'
import { isTerminal } from '@/api/runs'
import AiBadge from '@/components/ui/AiBadge'
import Button from '@/components/ui/Button'
import Markdown from '@/components/ui/Markdown'
import ProgressBar from '@/components/ui/ProgressBar'
import { usePlanActions, useTurns } from '@/hooks/useAgent'
import { formatResetAt, useEntitlements } from '@/hooks/useQuota'
import { useRun } from '@/hooks/useRun'
import { isAiGeneration } from '@/lib/tools'

const STEP_LABEL: Record<StepStatus, string> = {
  pending: '等待中',
  waiting: '待确认',
  queued: '排队中',
  running: '进行中',
  succeeded: '已完成',
  failed: '未完成',
  canceled: '已取消',
}

export default function AgentConversation({ sessionId }: { sessionId: string }) {
  const { data: turns = [], isPending } = useTurns(sessionId)
  const end = useRef<HTMLDivElement>(null)
  const latest = turns.at(-1)

  // 块体而非简写：新版浏览器的 scrollIntoView 返回 Promise，
  // 简写会把它当成 effect 的清理函数，下一次重跑时 React 调用它就崩了
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [turns.length, latest?.status])

  if (isPending) {
    return <p className="text-faint min-h-0 flex-1 px-4 py-4 text-xs">加载中…</p>
  }

  if (turns.length === 0) {
    return (
      <p className="text-faint min-h-0 flex-1 px-4 py-4 text-xs leading-relaxed">
        用一句话说明要怎么改，例如「水平翻转」或「去背景再调亮一点」。多步计划会先列出再执行。
      </p>
    )
  }

  return (
    <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-3 py-3">
      {turns.map((turn) => (
        <TurnBlock key={turn.id} turn={turn} sessionId={sessionId} />
      ))}
      <div ref={end} />
    </div>
  )
}

function TurnBlock({ turn, sessionId }: { turn: Turn; sessionId: string }) {
  return (
    <div className="space-y-2">
      <p className="bg-brand-soft text-brand-strong ml-6 rounded-[12px] px-3 py-2 text-xs leading-relaxed">
        {turn.goal}
      </p>

      {turn.error ? (
        <p className="text-danger mr-6 text-xs leading-relaxed">{turn.error}</p>
      ) : turn.phase === 'planning' ? (
        <PlanningBlock turn={turn} />
      ) : (
        <Markdown text={turn.reply} className="mr-6 text-xs" />
      )}

      {turn.steps.map((step, index) => (
        <StepCard key={step.id} index={index + 1} step={step} sessionId={sessionId} />
      ))}

      <PlanActions turn={turn} sessionId={sessionId} />
    </div>
  )
}

// 后端在轮次刚创建时先放这句占位，真正的公开说明会随后流式覆盖它
const PLANNING_PLACEHOLDER = '正在安排…'

function PlanningBlock({ turn }: { turn: Turn }) {
  const text =
    turn.public_summary && turn.public_summary !== PLANNING_PLACEHOLDER
      ? turn.public_summary
      : ''
  return (
    <div className="mr-6 space-y-1.5">
      <div className="text-ink flex items-baseline gap-1 text-xs leading-relaxed">
        {!text && (
          <span className="bg-brand relative mr-0.5 inline-flex size-1.5 self-center" aria-hidden>
            <span className="bg-brand absolute inline-flex size-full animate-ping rounded-full opacity-50" />
            <span className="bg-brand relative inline-flex size-1.5 rounded-full" />
          </span>
        )}
        <Markdown text={text || PLANNING_PLACEHOLDER} className="min-w-0 flex-1" />
        <span
          className="bg-brand-strong ml-0.5 inline-block h-3 w-[2px] translate-y-[1px] animate-pulse self-center"
          aria-hidden
        />
      </div>
      {turn.plan_draft.map((draft, index) => (
        <DraftCard key={draft.id} index={index + 1} draft={draft} />
      ))}
    </div>
  )
}

function DraftCard({ index, draft }: { index: number; draft: DraftStep }) {
  const prompt =
    typeof draft.params.prompt === 'string' ? draft.params.prompt : null
  const count = typeof draft.params.count === 'number' ? draft.params.count : null
  return (
    <div className="border-line mr-6 rounded-[12px] border border-dashed px-3 py-2 opacity-80">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-muted text-xs font-medium">
          {index}. {draft.label}
        </span>
        <span className="text-faint shrink-0 text-[10px]">草稿 · 尚未校验</span>
      </div>
      {(prompt || count) && (
        <p className="text-faint mt-1 truncate text-[10px]">
          {prompt}
          {count ? `${prompt ? ' · ' : ''}${count} 张` : ''}
        </p>
      )}
    </div>
  )
}

function PlanActions({ turn, sessionId }: { turn: Turn; sessionId: string }) {
  const actions = usePlanActions(sessionId)
  const entitlements = useEntitlements()
  if (turn.phase === 'planning') {
    return (
      <div className="mr-6">
        <Action disabled={actions.busy} onClick={() => actions.cancel(turn.id)}>
          取消规划
        </Action>
      </div>
    )
  }
  if (turn.phase === 'awaiting_confirmation') {
    const units = turn.steps
      .filter((step) => step.status === 'waiting' || step.status === 'pending')
      .reduce((sum, step) => sum + step.units, 0)
    const available = entitlements.data?.available
    const short = units > 0 && available !== undefined && available < units
    return (
      <div className="mr-6 space-y-1.5">
        <div className="flex gap-1.5">
          <Action
            disabled={actions.busy || short}
            onClick={() => actions.confirm(turn.id)}
          >
            执行计划
          </Action>
          <Action disabled={actions.busy} onClick={() => actions.cancel(turn.id)}>
            取消
          </Action>
        </div>
        <p className={`text-[10px] leading-relaxed ${short ? 'text-danger' : 'text-muted'}`}>
          预计消耗 {units} 次 · 可用 {available ?? '—'} 次
          {short && `，${formatResetAt(entitlements.data)}后恢复`}
        </p>
      </div>
    )
  }
  if (turn.phase === 'executing') {
    return (
      <div className="mr-6">
        <Action disabled={actions.busy} onClick={() => actions.cancel(turn.id)}>
          取消后续
        </Action>
      </div>
    )
  }
  if (turn.phase === 'failed') {
    return (
      <div className="mr-6">
        <Action disabled={actions.busy} onClick={() => actions.retry(turn.id)}>
          重试失败步骤
        </Action>
      </div>
    )
  }
  return null
}

function Action({
  children,
  disabled,
  onClick,
}: {
  children: ReactNode
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <Button variant="outline" size="sm" disabled={disabled} onClick={onClick}>
      {children}
    </Button>
  )
}

function StepCard({
  index,
  step,
  sessionId,
}: {
  index: number
  step: PlanStep
  sessionId: string
}) {
  const queryClient = useQueryClient()
  const { status, progress, stage, error } = useRun(step.run_id)
  const watched = useRef(false)
  // SSE 只覆盖正在跑的这一步；排队、待确认这些还没开跑的状态由计划本身给出
  const current = status ?? step.status
  const running = current === 'queued' || current === 'running'

  useEffect(() => {
    if (status === 'queued' || status === 'running') watched.current = true
    if (!watched.current || !status || !isTerminal(status)) return
    watched.current = false
    void queryClient.invalidateQueries({ queryKey: ['session', sessionId] })
    void queryClient.invalidateQueries({ queryKey: ['session', sessionId, 'history'] })
    void queryClient.invalidateQueries({ queryKey: ['session', sessionId, 'messages'] })
  }, [status, sessionId, queryClient])

  return (
    <div className="border-line mr-6 rounded-[12px] border px-3 py-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-ink inline-flex flex-wrap items-center gap-1.5 text-xs font-medium">
          {index}. {step.label}
          {isAiGeneration(step.tool) && <AiBadge />}
        </span>
        <span className="text-faint shrink-0 text-[10px] tabular-nums">
          {running ? `${progress}%` : STEP_LABEL[current]}
        </span>
      </div>

      {running && (
        <>
          <ProgressBar value={progress} className="mt-2 h-0.5 rounded-full" />
          <p className="text-faint mt-1.5 text-[10px]">{stage}</p>
        </>
      )}

      {error && <p className="text-danger mt-1.5 text-[10px] leading-relaxed">{error}</p>}
    </div>
  )
}
