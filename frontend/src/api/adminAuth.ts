import { api } from '@/api/client'
import type { Credentials, User } from '@/api/auth'

/** 管理后台使用独立 Cookie，避免覆盖同域名下的工作台登录态。 */
export const adminAuthApi = {
  login: (body: Credentials) => api.post<User>('/auth/admin/login', body),
  logout: () => api.post<void>('/auth/admin/logout'),
  me: () => api.get<User>('/auth/admin/me'),
}
