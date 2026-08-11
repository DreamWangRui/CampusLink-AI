/**
 * 聊天相关 API
 */
import api from './index'
import type { ChatRequest, ChatResponse } from '../types'

/**
 * 发送问题并获取 AI 回答
 * POST /api/chat
 *
 * @param question - 用户问题
 * @returns AI 生成的回答
 */
export async function sendMessage(question: string): Promise<ChatResponse> {
  return api.post('/chat', { question } as ChatRequest)
}
