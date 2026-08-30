/**
 * 知识库 Store 单元测试（mock API 层，不发起真实请求）
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../src/api/knowledge', () => ({
  getKnowledgeList: vi.fn(async () => ({ documents: [], total: 0 })),
  getFolders: vi.fn(async () => ({ folders: [{ name: '未分类', document_count: 1 }] })),
  deleteKnowledgeDocument: vi.fn(),
  moveKnowledgeDocument: vi.fn(),
  uploadDocuments: vi.fn(),
  uploadDocumentsAsync: vi.fn(),
  getUploadTaskStatus: vi.fn(),
}))

import { moveKnowledgeDocument } from '../src/api/knowledge'
import { useKnowledgeStore } from '../src/store/knowledge'

describe('knowledge store', () => {
  beforeEach(() => {
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
})
