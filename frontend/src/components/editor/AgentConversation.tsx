import { useEffect, useRef, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import type { PlanStep, StepStatus, Turn } from '@/api/agent'
import { isTerminal } from '@/api/runs'
import Button from '@/components/ui/Button'
import ProgressBar from '@/components/ui/ProgressBar'
import { usePlanActions, useTurns } from '@/hooks/useAgent'
import { useRun } from '@/hooks/useRun'

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
    return <p className="min-h-0 flex-1 px-4 py-4 text-[11px] text-shell-muted">加载中…</p>
  }

  if (turns.length === 0) {
    return (
      <div className="min-h-0 flex-1 px-4 py-4 text-[11px] leading-relaxed text-shell-muted">
        <p>在画布底部的命令栏输入要怎么改，例如「水平翻转」或「去背景再调亮一点」。</p>
        <p className="mt-2">发送前会标明作用范围；多步计划先列出步骤，确认后才执行。</p>
      </div>
    )
  }

  return (
    <div className="scrollbar-dark min-h-0 flex-1 space-y-4 overflow-y-auto px-3 py-3">
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
      <p className="border-ai/20 bg-ai/10 text-ai ml-6 rounded-control border px-3 py-2 text-[11px] leading-relaxed">
        {turn.goal}
      </p>

      {turn.error ? (
        <p className="mr-6 text-[11px] leading-relaxed text-[#f19a8f]">{turn.error}</p>
      ) : (
        <p className="mr-6 text-[11px] leading-relaxed text-shell-ink">{turn.reply}</p>
      )}

      {turn.steps.map((step, index) => (
        <StepCard key={step.id} index={index + 1} step={step} sessionId={sessionId} />
      ))}

      <PlanActions turn={turn} sessionId={sessionId} />
    </div>
  )
}

function PlanActions({ turn, sessionId }: { turn: Turn; sessionId: string }) {
  const actions = usePlanActions(sessionId)
  if (turn.status === 'queued') {
    return (
      <div className="mr-6 flex gap-1.5">
        <Action strong disabled={actions.busy} onClick={() => actions.confirm(turn.id)}>
          执行计划
        </Action>
        <Action disabled={actions.busy} onClick={() => actions.cancel(turn.id)}>
          取消
        </Action>
      </div>
    )
  }
  if (turn.status === 'running') {
    return (
      <div className="mr-6">
        <Action disabled={actions.busy} onClick={() => actions.cancel(turn.id)}>
          取消后续
        </Action>
      </div>
    )
  }
  if (turn.status === 'failed') {
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
  strong,
  onClick,
}: {
  children: ReactNode
  disabled?: boolean
  strong?: boolean
  onClick: () => void
}) {
  return (
    <Button
      variant={strong ? 'signal' : 'outline'}
      size="sm"
      tone="dark"
      disabled={disabled}
      onClick={onClick}
    >
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
    <div className="border-shell-line bg-shell-3/55 mr-6 rounded-control border px-3 py-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[11px] font-medium text-shell-ink">
          <span className="num mr-1 text-ai">{index}</span>
          {step.label}
        </span>
        <span className="num shrink-0 text-[10px] text-shell-muted">
          {running ? `${progress}%` : STEP_LABEL[current]}
        </span>
      </div>

      {running && (
        <>
          <ProgressBar value={progress} tone="signal" className="mt-2 h-0.5 rounded-full" />
          <p className="mt-1.5 text-[10px] text-shell-muted">{stage}</p>
        </>
      )}

      {error && <p className="mt-1.5 text-[10px] leading-relaxed text-[#f19a8f]">{error}</p>}
    </div>
  )
}
