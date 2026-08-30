/**
 * 鉴权相关 API（登录 / 注册）
 */
import api from './index'
import type { LoginResponse } from '../types'

/**
 * 登录（管理员或普通用户，服务端返回角色）
 * POST /api/auth/login
 */
export async function login(username: string, password: string): Promise<LoginResponse> {
  return api.post('/auth/login', { username, password })
}

/** 管理员登录别名（知识库管理页语义） */
export const adminLogin = login

/**
 * 注册普通用户（注册后需调用 login 获取令牌）
 * POST /api/auth/register
 */
export async function register(username: string, password: string): Promise<{ username: string }> {
  return api.post('/auth/register', { username, password })
}

/**
 * 修改当前登录用户密码（普通用户；管理员密码由环境变量管理）
 * PUT /api/auth/password
 */
export async function changePassword(oldPassword: string, newPassword: string): Promise<{ success: boolean; message: string }> {
  return api.put('/auth/password', { old_password: oldPassword, new_password: newPassword })
}
