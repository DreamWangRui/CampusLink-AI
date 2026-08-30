/**
 * 鉴权相关 API
 */
import api from './index'
import type { LoginResponse } from '../types'

/**
 * 管理员登录，成功后返回访问令牌
 * POST /api/auth/login
 */
export async function adminLogin(username: string, password: string): Promise<LoginResponse> {
  return api.post('/auth/login', { username, password })
}
