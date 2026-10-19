import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { errorMessage, useAuthActions, useCurrentUser } from '@/hooks/useAuth'
import { Alert, Button, Field, inputCls } from '@/components/admin/ui'
import { WORKBENCH_URL } from './config'
import Splash from './Splash'

/** 后台专用登录页：与工作台的 /auth 完全独立，只接受管理员账号。 */
export default function AdminLoginPage() {
  const { user, isLoading } = useCurrentUser()
  const { login, logout } = useAuthActions()
  const navigate = useNavigate()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  if (isLoading) return <Splash />
  if (user?.role === 'admin') return <Navigate to="/" replace />

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    login.mutate(
      { username, password },
      {
        onSuccess: (u) => {
          if (u.role === 'admin') {
            navigate('/', { replace: true })
            return
          }
          // 普通用户即使登录成功也进不来，立刻退出把会话还原干净
          logout.mutate(undefined, {
            onSettled: () => setError('该账号不是管理员，请使用管理员账号登录'),
          })
        },
        onError: (e) => setError(errorMessage(e)),
      },
    )
  }

  return (
    <div className="ad-root bg-ad-sidebar flex min-h-screen flex-col items-center justify-center p-6">
      <div className="w-full max-w-[360px]">
        <div className="mb-5 flex items-center gap-2.5">
          <span className="bg-ad-primary grid size-8 shrink-0 place-items-center text-[13px] font-bold text-white">
            AI
          </span>
          <div className="leading-tight">
            <div className="text-[14px] font-semibold text-white">图片智能体 · 管理后台</div>
            <div className="text-[10px] tracking-[0.12em] text-ad-sidebar-faint uppercase">
              Admin Console
            </div>
          </div>
        </div>

        <form
          onSubmit={submit}
          className="border-ad-border-strong bg-ad-surface border shadow-ad-pop"
        >
          <header className="border-ad-border bg-ad-surface-2 border-b px-4 py-2.5">
            <h1 className="text-ad-ink text-[13px] font-semibold">管理员登录</h1>
            <p className="text-ad-faint mt-0.5 text-[11px]">仅管理员账号可进入本控制台</p>
          </header>

          <div className="space-y-3 p-4">
            <Field label="用户名">
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                placeholder="管理员用户名"
                autoFocus
                className={inputCls}
              />
            </Field>
            <Field label="密码">
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                placeholder="登录密码"
                className={inputCls}
              />
            </Field>

            {error ? <Alert tone="err">{error}</Alert> : null}

            <Button
              type="submit"
              variant="primary"
              className="w-full"
              loading={login.isPending}
              disabled={!username || !password}
            >
              登录
            </Button>
          </div>

          <footer className="border-ad-border bg-ad-surface-2 border-t px-4 py-2">
            <a
              href={WORKBENCH_URL}
              className="text-ad-muted hover:text-ad-primary text-[11px] transition-colors"
            >
              ← 返回工作台
            </a>
          </footer>
        </form>

        <p className="text-ad-sidebar-faint mt-4 text-center text-[11px]">
          {user ? '当前会话不是管理员账号，请先退出' : '会话状态由服务端 Cookie 维护'}
        </p>
      </div>
    </div>
  )
}
