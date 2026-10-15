import { Navigate, Outlet } from 'react-router-dom'

import { useCurrentUser } from '@/hooks/useAuth'

/** 仅允许管理员通过；普通用户重定向到首页，未登录跳登录。 */
export default function RequireAdmin() {
  const { user, isLoading } = useCurrentUser()
  if (isLoading) {
    return <div className="text-muted flex h-screen items-center justify-center text-sm">加载中…</div>
  }
  if (!user) return <Navigate to="/auth" replace />
  if (user.role !== 'admin') return <Navigate to="/" replace />
  return <Outlet />
}