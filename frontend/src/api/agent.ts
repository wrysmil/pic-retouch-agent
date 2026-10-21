import { api } from '@/api/client'
import type { RunStatus } from '@/api/runs'

export type StepStatus =
  | 'pending'
  | 'waiting'
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'canceled'

export type PlanStep = {
  id: string
  tool: string
  label: string
  depends_on: string[]
  run_id: string | null
  status: StepStatus
  units: number
}

export type DraftStep = {
  call_index: number
  id: string
  tool: string
  label: string
  params: Record<string, unknown>
  state: 'draft'
}

export type TurnPhase =
  | 'planning'
  | 'awaiting_confirmation'
  | 'executing'
  | 'completed'
  | 'failed'
  | 'canceled'
  | 'needs_attention'

export type Turn = {
  id: string
  revision: number
  goal: string
  reply: string
  status: RunStatus
  phase: TurnPhase
  public_summary: string
  plan_version: number
  planning_attempt: number
  last_event_seq: number
  error: string | null
  created_at: string
  steps: PlanStep[]
  plan_draft: DraftStep[]
}

export const agentApi = {
  turns: (sessionId: string) => api.get<Turn[]>(`/sessions/${sessionId}/messages`),
  turn: (sessionId: string, turnId: string) =>
    api.get<Turn>(`/sessions/${sessionId}/messages/${turnId}`),
  send: (sessionId: string, text: string, requestId?: string) =>
    api.post<Turn>(`/sessions/${sessionId}/messages`, {
      text,
      request_id: requestId,
    }),
  confirm: (sessionId: string, turnId: string) =>
    api.post<Turn>(`/sessions/${sessionId}/messages/${turnId}/confirm`),
  cancel: (sessionId: string, turnId: string) =>
    api.post<Turn>(`/sessions/${sessionId}/messages/${turnId}/cancel`),
  retry: (sessionId: string, turnId: string) =>
    api.post<Turn>(`/sessions/${sessionId}/messages/${turnId}/retry`),
}