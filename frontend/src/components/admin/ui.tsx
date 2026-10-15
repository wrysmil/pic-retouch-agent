import { useEffect, type ReactNode } from 'react'

/** 后台管理通用视觉基元：卡片、按钮、徽标、表单控件、弹窗、表格骨架。
 *  统一使用 ad- 前缀的「企业蓝·数据密集」设计 token，与工作台视觉隔离。 */

export function Card({
  title,
  desc,
  action,
  children,
  className = '',
}: {
  title?: ReactNode
  desc?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={`bg-ad-surface border-ad-border rounded-ad border shadow-ad-card ${className}`}
    >
      {(title || action) && (
        <header className="border-ad-border flex items-start justify-between gap-4 border-b px-4 py-3">
          <div>
            {title ? <h2 className="text-ad-ink text-sm font-semibold">{title}</h2> : null}
            {desc ? <p className="text-ad-faint mt-0.5 text-xs">{desc}</p> : null}
          </div>
          {action}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  )
}

export function Spinner({ className = 'size-4' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={`animate-spin ${className}`} aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" opacity="0.25" />
      <path d="M21 12a9 9 0 00-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  )
}

type ButtonProps = {
  variant?: 'primary' | 'ghost' | 'outline' | 'danger' | 'subtle'
  size?: 'sm' | 'md'
  loading?: boolean
} & React.ButtonHTMLAttributes<HTMLButtonElement>

export function Button({
  variant = 'outline',
  size = 'md',
  loading = false,
  className = '',
  disabled,
  children,
  ...rest
}: ButtonProps) {
  const base =
    'inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-ad-sm font-medium transition-colors focus-visible:ring-ad-primary/30 focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50'
  const sizes = { sm: 'px-2.5 py-1 text-xs', md: 'px-3.5 py-1.5 text-sm' }
  const variants = {
    primary: 'bg-ad-primary text-white hover:bg-ad-primary-dark',
    danger: 'bg-ad-danger text-white hover:brightness-95',
    outline: 'border-ad-border-strong text-ad-ink hover:bg-ad-surface-2 border',
    ghost: 'text-ad-muted hover:text-ad-ink hover:bg-ad-surface-2',
    subtle: 'bg-ad-primary-soft text-ad-primary-dark hover:brightness-95',
  }
  return (
    <button
      className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Spinner className={size === 'sm' ? 'size-3.5' : 'size-4'} /> : null}
      {children}
    </button>
  )
}

export function Badge({
  tone = 'neutral',
  children,
}: {
  tone?: 'neutral' | 'success' | 'danger' | 'brand' | 'warn'
  children: ReactNode
}) {
  const tones = {
    neutral: 'bg-ad-surface-3 text-ad-muted',
    success: 'bg-ad-success-soft text-ad-success',
    danger: 'bg-ad-danger-soft text-ad-danger',
    brand: 'bg-ad-primary-soft text-ad-primary-dark',
    warn: 'bg-ad-accent-soft text-ad-accent',
  }
  return (
    <span
      className={`inline-flex items-center rounded-ad-xs px-2 py-0.5 text-xs font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  )
}

export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: ReactNode
  hint?: ReactNode
  error?: ReactNode
  children: ReactNode
}) {
  return (
    <label className="block">
      <span className="text-ad-ink mb-1.5 flex items-center gap-1 text-xs font-medium">
        {label}
        {hint ? <span className="text-ad-faint font-normal">（{hint}）</span> : null}
      </span>
      {children}
      {error ? <span className="text-ad-danger mt-1 block text-xs">{error}</span> : null}
    </label>
  )
}

export const inputCls =
  'border-ad-border-strong focus:border-ad-primary focus:ring-ad-primary/20 bg-ad-surface text-ad-ink placeholder:text-ad-faint w-full rounded-ad-sm border px-3 py-1.5 text-sm transition-shadow focus:ring-2 focus:outline-none'

export const selectCls = `${inputCls} cursor-pointer`

export function StatCard({
  label,
  value,
  sub,
  icon,
  tone = 'brand',
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  icon: string
  tone?: 'brand' | 'success' | 'warn' | 'neutral'
}) {
  const tones = {
    brand: 'bg-ad-primary-soft text-ad-primary',
    success: 'bg-ad-success-soft text-ad-success',
    warn: 'bg-ad-accent-soft text-ad-accent',
    neutral: 'bg-ad-surface-3 text-ad-muted',
  }
  return (
    <div className="bg-ad-surface border-ad-border rounded-ad border p-4 shadow-ad-card">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-ad-muted text-xs font-medium">{label}</p>
          <p className="text-ad-ink font-ad-mono mt-1.5 text-2xl font-semibold tabular-nums">
            {value}
          </p>
          {sub ? <p className="text-ad-faint mt-1 text-xs">{sub}</p> : null}
        </div>
        <span
          className={`grid size-9 shrink-0 place-items-center rounded-ad-sm ${tones[tone]}`}
        >
          <svg viewBox="0 0 24 24" fill="none" className="size-5" aria-hidden>
            <path
              d={icon}
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      </div>
    </div>
  )
}

export function Modal({
  title,
  desc,
  onClose,
  children,
  footer,
  width = 'max-w-md',
}: {
  title: ReactNode
  desc?: ReactNode
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  width?: string
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="animate-fade-in fixed inset-0 z-50 grid place-items-center bg-ad-ink/45 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className={`bg-ad-surface animate-pop w-full ${width} rounded-ad shadow-ad-pop`}>
        <header className="border-ad-border flex items-start justify-between gap-4 border-b px-5 py-4">
          <div>
            <h3 className="text-ad-ink text-sm font-semibold">{title}</h3>
            {desc ? <p className="text-ad-faint mt-0.5 text-xs">{desc}</p> : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-ad-faint hover:text-ad-ink -mr-1 cursor-pointer rounded-ad-xs p-1 transition-colors"
            aria-label="关闭"
          >
            <svg viewBox="0 0 24 24" fill="none" className="size-4">
              <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
        </header>
        <div className="scrollbar-slim max-h-[70vh] overflow-auto px-5 py-4">{children}</div>
        {footer ? (
          <footer className="border-ad-border flex justify-end gap-2 border-t px-5 py-3.5">
            {footer}
          </footer>
        ) : null}
      </div>
    </div>
  )
}

export function Loading({ text = '加载中…' }: { text?: string }) {
  return (
    <div className="text-ad-muted flex items-center justify-center gap-2 py-10 text-sm" role="status">
      <Spinner className="size-4" />
      {text}
    </div>
  )
}

export function EmptyState({ text }: { text: string }) {
  return (
    <div className="text-ad-faint flex flex-col items-center gap-2 py-10 text-sm">
      <svg viewBox="0 0 24 24" fill="none" className="size-8 opacity-50">
        <path
          d="M4 7h16v12H4zM4 7l8 6 8-6"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {text}
    </div>
  )
}

export function TableShell({ head, children }: { head: ReactNode[]; children: ReactNode }) {
  return (
    <div className="border-ad-border overflow-hidden rounded-ad-sm border">
      <div className="scrollbar-slim overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <thead className="bg-ad-surface-2 text-ad-muted text-xs">
            <tr>
              {head.map((h, i) => (
                <th
                  key={i}
                  className={`border-ad-border px-3 py-2 font-semibold whitespace-nowrap border-b ${i === head.length - 1 ? 'text-right' : 'text-left'}`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>{children}</tbody>
        </table>
      </div>
    </div>
  )
}
