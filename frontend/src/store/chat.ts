/**
 * 聊天状态管理（Pinia Store）
 * 管理聊天消息列表和发送状态，使用 SSE 流式接口逐字渲染回答
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatMessage, SourceRef } from '../types'

/** SSE 数据事件结构 */
interface StreamEvent {
  type: 'meta' | 'delta' | 'error' | 'done'
  sources?: SourceRef[]
  fallback?: boolean
  content?: string
}

export const useChatStore = defineStore('chat', () => {
  // ==================== 状态 ====================
  /** 聊天消息列表 */
  const messages = ref<ChatMessage[]>([])

  /** 是否正在等待 AI 回复 */
  const loading = ref(false)

  // ==================== 操作 ====================

  /**
   * 发送用户消息，通过 SSE 流式接口获取 AI 回答（逐字渲染）
   *
   * @param question - 用户输入的问题
   */
  async function send(question: string) {
    // 添加用户消息到列表
    messages.value.push({
      role: 'user',
      content: question,
      time: new Date().toLocaleTimeString('zh-CN'),
    })

    // 先占位一条 AI 消息，流式过程中持续追加内容
    const aiMessage: ChatMessage = {
      role: 'assistant',
      content: '',
      time: new Date().toLocaleTimeString('zh-CN'),
      sources: [],
    }
    messages.value.push(aiMessage)
    loading.value = true

    try {
      // axios 不支持浏览器端流式读取，这里使用原生 fetch
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      if (!response.ok || !response.body) {
        throw new Error(`请求失败（HTTP ${response.status}）`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // SSE 事件以空行分隔，逐条解析（最后一段可能是半截事件，留到下一轮）
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''
        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data:')) continue
          const event = JSON.parse(line.slice(5).trim()) as StreamEvent
          if (event.type === 'meta') {
            aiMessage.sources = event.sources ?? []
          } else if (event.type === 'delta') {
            aiMessage.content += event.content ?? ''
          } else if (event.type === 'error') {
            aiMessage.content += `\n\n⚠️ ${event.content ?? '生成过程出错'}`
          }
        }
      }
    } catch (error: any) {
      // 流式过程中断/失败：在占位消息上追加错误提示
      const reason = error?.message || '网络错误'
      aiMessage.content += aiMessage.content ? `\n\n⚠️ ${reason}` : `抱歉，请求失败：${reason}`
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
