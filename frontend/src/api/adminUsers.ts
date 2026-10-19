import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/api/client'

export type Role = 'user' | 'admin'

export type AdminUser = {
  id: string
  username: string
  role: Role
  is_active: boolean
  auth_version: number
  last_login_at: string | null
  created_at: string
  password_changed_at: string | null
}

export type AdminUserList = {
  total: number
  items: AdminUser[]
}

const KEY = ['admin', 'users'] as const

export function useAdminUsers(params: {
  keyword?: string
  role?: Role
  is_active?: boolean
  limit?: number
  offset?: number
}) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: async () => {
      const query: Record<string, string> = {}
      if (params.keyword) query.keyword = params.keyword
      if (params.role) query.role = params.role
      if (params.is_active !== undefined) query.is_active = String(params.is_active)
      if (params.limit !== undefined) query.limit = String(params.limit)
      if (params.offset !== undefined) query.offset = String(params.offset)
      const search = new URLSearchParams(query).toString()
      return api.get<AdminUserList>(`/admin/users${search ? `?${search}` : ''}`)
    },
  })
}

export type CreateUserInput = {
  username: string
  password: string
  role: Role
  is_active: boolean
}

export function useCreateAdminUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateUserInput) => api.post<AdminUser>('/admin/users', body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })
}

export function useUpdateUserRole() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, role }: { id: string; role: Role }) =>
      api.patch<AdminUser>(`/admin/users/${id}/role`, { role }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })
}

export function useUpdateUserActive() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.patch<AdminUser>(`/admin/users/${id}/active`, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })
}

export function useResetUserPassword() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, new_password }: { id: string; new_password: string }) =>
      api.post<AdminUser>(`/admin/users/${id}/reset-password`, { new_password }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })
}

export function useRevokeUserSessions() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.post<AdminUser>(`/admin/users/${id}/revoke-sessions`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })
}