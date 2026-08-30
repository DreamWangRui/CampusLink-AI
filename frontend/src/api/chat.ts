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
