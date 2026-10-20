import { Navigate, Outlet } from 'react-router-dom'

import { useCurrentAdmin } from '@/hooks/useAdminAuth'
import { Button } from '@/components/admin/ui'
import { WORKBENCH_URL } from './config'
import Splash from './Splash'

/** 后台准入：未登录去 /login，已登录但非管理员停在 403 页，不再像从前那样甩回工作台首页。 */
export default function RequireAdmin() {
  const { user, isLoading } = useCurrentAdmin()

  if (isLoading) return <Splash />
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== 'admin') return <Forbidden username={user.username} />
  return <Outlet />
}

function Forbidden({ username }: { username: string }) {
  return (
    <div className="ad-root bg-ad-canvas flex h-screen items-center justify-center p-6">
      <div className="border-ad-border bg-ad-surface w-full max-w-sm border">
        <header className="border-ad-border bg-ad-surface-2 border-b px-4 py-2.5">
          <h1 className="text-ad-ink text-[13px] font-semibold">403 · 无后台访问权限</h1>
          <p className="text-ad-faint mt-0.5 text-[11px]">当前账号不是管理员</p>
        </header>
        <div className="space-y-3 p-4">
          <p className="text-ad-muted text-[13px]">
            账号 <span className="font-ad-mono text-ad-ink">{username}</span>{' '}
            已被拒绝访问本控制台。如需开通，请让已有管理员在「用户管理」中把角色改为管理员。
          </p>
          <div className="flex gap-2">
            <Button variant="primary" onClick={() => window.location.assign(WORKBENCH_URL)}>
              返回工作台
            </Button>
            <Button variant="default" onClick={() => window.location.assign('/login')}>
              换个账号
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
