export type ButtonVariant = 'ghost' | 'solid' | 'outline' | 'icon' | 'signal' | 'soft'
export type ButtonSize = 'sm' | 'md' | 'lg'
export type ButtonTone = 'light' | 'dark'

const BASE =
  'relative overflow-hidden font-medium transition-[background-color,border-color,color,transform] duration-150 ease-out active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-40 disabled:active:scale-100'

const SHAPE: Record<ButtonSize, string> = {
  sm: 'rounded-chip min-h-8 px-2.5 py-1 text-[11px]',
  md: 'rounded-control min-h-9 px-3 py-1.5 text-xs',
  lg: 'rounded-control min-h-11 px-4 py-2 text-sm',
}

const ICON_SHAPE: Record<ButtonSize, string> = {
  sm: 'rounded-chip grid size-8 place-items-center',
  md: 'rounded-control grid size-9 place-items-center',
  lg: 'rounded-control grid size-11 place-items-center',
}

const IDLE: Record<ButtonTone, Record<ButtonVariant, string>> = {
  light: {
    ghost: 'text-muted hover:bg-soft hover:text-ink',
    solid: 'bg-ink text-white hover:bg-dark',
    outline: 'border-line text-ink hover:border-line-strong hover:bg-soft border',
    icon: 'text-muted hover:bg-soft hover:text-ink',
    signal: 'bg-signal text-signal-ink hover:bg-[#c9f25a] font-semibold',
    soft: 'bg-brand-soft text-brand-strong hover:bg-[#d4e8e0]',
  },
  dark: {
    ghost: 'text-shell-muted hover:bg-shell-3 hover:text-shell-ink',
    solid: 'bg-shell-ink text-shell hover:bg-white',
    outline: 'border-shell-line text-shell-ink hover:border-[#3d4740] hover:bg-shell-3 border',
    icon: 'text-shell-muted hover:bg-shell-3 hover:text-shell-ink',
    signal: 'bg-signal text-signal-ink hover:bg-[#e4ff96] font-semibold',
    soft: 'bg-shell-3 text-shell-ink hover:bg-[#2a322c]',
  },
}

const ON: Record<ButtonTone, Record<ButtonVariant, string>> = {
  light: {
    ghost: 'bg-ai-soft text-brand-strong',
    solid: 'bg-dark text-white',
    outline: 'border-brand bg-brand-soft text-brand-strong border',
    icon: 'bg-ai-soft text-brand-strong',
    signal: 'bg-signal text-signal-ink ring-1 ring-signal-ink/20 font-semibold',
    soft: 'bg-brand-soft text-brand-strong ring-1 ring-brand/25',
  },
  dark: {
    ghost: 'bg-ai/15 text-ai',
    solid: 'bg-white text-shell',
    outline: 'border-ai/50 bg-ai/10 text-ai border',
    icon: 'bg-ai/15 text-ai',
    signal: 'bg-signal text-signal-ink font-semibold',
    soft: 'bg-ai/15 text-ai',
  },
}

export type ButtonLook = {
  variant?: ButtonVariant
  size?: ButtonSize
  tone?: ButtonTone
  active?: boolean
  block?: boolean
}

/** 供 Link 等非 button 元素复用同一套手感。 */
export function buttonClass({
  variant = 'ghost',
  size = 'md',
  tone = 'light',
  active,
  block,
}: ButtonLook = {}) {
  return [
    BASE,
    variant === 'icon' ? ICON_SHAPE[size] : SHAPE[size],
    tone === 'dark' ? 'focus-visible:outline-ai' : 'focus-visible:outline-brand',
    active ? ON[tone][variant] : IDLE[tone][variant],
    block ? 'w-full' : '',
  ]
    .filter(Boolean)
    .join(' ')
}
