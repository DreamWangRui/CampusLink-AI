/**
 * API 请求封装
 * 使用 Axios 与后端 FastAPI 通信
 */
import axios from 'axios'

// 创建 Axios 实例，配置后端 API 基础地址
const api = axios.create({
  // 后端 FastAPI 地址（开发环境通过 Vite 代理转发）
  baseURL: '/api',
  // 请求超时时间：60 秒（大模型生成回答可能需要较长时间）
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ==================== 请求拦截器 ====================
api.interceptors.request.use(
  (config) => {
    // 知识库管理接口自动附带管理员密钥（登录后保存在 localStorage）
    const url = config.url ?? ''
    if (url.startsWith('/knowledge') || url.startsWith('/document')) {
      const adminKey = localStorage.getItem('campuslink_admin_key')
      if (adminKey) {
        config.headers['X-Admin-Key'] = adminKey
      }
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// ==================== 响应拦截器 ====================
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    // 统一错误处理
    const message = error.response?.data?.detail || error.message || '请求失败'
    console.error('API 请求错误:', message)
    return Promise.reject(error)
  }
)

export default api
