import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import '../src/index.css'
import AdminApp from '../src/admin/App'

// 独立于工作台的第二个 React 根：只有后台的路由与登录页，没有工作台的任何页面
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AdminApp />
    </QueryClientProvider>
  </StrictMode>,
)
