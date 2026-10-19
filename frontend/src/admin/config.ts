/** 后台是独立应用：工作台跑在另一个端口/域名，跨应用跳转地址集中在这里。
 *  生产部署时用 VITE_WORKBENCH_URL 覆盖，例如 https://studio.example.com */
export const WORKBENCH_URL: string =
  (import.meta.env.VITE_WORKBENCH_URL as string | undefined) ?? 'http://127.0.0.1:7301'
