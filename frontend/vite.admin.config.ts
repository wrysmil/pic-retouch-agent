import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'

const fromHere = (rel: string) => fileURLToPath(new URL(rel, import.meta.url))

/** 后台是独立应用：独立端口、独立 HTML 入口、独立登录页。
 *  root 指向 admin/，因此 SPA 回退落到的是 admin/index.html 而不是工作台的首页。
 *  与工作台共用同一份 node_modules、同一套 /api 代理与同一份设计 token，代码仍放在 src/admin 与 src/components/admin。 */
export default defineConfig({
  root: fromHere('./admin'),
  publicDir: fromHere('./public'),
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fromHere('./src') },
  },
  server: {
    host: '127.0.0.1',
    port: 7303,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://localhost:7302', changeOrigin: true },
      '/events': { target: 'http://localhost:7302', changeOrigin: true },
    },
  },
  build: {
    outDir: fromHere('./dist-admin'),
    emptyOutDir: true,
  },
})
