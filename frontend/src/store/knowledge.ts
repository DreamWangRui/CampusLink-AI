/**
 * 知识库状态管理（Pinia Store）
 * 管理文档列表、文件夹、上传和筛选状态
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { KnowledgeDocument, FolderInfo, BatchUploadFileResult } from '../types'
import {
  getKnowledgeList, getFolders, deleteKnowledgeDocument,
  moveKnowledgeDocument, uploadDocumentsAsync, getUploadTaskStatus,
} from '../api/knowledge'


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

  /** 异步上传任务的逐文件实时进度 */
  const taskFiles = ref<BatchUploadFileResult[]>([])

  /** 任务进度：已完成文件数 / 总数 */
  const taskDone = ref(0)
  const taskTotal = ref(0)

  /** 管理面鉴权失败（401），需要重新登录 */
  const needsAuth = ref(false)

  /** 识别管理接口的 401 鉴权失败：置位弹窗标记并清除失效令牌 */
  function markAuthError(error: any): void {
    if (error?.response?.status === 401) {
      needsAuth.value = true
    }
  }

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
    } catch (error: any) {
      markAuthError(error)
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
   * 批量上传文档到知识库（异步任务 + 轮询逐文件进度）
   *
   * @param files - 要上传的文件数组
   * @param folder - 目标文件夹名称
   * @returns 上传结果汇总消息
   */
  async function upload(files: File[], folder: string): Promise<string> {
    uploading.value = true
    taskFiles.value = []
    taskDone.value = 0
    taskTotal.value = files.length
    try {
      // 1. 提交异步任务（立即返回任务 ID）
      const { task_id } = await uploadDocumentsAsync(files, folder)

      // 2. 轮询任务进度（1.2s 间隔，最长 10 分钟）
      const deadline = Date.now() + 10 * 60 * 1000
      let status
      while (Date.now() < deadline) {
        await new Promise(resolve => setTimeout(resolve, 1200))
        status = await getUploadTaskStatus(task_id)
        taskFiles.value = status.files
        taskDone.value = status.done
        if (status.state === 'done') break
      }
      if (!status || status.state !== 'done') {
        throw new Error('上传任务超时，请稍后在文档列表中确认结果')
      }

      // 3. 完成后刷新列表和文件夹
      await loadDocuments()
      await loadFolders()
      return status.message || '上传完成'
    } catch (error: any) {
      markAuthError(error)
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
      markAuthError(error)
      const msg = error?.response?.data?.detail || error.message || '删除失败'
      throw new Error(msg)
    }
  }

  /**
   * 移动文档到其他文件夹（输入不存在的分类名即创建）
   *
   * @param docId - 文档 ID
   * @param folder - 目标文件夹名称（留空归入未分类）
   * @returns 操作结果消息
   */
  async function moveDocument(docId: string, folder: string): Promise<string> {
    try {
      const response = await moveKnowledgeDocument(docId, folder)
      if (response.success) {
        // 移动后刷新列表和文件夹计数
        await loadDocuments()
        await loadFolders()
      }
      return response.message
    } catch (error: any) {
      markAuthError(error)
      const msg = error?.response?.data?.detail || error.message || '移动失败'
      throw new Error(msg)
    }
  }

  return {
    documents, total, loading, uploading,
    folders, selectedFolder,
    taskFiles, taskDone, taskTotal,
    needsAuth,
    loadDocuments, loadFolders, setFolderFilter,
    upload, removeDocument, moveDocument,
  }
})
