import { formatResetAt, useEntitlements, useEstimate } from '@/hooks/useQuota'

/** 提交前的次数提示：预计消耗与当前可用。只提示，最终以后端预占为准。 */
export default function QuotaCost({
  tool,
  params,
  className = '',
}: {
  tool: string
  params: Record<string, unknown>
  className?: string
}) {
  const estimate = useEstimate(tool, params)
  const entitlements = useEntitlements()
  if (!estimate.data) return null

  const short = !estimate.data.affordable
  return (
    <p
      className={`text-[10px] leading-relaxed ${short ? 'text-danger' : 'text-faint'} ${className}`}
    >
      预计 {estimate.data.required} 次 · 可用 {estimate.data.available} 次
      {short && `，${formatResetAt(entitlements.data)}后恢复`}
    </p>
  )
}

export function useAffordable(tool: string, params: Record<string, unknown>) {
  const estimate = useEstimate(tool, params)
  return {
    short: Boolean(estimate.data && !estimate.data.affordable),
    required: estimate.data?.required ?? 0,
    available: estimate.data?.available,
  }
}
