/**
 * 认证状态管理（Pinia Store）
 * 管理登录令牌与用户身份：管理员（知识库管理）和普通用户（云端聊天记录）共用一套登录
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  adminLogin as adminLoginApi,
  changePassword as changePasswordApi,
  login as loginApi,
  register as registerApi,
} from '../api/auth'

const TOKEN_KEY = 'campuslink_token'
const NAME_KEY = 'campuslink_user_name'
const ROLE_KEY = 'campuslink_role'

export const useAuthStore = defineStore('auth', () => {
  // ==================== 状态 ====================
  const token = ref(localStorage.getItem(TOKEN_KEY) ?? '')
  const username = ref(localStorage.getItem(NAME_KEY) ?? '')
  const role = ref(localStorage.getItem(ROLE_KEY) ?? '')

  /** 是否已登录（任意角色） */
  const isLoggedIn = computed(() => !!token.value)
  /** 是否管理员 */
  const isAdmin = computed(() => role.value === 'admin')

  // ==================== 操作 ====================

  function _save(tokenValue: string, nameValue: string, roleValue: string) {
    token.value = tokenValue
    username.value = nameValue
    role.value = roleValue
    localStorage.setItem(TOKEN_KEY, tokenValue)
    localStorage.setItem(NAME_KEY, nameValue)
    localStorage.setItem(ROLE_KEY, roleValue)
  }

  /** 登录（管理员或普通用户，服务端自动判定角色） */
  async function login(username: string, password: string): Promise<string> {
    const resp = await loginApi(username, password)
    _save(resp.token, resp.username, resp.role)
    return resp.role
  }

  /** 管理员快捷登录（知识库管理页使用，语义同 login） */
  async function adminLogin(username: string, password: string): Promise<string> {
    await adminLoginApi(username, password)
    return login(username, password)
  }

  /** 注册普通用户并自动登录 */
  async function register(username: string, password: string): Promise<void> {
    await registerApi(username, password)
    await login(username, password)
  }

  /** 修改当前登录用户密码（普通用户），返回结果消息 */
  async function changePassword(oldPassword: string, newPassword: string): Promise<string> {
    const resp = await changePasswordApi(oldPassword, newPassword)
    return resp.message
  }

  /** 退出登录 */
  function logout(): void {
    token.value = ''
    username.value = ''
    role.value = ''
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(NAME_KEY)
    localStorage.removeItem(ROLE_KEY)
  }

  return {
    token, username, role, isLoggedIn, isAdmin,
    login, adminLogin, register, logout, changePassword,
  }
})
