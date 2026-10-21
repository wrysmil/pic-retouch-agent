import { api } from '@/api/client'

export type VipInfo = {
  status: 'coming_soon'
  display_name: string
  message: string
}

export type Entitlements = {
  membership_type: 'free'
  display_name: string
  quota_date: string
  daily_limit: number
  adjustment: number
  reserved: number
  consumed: number
  available: number
  counting_unit: string
  timezone: string
  reset_at: string
  policy_version_id: string
  policy_version_seq: number
  vip: VipInfo
}

export type QuotaEstimate = {
  tool: string
  required: number
  available: number
  affordable: boolean
  reset_at: string
  counting_unit: string
}

export type LedgerEntry = {
  id: string
  action: 'reserve' | 'consume' | 'release' | 'adjust'
  units: number
  available_after: number
  reason: string | null
  reservation_id: string | null
  created_at: string
}

export const quotaApi = {
  entitlements: () => api.get<Entitlements>('/me/entitlements'),
  estimate: (tool: string, params: Record<string, unknown> = {}) =>
    api.post<QuotaEstimate>('/quota/estimate', { tool, params }),
  ledger: (limit = 50) => api.get<{ total: number; items: LedgerEntry[] }>(
    `/me/quota-ledger?limit=${limit}`,
  ),
}
