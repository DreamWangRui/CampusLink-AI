import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'

// 说明：Element Plus 已通过 unplugin-vue-components 按需引入（见 vite.config.ts），
// 组件样式自动导入；中文语言包由 App.vue 中的 el-config-provider 配置。

// 创建 Vue 应用实例
const app = createApp(App)

// 注册 Pinia 状态管理
app.use(createPinia())

// 注册路由
app.use(router)

app.mount('#app')
