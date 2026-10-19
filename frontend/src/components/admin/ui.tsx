import { useEffect, type ReactNode } from 'react'

/** 后台管理通用视觉基元：面板、按钮、标签、表单控件、弹窗、密集数据表格。
 *  设计约束（企业控制台风格）：一律直角、一律发丝线分层、一律信息密集优先。 */

export function Spinner({ className = 'size-4' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={`animate-spin ${className}`} aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" opacity="0.25" />
      <path d="M21 12a9 9 0 00-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  )
}

/* ---------------- 按钮 ---------------- */

type ButtonProps = {
  variant?: 'primary' | 'default' | 'ghost' | 'danger' | 'dangerSolid' | 'link'
  size?: 'xs' | 'sm' | 'md'
  loading?: boolean
} & React.ButtonHTMLAttributes<HTMLButtonElement>

const BUTTON_BASE =
  'inline-flex cursor-pointer items-center justify-center gap-1.5 border font-medium whitespace-nowrap select-none transition-colors focus-visible:ring-ad-primary/30 focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-45'

const BUTTON_SIZE = { xs: 'h-6 px-2 text-[11px]', sm: 'h-7 px-2.5 text-xs', md: 'h-8 px-3 text-[13px]' }

const BUTTON_VARIANT = {
  primary: 'bg-ad-primary border-ad-primary text-white hover:bg-ad-primary-dark hover:border-ad-primary-dark',
  default:
    'bg-ad-surface border-ad-border-strong text-ad-ink hover:bg-ad-surface-2 hover:border-ad-primary',
  ghost:
    'border-transparent bg-transparent text-ad-muted hover:bg-ad-surface-2 hover:text-ad-ink',
  danger:
    'bg-ad-surface border-ad-danger/40 text-ad-danger hover:border-ad-danger hover:bg-ad-danger-soft',
  dangerSolid: 'bg-ad-danger border-ad-danger text-white hover:brightness-95',
  link: 'border-transparent bg-transparent text-ad-primary hover:bg-transparent hover:underline',
} as const

export function Button({
  variant = 'default',
  size = 'md',
  loading = false,
  className = '',
  disabled,
  children,
  ...rest
}: ButtonProps) {
  const spinnerSize = size === 'xs' ? 'size-3' : size === 'sm' ? 'size-3.5' : 'size-4'
  return (
    <button
      className={`${BUTTON_BASE} ${BUTTON_SIZE[size]} ${BUTTON_VARIANT[variant]} ${className}`}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Spinner className={spinnerSize} /> : null}
      {children}
    </button>
  )
}

/* ---------------- 标签 ---------------- */

type Tone = 'neutral' | 'success' | 'danger' | 'brand' | 'warn'

const TAG_TONE: Record<Tone, string> = {
  neutral: 'bg-ad-surface-3 text-ad-muted border-ad-border-strong',
  success: 'bg-ad-success-soft text-ad-success border-ad-success/30',
  danger: 'bg-ad-danger-soft text-ad-danger border-ad-danger/30',
  brand: 'bg-ad-primary-soft text-ad-primary-dark border-ad-primary/30',
  warn: 'bg-ad-accent-soft text-ad-accent border-ad-accent/30',
}

export function Tag({
  tone = 'neutral',
  mono = false,
  children,
}: {
  tone?: Tone
  mono?: boolean
  children: ReactNode
}) {
  return (
    <span
      className={`inline-flex items-center border px-1.5 py-px text-[11px] leading-4 font-medium whitespace-nowrap ${
        mono ? 'font-ad-mono tabular-nums' : ''
      } ${TAG_TONE[tone]}`}
    >
      {children}
    </span>
  )
}

/* ---------------- 表单 ---------------- */

export function Field({
  label,
  hint,
  error,
  className = '',
  children,
}: {
  label: ReactNode
  hint?: ReactNode
  error?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <label className={`block ${className}`}>
      <span className="text-ad-muted mb-1 flex items-center gap-1.5 text-[11px] font-medium">
        {label}
        {hint ? <span className="text-ad-faint font-normal">（{hint}）</span> : null}
      </span>
      {children}
      {error ? <span className="text-ad-danger mt-1 block text-[11px]">{error}</span> : null}
    </label>
  )
}

export const inputCls =
  'border-ad-border-strong bg-ad-surface text-ad-ink placeholder:text-ad-faint focus:border-ad-primary focus:ring-ad-primary/15 h-8 w-full border px-2.5 text-[13px] transition-shadow focus:ring-2 focus:outline-none disabled:cursor-not-allowed disabled:bg-ad-surface-2 disabled:text-ad-faint'

export const selectCls = `${inputCls} ad-select cursor-pointer`

export const textareaCls = `${inputCls} h-auto py-1.5 leading-5`

/* ---------------- 容器 ---------------- */

export function Panel({
  title,
  desc,
  action,
  footer,
  bodyClass = 'p-3',
  className = '',
  children,
}: {
  title?: ReactNode
  desc?: ReactNode
  action?: ReactNode
  footer?: ReactNode
  bodyClass?: string
  className?: string
  children: ReactNode
}) {
  return (
    <section className={`border-ad-border bg-ad-surface border ${className}`}>
      {(title || action) && (
        <header className="border-ad-border bg-ad-surface-2 flex min-h-9 items-center justify-between gap-4 border-b px-3 py-1.5">
          <div className="min-w-0">
            {title ? (
              <h2 className="text-ad-ink text-[13px] leading-5 font-semibold">{title}</h2>
            ) : null}
            {desc ? <p className="text-ad-faint text-[11px] leading-4">{desc}</p> : null}
          </div>
          {action ? <div className="flex shrink-0 items-center gap-2">{action}</div> : null}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
      {footer ? (
        <footer className="border-ad-border bg-ad-surface-2 text-ad-muted border-t px-3 py-1.5 text-[11px]">
          {footer}
        </footer>
      ) : null}
    </section>
  )
}

/** 筛选/操作工具条：贴住面板顶部的一条灰底带，所有过滤条件都收在这里 */
export function Toolbar({ className = '', children }: { className?: string; children: ReactNode }) {
  return (
    <div
      className={`border-ad-border bg-ad-surface-2 flex flex-wrap items-end gap-2 border p-2 ${className}`}
    >
      {children}
    </div>
  )
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: readonly { key: T; label: ReactNode }[]
  value: T
  onChange: (key: T) => void
}) {
  return (
    <div className="border-ad-border bg-ad-surface inline-flex border">
      {tabs.map((t) => (
        <button
          key={t.key}
          type="button"
          onClick={() => onChange(t.key)}
          className={`h-8 cursor-pointer border-r px-4 text-[13px] font-medium transition-colors last:border-r-0 ${
            value === t.key
              ? 'bg-ad-primary text-white'
              : 'text-ad-muted hover:bg-ad-surface-2 hover:text-ad-ink'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}

/** 关键指标卡：顶部 2px 色条 + 等宽数字，是控制台的视觉锚点 */
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
  const bars = {
    brand: 'bg-ad-primary',
    success: 'bg-ad-success',
    warn: 'bg-ad-accent',
    neutral: 'bg-ad-border-strong',
  }
  const icons = {
    brand: 'text-ad-primary',
    success: 'text-ad-success',
    warn: 'text-ad-accent',
    neutral: 'text-ad-muted',
  }
  return (
    <div className="border-ad-border bg-ad-surface relative border p-3 pt-4">
      <span className={`absolute inset-x-0 top-0 h-0.5 ${bars[tone]}`} aria-hidden />
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-ad-muted text-[11px] font-medium tracking-wide">{label}</p>
          <p className="font-ad-mono text-ad-ink mt-1 text-2xl leading-7 font-semibold tabular-nums">
            {value}
          </p>
          {sub ? <p className="text-ad-faint mt-0.5 truncate text-[11px]">{sub}</p> : null}
        </div>
        <span className={`grid size-7 shrink-0 place-items-center ${icons[tone]}`} aria-hidden>
          <svg viewBox="0 0 24 24" fill="none" className="size-4">
            <path
              d={icon}
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      </div>
    </div>
  )
}

/** 只读键值表：后台展示配置详情的标准形态，比卡片省一半空间 */
export function KeyValue({
  items,
  columns = 2,
}: {
  items: { label: ReactNode; value: ReactNode }[]
  columns?: 1 | 2 | 3
}) {
  const cols = { 1: '', 2: 'sm:grid-cols-2', 3: 'sm:grid-cols-3' }[columns]
  return (
    <dl className={`grid gap-px border-ad-border bg-ad-border ${cols}`}>
      {items.map((it, i) => (
        <div key={i} className="bg-ad-surface px-3 py-2">
          <dt className="text-ad-faint text-[11px]">{it.label}</dt>
          <dd
            className="font-ad-mono text-ad-ink mt-0.5 truncate text-[13px]"
            title={typeof it.value === 'string' ? it.value : undefined}
          >
            {it.value}
          </dd>
        </div>
      ))}
    </dl>
  )
}

/* ---------------- 数据表格 ---------------- */

type Align = 'left' | 'right' | 'center'

const ALIGN: Record<Align, string> = {
  left: 'text-left',
  right: 'text-right',
  center: 'text-center',
}

export function DataTable({
  head,
  align,
  children,
  footer,
  minWidth = 720,
}: {
  head: ReactNode[]
  align?: Align[]
  children: ReactNode
  footer?: ReactNode
  minWidth?: number
}) {
  const cellAlign = (i: number): string => ALIGN[align?.[i] ?? (i === head.length - 1 ? 'right' : 'left')]
  return (
    <div className="border-ad-border bg-ad-surface border">
      <div className="scrollbar-slim overflow-x-auto">
        <table className="w-full border-collapse" style={{ minWidth }}>
          <thead>
            <tr>
              {head.map((h, i) => (
                <th
                  key={i}
                  scope="col"
                  className={`border-ad-border bg-ad-surface-2 text-ad-muted border-b px-3 py-1.5 text-[11px] font-semibold tracking-wide whitespace-nowrap ${cellAlign(i)}`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>{children}</tbody>
        </table>
      </div>
      {footer ? (
        <div className="border-ad-border bg-ad-surface-2 text-ad-muted flex items-center justify-between gap-3 border-t px-3 py-1.5 text-[11px]">
          {footer}
        </div>
      ) : null}
    </div>
  )
}

/** 表格行统一样式：发丝线分隔 + 悬停高亮（skill 指定的 Key Effects） */
export const rowCls = 'border-ad-border hover:bg-ad-surface-2 border-b transition-colors last:border-b-0'
export const cellCls = 'px-3 py-1.5 align-middle'

/* ---------------- 反馈 ---------------- */

export function Alert({
  tone = 'info',
  children,
  onClose,
}: {
  tone?: 'info' | 'ok' | 'err'
  children: ReactNode
  onClose?: () => void
}) {
  const tones = {
    info: 'bg-ad-primary-soft text-ad-primary-dark border-ad-primary',
    ok: 'bg-ad-success-soft text-ad-success border-ad-success',
    err: 'bg-ad-danger-soft text-ad-danger border-ad-danger',
  }
  return (
    <div
      role="status"
      className={`flex items-center justify-between gap-3 border-l-2 px-3 py-1.5 text-[13px] ${tones[tone]}`}
    >
      <span className="min-w-0">{children}</span>
      {onClose ? (
        <button
          type="button"
          onClick={onClose}
          className="cursor-pointer p-0.5 opacity-70 transition-opacity hover:opacity-100"
          aria-label="关闭提示"
        >
          <svg viewBox="0 0 24 24" fill="none" className="size-3.5">
            <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>
      ) : null}
    </div>
  )
}

export function Loading({ text = '加载中…' }: { text?: string }) {
  return (
    <div className="text-ad-muted flex items-center justify-center gap-2 py-10 text-[13px]" role="status">
      <Spinner className="size-4" />
      {text}
    </div>
  )
}

export function EmptyState({ text, hint }: { text: string; hint?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1.5 py-12 text-center">
      <svg viewBox="0 0 24 24" fill="none" className="text-ad-border-strong size-7" aria-hidden>
        <path
          d="M3 5h18v14H3zM3 5l9 7 9-7"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <p className="text-ad-muted text-[13px]">{text}</p>
      {hint ? <p className="text-ad-faint text-[11px]">{hint}</p> : null}
    </div>
  )
}

/* ---------------- 弹窗 ---------------- */

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
      className="animate-fade-in fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-ad-ink/50 p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        className={`bg-ad-surface border-ad-border-strong animate-pop w-full border shadow-ad-pop ${width}`}
      >
        <header className="border-ad-border bg-ad-surface-2 flex items-start justify-between gap-4 border-b px-4 py-2.5">
          <div className="min-w-0">
            <h3 className="text-ad-ink text-[13px] font-semibold">{title}</h3>
            {desc ? <p className="text-ad-faint mt-0.5 text-[11px]">{desc}</p> : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-ad-faint hover:text-ad-ink -mr-1 cursor-pointer p-1 transition-colors"
            aria-label="关闭"
          >
            <svg viewBox="0 0 24 24" fill="none" className="size-3.5">
              <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </header>
        <div className="scrollbar-slim max-h-[70vh] overflow-auto p-4">{children}</div>
        {footer ? (
          <footer className="border-ad-border bg-ad-surface-2 flex justify-end gap-2 border-t px-4 py-2.5">
            {footer}
          </footer>
        ) : null}
      </div>
    </div>
  )
}
