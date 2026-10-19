import { Spinner } from '@/components/admin/ui'

/** 会话状态未确认前的占位，避免闪一下空壳再跳转 */
export default function Splash() {
  return (
    <div className="ad-root bg-ad-canvas flex h-screen items-center justify-center">
      <div className="border-ad-border bg-ad-surface flex items-center gap-2.5 border px-4 py-3 text-[13px] text-ad-muted">
        <Spinner className="size-4" />
        正在校验管理员身份…
      </div>
    </div>
  )
}
