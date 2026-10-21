import { useMemo } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { isQuotaExhausted } from '@/api/client'
import { quotaApi } from '@/api/quota'

const ENTITLEMENTS_KEY = ['quota', 'entitlements']

export function useEntitlements() {
  return useQuery({
    queryKey: ENTITLEMENTS_KEY,
    queryFn: quotaApi.entitlements,
    // 额度会因别的标签页或后台任务变化，回到页面时重新取一次
    staleTime: 20_000,
    refetchOnWindowFocus: true,
    retry: 1,
  })
}

export function useEstimate(
  tool: string,
  params: Record<string, unknown>,
  enabled = true,
) {
  const key = useMemo(() => JSON.stringify(params), [params])
  return useQuery({
    queryKey: ['quota', 'estimate', tool, key],
    queryFn: () => quotaApi.estimate(tool, params),
    enabled,
    staleTime: 10_000,
  })
}

/** 提交成功或任务结束后刷新权益；多个入口共用同一份缓存。 */
export function useRefreshQuota() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: ENTITLEMENTS_KEY })
    void queryClient.invalidateQueries({ queryKey: ['quota', 'ledger'] })
  }
}

type ResetInfo = { reset_at: string; timezone: string }

export function formatResetAt(entitlements: ResetInfo | undefined): string {
  if (!entitlements) return '每日 00:00 重置'
  const date = new Date(entitlements.reset_at)
  const label = new Intl.DateTimeFormat('zh-CN', {
    timeZone: entitlements.timezone,
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
  return `${label} 重置`
}

export function quotaErrorMessage(error: unknown, fallback: string) {
  if (isQuotaExhausted(error)) {
    const reset = error.detail?.reset_at
      ? formatResetAt({ reset_at: error.detail.reset_at, timezone: 'Asia/Shanghai' })
      : '明日 00:00 重置'
    return `今日免费次数已用完，${reset}`
  }
  return error instanceof Error ? error.message : fallback
}
