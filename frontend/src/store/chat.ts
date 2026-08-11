/**
 * 聊天状态管理（Pinia Store）
 * 管理聊天消息列表和发送状态
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatMessage } from '../types'
import { sendMessage } from '../api/chat'

export const useChatStore = defineStore('chat', () => {
  // ==================== 状态 ====================
  /** 聊天消息列表 */
  const messages = ref<ChatMessage[]>([])

  /** 是否正在等待 AI 回复 */
  const loading = ref(false)

  // ==================== 操作 ====================

  /**
   * 发送用户消息并获取 AI 回答
   *
   * @param question - 用户输入的问题
   */
  async function send(question: string) {
    // 添加用户消息到列表
    const userMessage: ChatMessage = {
      role: 'user',
      content: question,
      time: new Date().toLocaleTimeString('zh-CN'),
    }
    messages.value.push(userMessage)

    // 设置加载状态
    loading.value = true

    try {
      // 调用后端 API
      const response = await sendMessage(question)
      // 添加 AI 回答到列表
      const aiMessage: ChatMessage = {
        role: 'assistant',
        content: response.answer,
        time: new Date().toLocaleTimeString('zh-CN'),
      }
      messages.value.push(aiMessage)
    } catch (error: any) {
      // 错误时添加提示消息
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: `抱歉，请求失败：${error?.response?.data?.detail || error.message || '网络错误'}`,
        time: new Date().toLocaleTimeString('zh-CN'),
      }
      messages.value.push(errorMessage)
    } finally {
      loading.value = false
    }
  }

  /**
   * 清空聊天记录
   */
  function clear() {
    messages.value = []
  }

  return { messages, loading, send, clear }
})
