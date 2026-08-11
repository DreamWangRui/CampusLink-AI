/**
 * 知识库状态管理（Pinia Store）
 * 管理文档列表、文件夹、上传和筛选状态
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { KnowledgeDocument, FolderInfo } from '../types'
import { getKnowledgeList, getFolders, deleteKnowledgeDocument, uploadDocuments } from '../api/knowledge'

export const useKnowledgeStore = defineStore('knowledge', () => {
  // ==================== 状态 ====================
  /** 知识库文档列表 */
  const documents = ref<KnowledgeDocument[]>([])

  /** 文档总数 */
  const total = ref(0)

  /** 是否正在加载 */
  const loading = ref(false)

  /** 是否正在上传 */
  const uploading = ref(false)

  /** 文件夹列表 */
  const folders = ref<FolderInfo[]>([])

  /** 当前选中的文件夹筛选（空字符串表示全部） */
  const selectedFolder = ref('')

  // ==================== 操作 ====================

  /**
   * 加载知识库文档列表（支持按文件夹筛选）
   */
  async function loadDocuments() {
    loading.value = true
    try {
      const folder = selectedFolder.value || undefined
      const response = await getKnowledgeList(folder)
      documents.value = response.documents
      total.value = response.total
    } catch (error) {
      console.error('加载文档列表失败:', error)
    } finally {
      loading.value = false
    }
  }

  /**
   * 加载文件夹列表
   */
  async function loadFolders() {
    try {
      const response = await getFolders()
      folders.value = response.folders
    } catch (error) {
      console.error('加载文件夹列表失败:', error)
    }
  }

  /**
   * 设置文件夹筛选并重新加载文档
   *
   * @param folder - 文件夹名称，空字符串表示全部
   */
  async function setFolderFilter(folder: string) {
    selectedFolder.value = folder
    await loadDocuments()
  }

  /**
   * 批量上传文档到知识库
   *
   * @param files - 要上传的文件数组
   * @param folder - 目标文件夹名称
   * @returns 上传结果消息
   */
  async function upload(files: File[], folder: string): Promise<string> {
    uploading.value = true
    try {
      const response = await uploadDocuments(files, folder)
      // 上传成功后刷新列表和文件夹
      await loadDocuments()
      await loadFolders()
      return response.message || `上传完成`
    } catch (error: any) {
      const msg = error?.response?.data?.detail || error.message || '上传失败'
      throw new Error(msg)
    } finally {
      uploading.value = false
    }
  }

  /**
   * 删除知识库中的文档
   *
   * @param docId - 文档 ID
   * @returns 操作结果消息
   */
  async function removeDocument(docId: string): Promise<string> {
    try {
      const response = await deleteKnowledgeDocument(docId)
      if (response.success) {
        // 删除成功后刷新列表和文件夹计数
        await loadDocuments()
        await loadFolders()
      }
      return response.message
    } catch (error: any) {
      const msg = error?.response?.data?.detail || error.message || '删除失败'
      throw new Error(msg)
    }
  }

  return {
    documents, total, loading, uploading,
    folders, selectedFolder,
    loadDocuments, loadFolders, setFolderFilter,
    upload, removeDocument,
  }
})
