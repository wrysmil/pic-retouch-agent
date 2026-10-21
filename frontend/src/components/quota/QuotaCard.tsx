import ProgressBar from '@/components/ui/ProgressBar'
import { formatResetAt, useEntitlements } from '@/hooks/useQuota'

/**
 * 侧栏账号区里的免费会员额度卡。
 * 只读：不出现升级、购买或充值入口；VIP 明确标注「即将开放」。
 */
export default function QuotaCard() {
  const { data, isPending, isError } = useEntitlements()

  if (isPending) {
    return (
      <div className="border-line min-w-[176px] rounded-[12px] border px-3 py-2.5" aria-hidden>
        <div className="bg-soft h-2.5 w-16 animate-pulse rounded" />
        <div className="bg-soft mt-2 h-1 w-full animate-pulse rounded" />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <p className="text-faint min-w-[176px] px-1 text-[10px] leading-relaxed">
        额度信息暂不可用
      </p>
    )
  }

  const used = data.consumed + data.reserved
  const percent = data.daily_limit > 0 ? Math.min(100, (used / data.daily_limit) * 100) : 100
  const empty = data.available <= 0

  return (
    <>
      {/* 收起态：仍能看到剩余次数，悬停侧栏后展开完整额度卡 */}
      <div className="flex justify-center group-hover:hidden group-focus-within:hidden">
        <span
          className={`grid size-7 place-items-center rounded-full text-[11px] font-semibold tabular-nums ${
            empty ? 'bg-danger/10 text-danger' : 'bg-brand-soft text-brand-strong'
          }`}
          title={`免费会员 · 今日剩余 ${data.available} 次`}
          aria-label={`免费会员，今日剩余 ${data.available} 次`}
        >
          {data.available}
        </span>
      </div>

      <div
        className="border-line bg-canvas/70 hidden min-w-[176px] rounded-[12px] border px-3 py-2.5 group-hover:block group-focus-within:block"
        aria-label={`免费会员，今日剩余 ${data.available} 次`}
      >
        <div className="flex items-center justify-between gap-2">
        <span className="text-ink text-[11px] font-semibold">免费会员</span>
        <span
          className={`text-[11px] font-semibold tabular-nums ${
            empty ? 'text-danger' : 'text-brand-strong'
          }`}
        >
          {empty ? '已用完' : `剩 ${data.available} 次`}
        </span>
      </div>

      <ProgressBar
        value={percent}
        tone="brand"
        className="mt-2 h-1 overflow-hidden rounded-full"
      />

      <p className="text-faint mt-1.5 text-[10px] leading-relaxed">
        {empty
          ? `${formatResetAt(data)}，届时恢复 ${data.daily_limit} 次`
          : `今日 ${data.consumed} 已用${data.reserved ? ` · ${data.reserved} 处理中` : ''} · 每日 ${data.daily_limit} 次`}
      </p>
        <p className="text-faint/90 mt-1 border-t border-line/70 pt-1.5 text-[10px] leading-relaxed">
          VIP 会员 · 即将开放
        </p>
      </div>
    </>
  )
}
