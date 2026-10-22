import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { adminAuthApi } from '@/api/adminAuth'
import type { Credentials, User } from '@/api/auth'
import { recordRateLimit } from '@/stores/rateLimit'

const ADMIN_ME_KEY = ['admin-auth', 'me']

export function useCurrentAdmin() {
  const { data, isPending } = useQuery({
    queryKey: ADMIN_ME_KEY,
    queryFn: () => adminAuthApi.me(),
    retry: false,
    staleTime: Infinity,
    throwOnError: false,
  })
  return { user: data ?? null, isLoading: isPending }
}

export function useAdminAuthActions() {
  const queryClient = useQueryClient()
  const login = useMutation({
    mutationFn: (body: Credentials) => adminAuthApi.login(body),
    onSuccess: (user: User) => queryClient.setQueryData(ADMIN_ME_KEY, user),
    onError: (error) => recordRateLimit('admin-login', error),
  })
  const logout = useMutation({
    mutationFn: () => adminAuthApi.logout(),
    onSuccess: () => queryClient.removeQueries({ queryKey: ADMIN_ME_KEY }),
  })
  return { login, logout }
}
