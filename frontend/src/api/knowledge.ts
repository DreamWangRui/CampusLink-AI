/**
 * 知识库管理相关 API
 */
import api from './index'
import type { KnowledgeListResponse, DeleteDocumentResponse, MoveDocumentResponse, BatchUploadResponse, FolderInfo } from '../types'

/**
 * 获取知识库文档列表（支持按文件夹筛选）
 * GET /api/knowledge/list
 *
 * @param folder - 可选，按文件夹名称筛选
 * @returns 文档列表和总数
 */
export async function getKnowledgeList(folder?: string): Promise<KnowledgeListResponse> {
  const params = folder ? { folder } : {}
  return api.get('/knowledge/list', { params })
}

/**
 * 获取所有文件夹/分类列表
 * GET /api/knowledge/folders
 *
 * @returns 文件夹列表，每项含名称和文档数量
 */
export async function getFolders(): Promise<{ folders: FolderInfo[] }> {
  return api.get('/knowledge/folders')
}

/**
 * 删除指定文档
 * DELETE /api/knowledge/delete
 *
 * @param docId - 要删除的文档 ID
 * @returns 操作结果
 */
export async function deleteKnowledgeDocument(docId: string): Promise<DeleteDocumentResponse> {
  return api.delete('/knowledge/delete', { data: { doc_id: docId } })
}

/**
 * 移动文档到其他文件夹（输入不存在的分类名即创建）
 * PUT /api/knowledge/move
 *
 * @param docId - 要移动的文档 ID
 * @param folder - 目标文件夹名称（留空归入未分类）
 * @returns 操作结果
 */
export async function moveKnowledgeDocument(docId: string, folder: string): Promise<MoveDocumentResponse> {
  return api.put('/knowledge/move', { doc_id: docId, folder })
}

/**
 * 批量上传文档到知识库
 * POST /api/document/upload
 *
 * @param files - 要上传的文件数组
 * @param folder - 目标文件夹名称（可选）
 * @returns 批量上传结果
 */
export async function uploadDocuments(files: File[], folder: string): Promise<BatchUploadResponse> {
  const formData = new FormData()
  // 多次 append 同名 'files' 字段，FastAPI 自动解析为 list[UploadFile]
  files.forEach(file => formData.append('files', file))
  if (folder) {
    formData.append('folder', folder)
  }
  return api.post('/document/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000, // 批量上传 + 解析 + 向量化可能需要较长时间（5 分钟）
  })
}
