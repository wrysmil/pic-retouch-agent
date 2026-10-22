import { useEffect, useState } from 'react'
import { create } from 'zustand'

import { rateLimitSeconds } from '@/api/client'

type RateLimitState = {
  until: Record<string, number>
  mark: (action: string, seconds: number) => void
  clear: (action: string) => void
}

export const useRateLimitStore = create<RateLimitState>((set) => ({
  until: {},
  mark: (action, seconds) =>
    set((state) => ({
      until: { ...state.until, [action]: Date.now() + Math.max(1, seconds) * 1000 },
    })),
  clear: (action) =>
    set((state) => {
      const until = { ...state.until }
      delete until[action]
      return { until }
    }),
}))

export function recordRateLimit(action: string, error: unknown) {
  const seconds = rateLimitSeconds(error)
  if (seconds > 0) useRateLimitStore.getState().mark(action, seconds)
}

export function clearRateLimit(action: string) {
  useRateLimitStore.getState().clear(action)
}

export function useRateLimit(action: string) {
  const until = useRateLimitStore((state) => state.until[action] ?? 0)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!until || until <= now) return
    const tick = () => setNow(Date.now())
    const timer = window.setInterval(tick, 250)
    return () => window.clearInterval(timer)
  }, [until, now])

  return Math.max(0, Math.ceil((until - now) / 1000))
}

export function rateLimitLabel(action: string, seconds: number) {
  return seconds > 0 ? `${seconds} 秒后重试` : action
}
