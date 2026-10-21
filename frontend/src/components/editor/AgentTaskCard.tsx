import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { DraftStep, PlanStep, StepStatus, Turn } from '@/api/agent'
import { isTerminal } from '@/api/runs'
import ChatIcon from '@/components/editor/ChatIcon'
import AiBadge from '@/components/ui/AiBadge'
import ProgressBar from '@/components/ui/ProgressBar'
import { usePlanActions } from '@/hooks/useAgent'
import { errorMessage } from '@/hooks/useAuth'
import { formatResetAt, useEntitlements } from '@/hooks/useQuota'
import { hasPendingPlanSteps } from '@/lib/agentPresentation'
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

export default function AgentTaskCard({ turn, sessionId }: { turn: Turn; sessionId: string }) {
  const actions = usePlanActions(sessionId)
  const entitlements = useEntitlements()
  const completed = turn.steps.filter((step) => step.status === 'succeeded').length
  const units = turn.steps
    .filter((step) => ['waiting', 'pending'].includes(step.status))
    .reduce((sum, step) => sum + step.units, 0)
  const short = units > 0 && entitlements.data !== undefined && entitlements.data.available < units
  const canStopLater = hasPendingPlanSteps(turn.steps)
  const finished = turn.phase === 'completed'
  const body = (
    <>
      {turn.phase === 'planning' ? (
        <div className="chat-planning" role="status">
          <p>
            <span className="chat-spinner" />
            正在整理可执行的修改方案
          </p>
          {turn.plan_draft.length === 0 ? (
            <div className="chat-planning-placeholder">
              <span />
              <span />
              <small>方案准备好后，会显示在这里。</small>
            </div>
          ) : (
            <ol className="chat-step-list">
              {turn.plan_draft.map((draft, index) => (
                <DraftCard key={draft.id} draft={draft} index={index + 1} />
              ))}
            </ol>
          )}
        </div>
      ) : (
        <ol className="chat-step-list">
          {turn.steps.map((step, index) => (
            <StepCard key={step.id} step={step} index={index + 1} sessionId={sessionId} />
          ))}
        </ol>
      )}
      {!finished && (
        <div className="chat-task-actions">
          {turn.phase === 'planning' && (
            <button
              className="chat-text-button"
              disabled={actions.busy}
              onClick={() => actions.cancel(turn.id)}
            >
              取消规划
            </button>
          )}
          {turn.phase === 'awaiting_confirmation' && (
            <>
              <p className={short ? 'text-danger' : ''}>
                {units > 0
                  ? `预计消耗 ${units} 次 · 当前可用 ${entitlements.data?.available ?? '—'} 次`
                  : '不消耗生图次数'}
                {short && `，${formatResetAt(entitlements.data)}后恢复`}
              </p>
              <div>
                <button
                  className="chat-primary"
                  disabled={actions.busy || short}
                  onClick={() => actions.confirm(turn.id)}
                >
                  <ChatIcon name="spark" />
                  {actions.busy ? '正在提交…' : '按这个方案开始'}
                </button>
                <button
                  className="chat-text-button"
                  disabled={actions.busy}
                  onClick={() => actions.cancel(turn.id)}
                >
                  取消
                </button>
              </div>
            </>
          )}
          {turn.phase === 'executing' && (
            <div>
              <span className="chat-action-hint">
                {canStopLater
                  ? '当前步骤会完成，尚未开始的后续步骤可以停止'
                  : '当前步骤正在完成，暂无可停止的后续任务'}
              </span>
              {canStopLater && (
                <button
                  className="chat-text-button"
                  disabled={actions.busy}
                  onClick={() => actions.cancel(turn.id)}
                >
                  <ChatIcon name="stop" />
                  {actions.busy ? '正在停止…' : '停止后续'}
                </button>
              )}
            </div>
          )}
          {turn.phase === 'failed' && (
            <>
              <p>{turn.steps.length > 0 ? '已完成的步骤会保留，重试只处理失败的部分。' : '方案未能完成，可以重新整理；当前图片保持原样。'}</p>
              <button
                className="chat-primary"
                disabled={actions.busy}
                onClick={() => actions.retry(turn.id)}
              >
                <ChatIcon name="retry" />
                {actions.busy ? '正在提交…' : turn.steps.length > 0 ? '重试失败步骤' : '重新整理方案'}
              </button>
            </>
          )}
        </div>
      )}
      {actions.error && (
        <p className="chat-action-error" role="alert">
          {errorMessage(actions.error)}
        </p>
      )}
    </>
  )
  if (finished)
    return (
      <details className="chat-task-card chat-task-completed">
        <summary>
          <span>
            <ChatIcon name="check" />
            {completed} 项调整已完成
          </span>
          <span>
            查看过程 <ChatIcon name="chevron" />
          </span>
        </summary>
        {body}
      </details>
    )
  const title =
    turn.phase === 'planning'
      ? '先理解，再动手'
      : turn.phase === 'awaiting_confirmation'
        ? `为你准备了 ${turn.steps.length} 步方案`
        : turn.phase === 'failed'
          ? '这一步，暂时没有完成'
          : turn.phase === 'canceled'
            ? '处理已停止'
            : '正在把想法变成画面'
  return (
    <section className={`chat-task-card chat-task-${turn.phase}`} aria-label="修图任务进展">
      <header>
        <strong>{title}</strong>
        <span>
          {completed > 0 || turn.phase === 'executing'
            ? `${completed} / ${turn.steps.length} 完成`
            : turn.phase === 'awaiting_confirmation'
              ? '等你确认'
              : ''}
        </span>
      </header>
      {body}
    </section>
  )
}

function DraftCard({ draft, index }: { draft: DraftStep; index: number }) {
  return (
    <li className="chat-step chat-step-draft">
      <span className="chat-step-icon">{index}</span>
      <div className="chat-step-body">
        <strong>{draft.label}</strong>
        <small>方案草稿 · 尚未执行</small>
      </div>
    </li>
  )
}

function StepCard({
  step,
  index,
  sessionId,
}: {
  step: PlanStep
  index: number
  sessionId: string
}) {
  const queryClient = useQueryClient()
  const live = useRun(step.run_id)
  const watched = useRef(false)
  const current = live.status ?? step.status
  const running = current === 'queued' || current === 'running'
  useEffect(() => {
    if (live.status === 'queued' || live.status === 'running') watched.current = true
    if (!watched.current || !live.status || !isTerminal(live.status)) return
    watched.current = false
    void queryClient.invalidateQueries({ queryKey: ['session', sessionId] })
    void queryClient.invalidateQueries({ queryKey: ['session', sessionId, 'history'] })
    void queryClient.invalidateQueries({ queryKey: ['session', sessionId, 'messages'] })
  }, [live.status, sessionId, queryClient])
  return (
    <li className={`chat-step chat-step-${current}`}>
      <span className="chat-step-icon">
        {current === 'succeeded' ? (
          <ChatIcon name="check" />
        ) : running ? (
          <span className="chat-spinner" />
        ) : current === 'failed' ? (
          '!'
        ) : (
          index
        )}
      </span>
      <div className="chat-step-body">
        <strong>
          {step.label}
          {isAiGeneration(step.tool) && <AiBadge />}
        </strong>
        {running && (
          <>
            <small>
              {live.stage || (current === 'queued' ? '任务已提交，等待处理' : '正在处理图片')}
            </small>
            <ProgressBar value={live.progress} tone="brand" className="mt-2 h-0.5 rounded-full" />
          </>
        )}
        {live.error && <small className="text-danger">{live.error}</small>}
      </div>
      <span className="chat-step-status">
        {running ? `${Math.round(live.progress)}%` : STEP_LABEL[current]}
      </span>
    </li>
  )
}
