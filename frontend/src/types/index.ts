/**
 * TypeScript 类型定义
 * 与后端 Pydantic 模型对应
 */

// ==================== 聊天相关类型 ====================

/** 聊天请求 */
export interface ChatRequest {
  question: string
}

/** 回答引用的知识库片段来源 */
export interface SourceRef {
  filename: string
  chunk_index?: number | null
  distance: number
}

/** 对话历史条目（多轮对话） */
export interface HistoryItem {
  role: 'user' | 'assistant'
  content: string
}

/** 聊天响应 */
export interface ChatResponse {
  answer: string
  sources: SourceRef[]
}

/** 聊天消息（用于页面展示） */
export interface ChatMessage {
  /** 消息角色：用户或 AI */
  role: 'user' | 'assistant'
  /** 消息内容 */
  content: string
  /** 发送时间 */
  time: string
  /** 回答参考的知识库来源（仅 AI 回答） */
  sources?: SourceRef[]
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

/** 移动文档请求 */
export interface MoveDocumentRequest {
  doc_id: string
  folder: string
}

/** 移动文档响应 */
export interface MoveDocumentResponse {
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

/** 异步上传任务状态（轮询返回） */
export interface UploadTaskStatus {
  task_id: string
  state: 'processing' | 'done'
  files: BatchUploadFileResult[]
  done: number
  total: number
  message: string
}

/** 文件夹/分类信息 */
export interface FolderInfo {
  name: string
  document_count: number
}
