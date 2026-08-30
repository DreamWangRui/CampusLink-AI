/**
 * 知识库 Store 单元测试（mock API 层，不发起真实请求）
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// localStorage 内存桩
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

import { getKnowledgeList, moveKnowledgeDocument } from '../src/api/knowledge'
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

  it('401 时置位 needsAuth（弹出登录弹窗）', async () => {
    vi.mocked(getKnowledgeList).mockRejectedValue({
      response: { status: 401, data: { detail: '请先登录' } },
    })

    const store = useKnowledgeStore()
    await store.loadDocuments()
    expect(store.needsAuth).toBe(true)
  })
})
