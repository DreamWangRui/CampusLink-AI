import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import './style.css'

// 创建 Vue 应用实例
const app = createApp(App)

// 注册 Element Plus 组件库
app.use(ElementPlus, { locale: undefined }) // 默认使用中文

// 注册 Pinia 状态管理
app.use(createPinia())

// 注册路由
app.use(router)

// 注册所有 Element Plus 图标
import type { Component } from 'vue'
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component as Component)
}

app.mount('#app')
