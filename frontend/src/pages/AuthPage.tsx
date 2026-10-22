import { useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'

import BrandMark from '@/components/BrandMark'
import { errorMessage, useAuthActions, useCurrentUser } from '@/hooks/useAuth'
import { useRateLimit } from '@/stores/rateLimit'

type Mode = 'login' | 'register'
type Rules = { minLength?: number; maxLength?: number; pattern?: string; title?: string }

const COPY: Record<Mode, { title: string; submit: string; switchTo: Mode; switchHint: string }> = {
  login: { title: '登录', submit: '登录', switchTo: 'register', switchHint: '还没有账号？注册' },
  register: {
    title: '创建账号',
    submit: '注册并进入',
    switchTo: 'login',
    switchHint: '已有账号？登录',
  },
}

// 与后端 Credentials 一致，注册时先在浏览器拦下，不用等一次请求。登录不限长度，老账号也进得来。
const RULES: Record<Mode, { username: Rules; password: Rules }> = {
  login: { username: {}, password: {} },
  register: {
    username: {
      minLength: 3,
      maxLength: 32,
      pattern: '[\\p{L}\\p{N}_]{3,32}',
      title: '3–32 位字母、数字或下划线',
    },
    password: { minLength: 6, maxLength: 64, title: '6–64 位' },
  },
}

export default function AuthPage() {
  const [params, setParams] = useSearchParams()
  const mode: Mode = params.get('mode') === 'register' ? 'register' : 'login'
  const copy = COPY[mode]

  const navigate = useNavigate()
  const { user, isLoading } = useCurrentUser()
  const { login, register } = useAuthActions()
  const action = mode === 'login' ? login : register
  const rateLimitSeconds = useRateLimit(mode)

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  if (!isLoading && user) return <Navigate to="/create" replace />

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    action.mutate({ username, password }, { onSuccess: () => navigate('/create', { replace: true }) })
  }

  const switchMode = () => {
    action.reset()
    setParams({ mode: copy.switchTo })
  }

  return (
    <div className="relative isolate flex min-h-screen items-center justify-center px-5 py-8 sm:px-8 sm:py-12">
      <div className="bg-glow absolute inset-x-0 top-0 h-[420px]" aria-hidden />

      <div className="relative w-full max-w-[940px]">
        <Link to="/" className="text-muted hover:text-ink mb-6 inline-flex items-center gap-2 text-sm transition-colors">
          <span aria-hidden>←</span> 返回首页
        </Link>

        <div className="border-line bg-paper rounded-panel shadow-panel grid overflow-hidden border md:grid-cols-[1fr_1fr]">
          <aside className="bg-soft relative hidden flex-col justify-between overflow-hidden p-9 md:flex">
            <div className="relative z-10">
              <span className="text-brand-strong text-[10px] font-semibold tracking-[0.22em]">YOUR CREATIVE SPACE</span>
              <h2 className="text-ink mt-5 text-3xl leading-snug font-semibold tracking-tight">
                给每个灵感，<br />一个好看的开始。
              </h2>
              <p className="text-muted mt-4 max-w-64 text-sm leading-7">从一句描述到一张作品，让创作自然发生。</p>
            </div>
            <img
              src="/illustrations/studio-companion.webp"
              alt=""
              width={400}
              height={400}
              className="studio-illustration pointer-events-none relative -mx-4 my-2 w-[calc(100%+2rem)] max-w-none mix-blend-multiply select-none"
            />
            <div className="border-line text-muted flex items-center gap-2 border-t pt-5 text-xs">
              <span className="bg-accent h-2 w-2 rounded-full" aria-hidden />
              描述灵感 · 生成画面 · 细致修图
            </div>
          </aside>

          <div className="px-7 py-9 sm:px-10 md:flex md:flex-col md:justify-center md:py-12">
            <BrandMark size="sm">
              <span className="text-ink text-sm font-semibold">映造</span>
            </BrandMark>

            <h1 className="text-ink mt-9 text-3xl font-semibold tracking-tight">{copy.title}</h1>
            <p className="text-muted mt-3 text-sm leading-6">
              {mode === 'login' ? '欢迎回来，继续你的创作。' : '准备好，把灵感变成作品。'}
            </p>

            <form onSubmit={submit} className="mt-8 space-y-5">
              <Field
                label="用户名"
                value={username}
                onChange={setUsername}
                autoComplete="username"
                placeholder="3–32 位字母、数字或下划线"
                rules={RULES[mode].username}
              />
              <Field
                label="密码"
                type="password"
                value={password}
                onChange={setPassword}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                placeholder="至少 6 位"
                rules={RULES[mode].password}
              />

              {action.isError && (
                <p className="text-danger text-sm">
                  {errorMessage(action.error)}
                  {rateLimitSeconds > 0 ? ` · ${rateLimitSeconds} 秒后可重试` : ''}
                </p>
              )}

              <button
                type="submit"
                disabled={action.isPending || rateLimitSeconds > 0}
                className="bg-ink hover:bg-dark rounded-control mt-1 w-full py-3 text-sm font-medium text-white transition-colors disabled:opacity-50"
              >
                {action.isPending
                  ? '处理中…'
                  : rateLimitSeconds > 0
                    ? `${rateLimitSeconds} 秒后可重试`
                    : copy.submit}
              </button>
            </form>

            <button
              type="button"
              onClick={switchMode}
              className="text-muted hover:text-brand-strong mt-6 text-sm transition-colors md:self-start"
            >
              {copy.switchHint}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function Field({
  label,
  value,
  onChange,
  type = 'text',
  autoComplete,
  placeholder,
  rules,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  type?: string
  autoComplete?: string
  placeholder?: string
  rules?: Rules
}) {
  return (
    <label className="block">
      <span className="text-ink mb-2 block text-sm font-medium">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={autoComplete}
        placeholder={placeholder}
        required
        {...rules}
        className="border-line bg-soft/60 text-ink placeholder:text-faint focus:border-brand focus:ring-brand/10 rounded-control w-full border px-3.5 py-3 text-sm outline-none transition-colors focus:bg-paper focus:ring-4"
      />
    </label>
  )
}
