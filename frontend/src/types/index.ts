/**
 * TypeScript 类型定义
 * 与后端 Pydantic 模型对应
 */

// ==================== 聊天相关类型 ====================

/** 聊天请求 */
export interface ChatRequest {
  question: string
}

/** 聊天响应 */
export interface ChatResponse {
  answer: string
}

/** 聊天消息（用于页面展示） */
export interface ChatMessage {
  /** 消息角色：用户或 AI */
  role: 'user' | 'assistant'
  /** 消息内容 */
  content: string
  /** 发送时间 */
  time: string
}

// ==================== 知识库相关类型 ====================

/** 知识库文档信息 */
export interface KnowledgeDocument {
  id: string
  filename: string
  folder: string
  upload_time: string
  chunk_count: number
}

/** 知识库文档列表响应 */
export interface KnowledgeListResponse {
  documents: KnowledgeDocument[]
  total: number
}

/** 删除文档响应 */
export interface DeleteDocumentResponse {
  success: boolean
  message: string
}

/** 批量上传中单个文件的结果 */
export interface BatchUploadFileResult {
  success: boolean
  filename: string
  chunk_count: number
  message: string
}

/** 批量上传响应 */
export interface BatchUploadResponse {
  files: BatchUploadFileResult[]
  total_chunks: number
  message: string
}

/** 文件夹/分类信息 */
export interface FolderInfo {
  name: string
  document_count: number
}
