import { useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { agentApi, type DraftStep, type Turn } from '@/api/agent'
import { isTerminal } from '@/api/runs'
import { useRefreshQuota } from '@/hooks/useQuota'
import { recordRateLimit } from '@/stores/rateLimit'

const turnsKey = (sessionId: string) => ['session', sessionId, 'messages']

// 这些阶段后台还会继续推进，SSE 之外保留低频轮询兜底
const OPEN_PHASES = new Set(['planning', 'executing'])
const LIVE_PHASES = new Set(['planning', 'awaiting_confirmation', 'executing'])

type TurnEvent = {
  seq: number
  type: string
  payload: { turn?: Turn; draft?: DraftStep; text?: string; message?: string }
}

function mergeDraft(drafts: DraftStep[], draft: DraftStep): DraftStep[] {
  return [...drafts.filter((item) => item.call_index !== draft.call_index), draft].sort(
    (a, b) => a.call_index - b.call_index,
  )
}

/** 计划推进后画布、历史、对话都要重取，三个动作共用同一份失效逻辑。 */
function useRefreshTurn(sessionId: string) {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: turnsKey(sessionId) })
    void queryClient.invalidateQueries({ queryKey: ['session', sessionId] })
    void queryClient.invalidateQueries({ queryKey: ['session', sessionId, 'history'] })
  }
}

/**
 * 订阅最新一轮的轮次事件。快照先重建界面，草稿/计划事件再增量更新；
 * 断线由浏览器自动重连，带 after_seq 从数据库补齐。
 */
function useTurnStream(sessionId: string, turn: Turn | undefined) {
  const queryClient = useQueryClient()
  const id = turn && LIVE_PHASES.has(turn.phase) ? turn.id : null
  const streamKey = turn ? `${sessionId}:${turn.id}` : ''
  const lastEventSeq = turn?.last_event_seq ?? 0
  const afterRef = useRef({ key: streamKey, seq: lastEventSeq })

  useEffect(() => {
    if (!streamKey) return
    if (afterRef.current.key !== streamKey) {
      afterRef.current = { key: streamKey, seq: lastEventSeq }
      return
    }
    afterRef.current.seq = Math.max(afterRef.current.seq, lastEventSeq)
  }, [streamKey, lastEventSeq])

  useEffect(() => {
    if (!id) return
    const afterSeq = afterRef.current.key === streamKey ? afterRef.current.seq : 0
    const source = new EventSource(`/events/agent-runs/${id}?after_seq=${afterSeq}`)
    let timer: number | undefined
    let closed = false

    const refresh = () => {
      if (timer !== undefined) return
      timer = window.setTimeout(() => {
        timer = undefined
        void queryClient.invalidateQueries({ queryKey: turnsKey(sessionId) })
      }, 120)
    }

    source.onmessage = (event) => {
      let data: TurnEvent
      try {
        data = JSON.parse(event.data) as TurnEvent
      } catch {
        return
      }
      let needsRefresh = false
      const current = data.payload.turn
      if (current) {
        if (afterRef.current.key !== streamKey) {
          afterRef.current = { key: streamKey, seq: current.last_event_seq }
        } else {
          afterRef.current.seq = Math.max(afterRef.current.seq, current.last_event_seq)
        }
        queryClient.setQueryData<Turn[]>(turnsKey(sessionId), (turns) =>
          turns?.map((item) => (item.id === current.id ? current : item)),
        )
        needsRefresh = true
        void queryClient.invalidateQueries({ queryKey: ['session', sessionId] })
        if (isTerminal(current.status)) {
          void queryClient.invalidateQueries({ queryKey: ['session', sessionId, 'history'] })
          closed = true
          source.close()
        }
      }
      if (data.type === 'planning.step.draft' && data.payload.draft) {
        const draft = data.payload.draft
        queryClient.setQueryData<Turn[]>(turnsKey(sessionId), (turns) =>
          turns?.map((item) =>
            item.id === id
              ? { ...item, plan_draft: mergeDraft(item.plan_draft ?? [], draft) }
              : item,
          ),
        )
      }
      if (data.type === 'planning.summary.delta' && typeof data.payload.text === 'string') {
        const text = data.payload.text
        // 文字流只在前端累加，避免每个 token 都回服务端拉一次
        queryClient.setQueryData<Turn[]>(turnsKey(sessionId), (turns) =>
          turns?.map((item) => (item.id === id ? { ...item, public_summary: text } : item)),
        )
      }
      if (data.type === 'planning.failed') {
        closed = true
        source.close()
        needsRefresh = true
      }
      // 计划下发时已经预占额度，这里同步刷新可用次数
      if (data.type === 'plan.ready' || data.type === 'turn.updated') {
        void queryClient.invalidateQueries({ queryKey: ['quota', 'entitlements'] })
      }
      if (!closed && needsRefresh) refresh()
    }

    // 浏览器自身会退避重连；这里只兜底轮询，不主动重建连接
    source.onerror = () => {
      if (!closed) refresh()
    }

    return () => {
      closed = true
      source.close()
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [id, sessionId, queryClient, streamKey])
}

export function useTurns(sessionId: string) {
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: turnsKey(sessionId),
    queryFn: () => agentApi.turns(sessionId),
    // 规划/执行阶段轮询降为兜底，主要靠轮次 SSE 推进
    refetchInterval: (current) => {
      const latest = current.state.data?.at(-1)
      // SSE 是主通道；快照只负责兜底，避免任务执行时高频重复请求
      return latest && OPEN_PHASES.has(latest.phase) ? 4000 : false
    },
  })

  const latest = query.data?.at(-1)
  useTurnStream(sessionId, latest)

  const previous = useRef(latest?.status)
  useEffect(() => {
    const wasRunning = previous.current === 'running'
    previous.current = latest?.status
    if (!wasRunning || !latest?.status || !isTerminal(latest.status)) return
    void queryClient.invalidateQueries({ queryKey: ['session', sessionId] })
    void queryClient.invalidateQueries({ queryKey: ['session', sessionId, 'history'] })
  }, [latest?.status, sessionId, queryClient])

  useEffect(() => {
    previous.current = undefined
  }, [sessionId])

  return query
}

function requestId() {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

export function useSendMessage(sessionId: string) {
  const queryClient = useQueryClient()
  const refresh = useRefreshTurn(sessionId)
  const refreshQuota = useRefreshQuota()
  // 同一轮提交（含误触的第二次调用）复用同一个请求键，落定后下次发送再换新键
  const pendingId = useRef<string | null>(null)
  return useMutation({
    mutationFn: (text: string) => {
      pendingId.current ??= requestId()
      return agentApi.send(sessionId, text, pendingId.current)
    },
    onSuccess: (turn) => {
      // 先写入新轮次再刷新，避免请求已返回、列表未回填时再次并发发送。
      queryClient.setQueryData<Turn[]>(turnsKey(sessionId), (turns = []) => [
        ...turns.filter((item) => item.id !== turn.id),
        turn,
      ])
      refresh()
      refreshQuota()
    },
    onError: (error) => recordRateLimit('agent-plan', error),
    onSettled: () => {
      pendingId.current = null
    },
  })
}

export function usePlanActions(sessionId: string) {
  const refresh = useRefreshTurn(sessionId)
  const refreshQuota = useRefreshQuota()
  const after = () => {
    refresh()
    refreshQuota()
  }
  const confirm = useMutation({
    mutationFn: (turnId: string) => agentApi.confirm(sessionId, turnId),
    onSuccess: after,
  })
  const cancel = useMutation({
    mutationFn: (turnId: string) => agentApi.cancel(sessionId, turnId),
    onSuccess: after,
  })
  const retry = useMutation({
    mutationFn: (turnId: string) => agentApi.retry(sessionId, turnId),
    onSuccess: after,
  })
  return {
    confirm: (turnId: string) => {
      cancel.reset()
      retry.reset()
      confirm.mutate(turnId)
    },
    cancel: (turnId: string) => {
      confirm.reset()
      retry.reset()
      cancel.mutate(turnId)
    },
    retry: (turnId: string) => {
      confirm.reset()
      cancel.reset()
      retry.mutate(turnId)
    },
    busy: confirm.isPending || cancel.isPending || retry.isPending,
    error: confirm.error ?? cancel.error ?? retry.error,
  }
}
