import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  // 开发服务器配置
  server: {
    port: 5173,
    host: '0.0.0.0', // 允许局域网访问
    // API 代理：将 /api 请求转发到 FastAPI 后端（端口 8000）
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
