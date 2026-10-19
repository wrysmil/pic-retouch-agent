import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import AdminLayout from '@/layouts/AdminLayout'
import AdminModelsPage from '@/pages/AdminModelsPage'
import AdminOverviewPage from '@/pages/AdminOverviewPage'
import AdminUsersPage from '@/pages/AdminUsersPage'
import AdminLoginPage from './AdminLoginPage'
import RequireAdmin from './RequireAdmin'

/** 后台独立应用：自己的端口、自己的入口页、自己的登录页，与工作台互不共享路由。 */
export default function AdminApp() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<AdminLoginPage />} />

        <Route element={<RequireAdmin />}>
          <Route element={<AdminLayout />}>
            <Route path="/" element={<AdminOverviewPage />} />
            <Route path="/users" element={<AdminUsersPage />} />
            <Route path="/models" element={<AdminModelsPage />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
