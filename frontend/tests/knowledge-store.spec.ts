/**
 * 知识库 Store 单元测试（mock API 层，不发起真实请求）
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// localStorage 内存桩（登录令牌存取用到）
const storage = new Map<string, string>()
vi.stubGlobal('localStorage', {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => storage.delete(key),
})

vi.mock('../src/api/knowledge', () => ({
  getKnowledgeList: vi.fn(async () => ({ documents: [], total: 0 })),
  getFolders: vi.fn(async () => ({ folders: [{ name: '未分类', document_count: 1 }] })),
  deleteKnowledgeDocument: vi.fn(),
  moveKnowledgeDocument: vi.fn(),
  uploadDocuments: vi.fn(),
  uploadDocumentsAsync: vi.fn(),
  getUploadTaskStatus: vi.fn(),
}))

vi.mock('../src/api/auth', () => ({
  adminLogin: vi.fn(),
}))

import { adminLogin } from '../src/api/auth'
import { moveKnowledgeDocument, getKnowledgeList } from '../src/api/knowledge'
import { useKnowledgeStore } from '../src/store/knowledge'

describe('knowledge store', () => {
  beforeEach(() => {
    storage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('moveDocument 成功后刷新列表与分类', async () => {
    vi.mocked(moveKnowledgeDocument).mockResolvedValue({
      success: true,
      message: '已成功移动 3 个 Chunk 到「新分类」',
    })

    const store = useKnowledgeStore()
    const message = await store.moveDocument('doc1', '新分类')

    expect(message).toContain('新分类')
    expect(moveKnowledgeDocument).toHaveBeenCalledWith('doc1', '新分类')
    // 刷新动作被触发（mock 返回空列表）
    expect(store.documents).toEqual([])
  })

  it('moveDocument 失败时抛出错误信息', async () => {
    vi.mocked(moveKnowledgeDocument).mockResolvedValue({
      success: false,
      message: "文档 'ghost' 不存在",
    })

    const store = useKnowledgeStore()
    const message = await store.moveDocument('ghost', 'x')
    expect(message).toContain('不存在')
  })

  it('401 时置位 needsAuth（弹出登录弹窗）并清除失效令牌', async () => {
    storage.set('campuslink_admin_token', 'expired-token')
    vi.mocked(getKnowledgeList).mockRejectedValue({
      response: { status: 401, data: { detail: '请先登录' } },
    })

    const store = useKnowledgeStore()
    await store.loadDocuments()
    expect(store.needsAuth).toBe(true)
    expect(storage.has('campuslink_admin_token')).toBe(false)
  })

  it('login 成功保存令牌、清除 needsAuth 并重新加载', async () => {
    vi.mocked(getKnowledgeList).mockRejectedValue({
      response: { status: 401, data: { detail: '请先登录' } },
    })

    const store = useKnowledgeStore()
    await store.loadDocuments()
    expect(store.needsAuth).toBe(true)

    // 登录成功：令牌入库、状态复位、重新加载成功
    vi.mocked(adminLogin).mockResolvedValue({
      token: 'tok-123',
      expires_in: 604800,
      username: 'admin',
    })
    vi.mocked(getKnowledgeList).mockResolvedValue({
      documents: [{ id: 'd1', filename: 'a.pdf', folder: '', upload_time: 't', chunk_count: 1 }],
      total: 1,
    })
    await store.login('admin', 'admin123')

    expect(storage.get('campuslink_admin_token')).toBe('tok-123')
    expect(store.needsAuth).toBe(false)
    expect(store.total).toBe(1)
  })

  it('login 账号密码错误时保持 needsAuth（弹窗不关闭）', async () => {
    vi.mocked(adminLogin).mockRejectedValue({
      response: { status: 401, data: { detail: '账号或密码错误' } },
    })

    const store = useKnowledgeStore()
    await expect(store.login('admin', 'bad')).rejects.toThrow()
    expect(storage.has('campuslink_admin_token')).toBe(false)
    expect(store.needsAuth).toBe(false) // 登录接口本身的 401 不重复置位，由弹窗保持
  })

  it('logout 清除令牌并重新触发鉴权', async () => {
    storage.set('campuslink_admin_token', 'tok-123')
    vi.mocked(getKnowledgeList).mockRejectedValue({
      response: { status: 401, data: { detail: '请先登录' } },
    })

    const store = useKnowledgeStore()
    await store.logout()

    expect(storage.has('campuslink_admin_token')).toBe(false)
    expect(store.needsAuth).toBe(true)
  })
})
