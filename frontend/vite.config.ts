import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // Element Plus 按需引入：模板中使用的组件（el-table 等）与样式自动按需导入，
    // 替代原先的全量引入（主包体积减半以上）
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
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
