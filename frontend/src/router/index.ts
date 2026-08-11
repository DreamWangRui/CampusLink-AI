/**
 * Vue Router 路由配置
 * 定义前端页面路由：聊天页（首页）和知识库管理页
 */
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  // 使用 HTML5 History 模式
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'chat',
      // 首页：聊天问答页面
      component: () => import('../views/ChatView.vue'),
      meta: { title: '智能问答 - CampusLink AI' },
    },
    {
      path: '/knowledge',
      name: 'knowledge',
      // 知识库管理页面
      component: () => import('../views/KnowledgeView.vue'),
      meta: { title: '知识库管理 - CampusLink AI' },
    },
  ],
})

// 全局路由守卫：设置页面标题
router.beforeEach((to) => {
  if (to.meta.title) {
    document.title = to.meta.title as string
  }
})

export default router
