import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import AdminLayout from '@/layouts/AdminLayout'
import AdminModelsPage from '@/pages/AdminModelsPage'
import AdminOverviewPage from '@/pages/AdminOverviewPage'
import AdminQuotaPage from '@/pages/AdminQuotaPage'
import AdminUsersPage from '@/pages/AdminUsersPage'
import AdminLoginPage from './AdminLoginPage'
import RequireAdmin from './RequireAdmin'

/** 后台独立应用：自己的端口、自己的入口页、自己的登录页，与工作台互不共享路由。 */
export default function AdminApp() {
  return (
    // BASE_URL 构建期为 /admin/，去掉尾斜杠否则精确路径 /admin 匹配不上 basename，整页拒绝渲染
    <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, '')}>
      <Routes>
        <Route path="/login" element={<AdminLoginPage />} />

        <Route element={<RequireAdmin />}>
          <Route element={<AdminLayout />}>
            <Route path="/" element={<AdminOverviewPage />} />
            <Route path="/users" element={<AdminUsersPage />} />
            <Route path="/quota" element={<AdminQuotaPage />} />
            <Route path="/models" element={<AdminModelsPage />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
