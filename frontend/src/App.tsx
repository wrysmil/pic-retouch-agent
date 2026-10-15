import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import RequireAuth from '@/layouts/RequireAuth'
import RequireAdmin from '@/layouts/RequireAdmin'
import AdminLayout from '@/layouts/AdminLayout'
import WorkbenchLayout from '@/layouts/WorkbenchLayout'
import AdminModelsPage from '@/pages/AdminModelsPage'
import AdminOverviewPage from '@/pages/AdminOverviewPage'
import AdminUsersPage from '@/pages/AdminUsersPage'
import AuthPage from '@/pages/AuthPage'
import BatchPage from '@/pages/BatchPage'
import CandidatesPage from '@/pages/CandidatesPage'
import CreatePage from '@/pages/CreatePage'
import EditorPage from '@/pages/EditorPage'
import LandingPage from '@/pages/LandingPage'
import MarketingPage from '@/pages/MarketingPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/auth" element={<AuthPage />} />

        <Route element={<RequireAuth />}>
          <Route element={<WorkbenchLayout />}>
            <Route path="/create" element={<CreatePage />} />
            <Route path="/editor" element={<EditorPage />} />
            <Route path="/editor/:sessionId" element={<EditorPage />} />
            <Route path="/marketing" element={<MarketingPage />} />
            <Route path="/marketing/:sessionId" element={<MarketingPage />} />
            <Route path="/batch" element={<BatchPage />} />
            <Route path="/batch/:runId" element={<BatchPage />} />
            <Route path="/candidates/:runId" element={<CandidatesPage />} />
          </Route>
        </Route>

        <Route element={<RequireAdmin />}>
          <Route element={<AdminLayout />}>
            <Route path="/admin" element={<AdminOverviewPage />} />
            <Route path="/admin/users" element={<AdminUsersPage />} />
            <Route path="/admin/models" element={<AdminModelsPage />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}