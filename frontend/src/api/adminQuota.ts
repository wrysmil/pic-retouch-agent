import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'

export type Policy = {
  id: string
  version_seq: number
  daily_limit: number
  counting_unit: string
  timezone: string
  effective_from: string
  published_by: string | null
  note: string | null
  created_at: string
}

export type OpenReservation = {
  id: string
  units: number
  settled: number
  released: number
  status: 'reserved' | 'unknown'
  run_id: string | null
  turn_id: string | null
  step_id: string | null
  expires_at: string | null
  created_at: string
}

export type UserQuota = {
  quota_date: string
  limit: number
  adjustment: number
  reserved: number
  consumed: number
  available: number
  reset_at: string
  policy_version_id: string
  policy_version_seq: number
  open_reservations: OpenReservation[]
}

export function usePolicies() {
  return useQuery({
    queryKey: ['admin', 'quota', 'policies'],
    queryFn: () => api.get<Policy[]>('/admin/membership-policies'),
  })
}

export function usePublishPolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { daily_limit: number; effective_from?: string; note?: string }) =>
      api.post<Policy>('/admin/membership-policies', body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'quota', 'policies'] })
    },
  })
}

export function useUserQuota(userId: string) {
  return useQuery({
    queryKey: ['admin', 'quota', 'user', userId],
    queryFn: () => api.get<UserQuota>(`/admin/users/${userId}/quota`),
    enabled: Boolean(userId),
  })
}

export function useReleaseReservation(userId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      api.post<{ id: string; status: string }>(
        `/admin/quota-reservations/${id}/release`,
        { reason },
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'quota', 'user', userId] })
    },
  })
}

export function useAdjustQuota(userId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { units: number; reason: string; quota_date?: string }) =>
      api.post<UserQuota>(`/admin/users/${userId}/quota-adjustments`, body),
    onSuccess: (data) => {
      queryClient.setQueryData(['admin', 'quota', 'user', userId], data)
      void queryClient.invalidateQueries({ queryKey: ['admin', 'quota', 'policies'] })
    },
  })
}
