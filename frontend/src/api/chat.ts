/**
 * 聊天相关 API
 */
import api from './index'
import type { ChatResponse, SourceRef } from '../types'

/** 云端聊天记录条目 */
export interface ChatHistoryMessage {
  role: 'user' | 'assistant'
  content: string
  sources: SourceRef[]
  created_at: string
}

/**
 * 发送问题并获取 AI 回答
 * POST /api/chat
 *
 * @param question - 用户问题
 * @returns AI 生成的回答
 */
export async function sendMessage(question: string): Promise<ChatResponse> {
  return api.post('/chat', { question } as never)
}

/**
 * 获取当前登录用户的云端聊天记录
 * GET /api/chat/history（需登录）
 */
export async function getChatHistory(): Promise<{ messages: ChatHistoryMessage[] }> {
  return api.get('/chat/history')
}

/**
 * 清空当前登录用户的云端聊天记录
 * DELETE /api/chat/history（需登录）
 */
export async function clearChatHistory(): Promise<{ cleared: number }> {
  return api.delete('/chat/history')
}

// ==================== 多会话管理 ====================

/**
 * 获取会话列表（按最近更新倒序）
 * GET /api/chat/sessions（需登录）
 */
export async function getSessions(): Promise<{ sessions: { id: string; title: string; created_at: string; updated_at: string }[] }> {
  return api.get('/chat/sessions')
}

/**
 * 新建会话（标题默认"新会话"，首条提问自动成为标题）
 * POST /api/chat/sessions（需登录）
 */
export async function createSession(): Promise<{ id: string; title: string; created_at: string; updated_at: string }> {
  return api.post('/chat/sessions')
}

/**
 * 获取指定会话的聊天记录
 * GET /api/chat/sessions/{id}/messages（需登录）
 */
export async function getSessionMessages(sessionId: string): Promise<{ messages: ChatHistoryMessage[] }> {
  return api.get(`/chat/sessions/${sessionId}/messages`)
}

/**
 * 删除会话及其全部消息
 * DELETE /api/chat/sessions/{id}（需登录）
 */
export async function deleteSession(sessionId: string): Promise<{ deleted: boolean }> {
  return api.delete(`/chat/sessions/${sessionId}`)
}

/**
 * 清空指定会话的聊天记录（保留会话）
 * DELETE /api/chat/sessions/{id}/messages（需登录）
 */
export async function clearSessionMessages(sessionId: string): Promise<{ cleared: number }> {
  return api.delete(`/chat/sessions/${sessionId}/messages`)
}
