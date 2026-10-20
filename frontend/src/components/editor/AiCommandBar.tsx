import { useState } from 'react'

import Icon from '@/components/ui/Icon'
import ProgressBar from '@/components/ui/ProgressBar'
import { useSendMessage, useTurns } from '@/hooks/useAgent'
import { errorMessage } from '@/hooks/useAuth'

/** 画布浮动命令栏：发送前始终显示本次作用范围，执行时显示真实阶段。 */
export default function AiCommandBar({
  sessionId,
  scope,
  busy,
  stage,
  progress,
}: {
  sessionId: string
  scope: string
  busy: boolean
  stage: string
  progress: number
}) {
  const [text, setText] = useState('')
  const send = useSendMessage(sessionId)
  const { data: turns = [] } = useTurns(sessionId)
  const planActive = turns.some((turn) => turn.status === 'queued' || turn.status === 'running')
  const latest = turns.at(-1)
  const canSend = text.trim().length > 0 && !send.isPending && !planActive

  const submit = () => {
    if (!canSend) return
    send.mutate(text.trim(), { onSuccess: () => setText('') })
  }

  return (
    <div className="pointer-events-none absolute inset-x-3 bottom-3 z-20 flex justify-center">
      <div className="pointer-events-auto w-full max-w-[660px]">
        {(busy || planActive) && (
          <div className="bg-shell/90 mb-1.5 rounded-control px-3 py-1.5 backdrop-blur">
            <div className="flex items-center justify-between gap-2 text-[10px]">
              <span className="flex min-w-0 items-center gap-1.5 text-ai">
                <Icon name="sparkles" size={11} className="shrink-0" />
                <span className="truncate">
                  {busy
                    ? `${stage || '处理中'}${progress ? ` · ${progress}%` : ''}`
                    : latest?.status === 'queued'
                      ? '计划已生成，等待确认'
                      : '计划执行中'}
                </span>
              </span>
              {busy && progress > 0 && <span className="num text-shell-muted">{progress}%</span>}
            </div>
            {busy && progress > 0 && (
              <ProgressBar value={progress} tone="signal" className="mt-1 h-0.5 rounded-full" />
            )}
          </div>
        )}

        <div className="border-shell-line bg-shell/95 shadow-float grid grid-cols-[minmax(0,1fr)_auto] items-center gap-1.5 rounded-card border p-1.5 backdrop-blur-md sm:grid-cols-[auto_minmax(0,1fr)_auto]">
          <span className="col-span-2 flex min-w-0 items-center gap-1.5 border-b border-shell-line px-2 pt-0.5 pb-1.5 sm:col-span-1 sm:border-r sm:border-b-0 sm:py-0 sm:pr-2.5 sm:pl-1">
            <span className="text-signal shrink-0 text-[9px] tracking-[0.08em]">作用范围</span>
            <span className="text-shell-ink min-w-0 truncate text-[10px]">{scope}</span>
          </span>
          <input
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault()
                submit()
              }
            }}
            disabled={planActive}
            aria-label="AI 编辑指令"
            placeholder={
              planActive ? '当前计划进行中，确认或等它结束后再发' : '描述要怎么改，例如：让背景更暖，保留标签…'
            }
            className="text-shell-ink placeholder:text-shell-muted min-w-0 bg-transparent px-1.5 py-1.5 text-[12px] outline-none disabled:cursor-not-allowed"
          />
          <button
            type="button"
            onClick={submit}
            disabled={!canSend}
            aria-label="发送指令"
            title="发送指令"
            className="bg-signal text-signal-ink hover:bg-[#e4ff96] grid size-9 shrink-0 place-items-center rounded-control transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Icon name={send.isPending ? 'loader' : 'arrow-up'} size={16} className={send.isPending ? 'animate-spin' : ''} />
          </button>
        </div>

        {send.isError && (
          <p className="bg-danger/95 mt-1.5 rounded-control px-3 py-1.5 text-[10px] text-white">
            {errorMessage(send.error)}
          </p>
        )}
      </div>
    </div>
  )
}
