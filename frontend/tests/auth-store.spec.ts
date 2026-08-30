/**
 * 认证 Store 单元测试（mock API 层）
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const storage = new Map<string, string>()
vi.stubGlobal('localStorage', {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => storage.delete(key),
})

vi.mock('../src/api/auth', () => ({
  login: vi.fn(),
  adminLogin: vi.fn(),
  register: vi.fn(async () => ({ username: 'newbie' })),
}))

import { login, register } from '../src/api/auth'
import { useAuthStore } from '../src/store/auth'

describe('auth store', () => {
  beforeEach(() => {
    storage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('login 保存令牌、用户名与角色', async () => {
    vi.mocked(login).mockResolvedValue({
      token: 'tok-abc',
      expires_in: 604800,
      username: 'admin',
      role: 'admin',
    })

    const store = useAuthStore()
    const role = await store.login('admin', 'admin123')

    expect(role).toBe('admin')
    expect(store.isLoggedIn).toBe(true)
    expect(store.isAdmin).toBe(true)
    expect(storage.get('campuslink_token')).toBe('tok-abc')
    expect(storage.get('campuslink_role')).toBe('admin')
  })

  it('register 注册后自动登录（user 角色）', async () => {
    vi.mocked(login).mockResolvedValue({
      token: 'tok-user',
      expires_in: 604800,
      username: 'newbie',
      role: 'user',
    })

    const store = useAuthStore()
    await store.register('newbie', 'pass666')

    expect(register).toHaveBeenCalledWith('newbie', 'pass666')
    expect(login).toHaveBeenCalledWith('newbie', 'pass666')
    expect(store.isLoggedIn).toBe(true)
    expect(store.isAdmin).toBe(false)
    expect(storage.get('campuslink_token')).toBe('tok-user')
  })

  it('logout 清除全部登录状态', async () => {
    vi.mocked(login).mockResolvedValue({
      token: 'tok-abc',
      expires_in: 604800,
      username: 'admin',
      role: 'admin',
    })

    const store = useAuthStore()
    await store.login('admin', 'admin123')
    expect(store.isLoggedIn).toBe(true)

    store.logout()
    expect(store.isLoggedIn).toBe(false)
    expect(storage.has('campuslink_token')).toBe(false)
    expect(storage.has('campuslink_user_name')).toBe(false)
    expect(storage.has('campuslink_role')).toBe(false)
  })
})
