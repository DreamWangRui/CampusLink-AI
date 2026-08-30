/**
 * 聊天状态管理（Pinia Store）
 * 管理聊天消息列表和发送状态，使用 SSE 流式接口逐字渲染回答
 * 聊天记录持久化到 localStorage：刷新页面不丢失（上限 50 条）
 */
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { ChatMessage, HistoryItem, SourceRef } from '../types'
import { useAuthStore } from './auth'
import { clearChatHistory, getChatHistory } from '../api/chat'

/** SSE 数据事件结构 */
interface StreamEvent {
  type: 'meta' | 'delta' | 'error' | 'done'
  sources?: SourceRef[]
  fallback?: boolean
  content?: string
}

const STORAGE_KEY = 'campuslink_chat_history'
const MAX_STORED = 50

/**
 * 从 localStorage 恢复聊天记录（损坏/非法数据静默忽略）
 */
function loadMessages(): ChatMessage[] {
  try {
    if (typeof localStorage === 'undefined') return []
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter(
        (m): m is ChatMessage =>
          !!m &&
          (m.role === 'user' || m.role === 'assistant') &&
          typeof m.content === 'string' &&
          m.content.length > 0,
      )
      .slice(-MAX_STORED)
  } catch {
    return []
  }
}

export const useChatStore = defineStore('chat', () => {
  // ==================== 状态 ====================
  /** 聊天消息列表（启动时从 localStorage 恢复） */
  const messages = ref<ChatMessage[]>(loadMessages())

  /** 是否正在等待 AI 回复 */
  const loading = ref(false)

  // ==================== 持久化 ====================
  // 任何消息变化（发送/流式追加/清空）都同步写入 localStorage
  watch(
    messages,
    () => {
      try {
        if (typeof localStorage === 'undefined') return
        localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.value.slice(-MAX_STORED)))
      } catch {
        // 隐私模式/配额不足时静默降级为仅内存
      }
    },
    { deep: true },
  )

  // ==================== 操作 ====================

  const authStore = useAuthStore()

  /**
   * 已登录时从服务端拉取云端聊天记录（覆盖本地缓存）
   */
  async function syncFromServer() {
    if (!authStore.isLoggedIn) return
    try {
      const resp = await getChatHistory()
      messages.value = resp.messages.map(m => ({
        role: m.role,
        content: m.content,
        time: (m.created_at || '').slice(11, 19) || new Date().toLocaleTimeString('zh-CN'),
        sources: m.sources ?? [],
      }))
    } catch {
      // 拉取失败时保留本地缓存
    }
  }

  // 登录后拉取云端记录；退出后清空本地（匿名重新开始）
  watch(
    () => authStore.isLoggedIn,
    (loggedIn) => {
      if (loggedIn) {
        syncFromServer()
      } else {
        messages.value = []
      }
    },
  )

  // 已登录用户启动时同步云端记录
  if (authStore.isLoggedIn) {
    syncFromServer()
  }

  /**
   * 发送用户消息，通过 SSE 流式接口获取 AI 回答（逐字渲染）
   * 自动携带最近对话历史，支持"那评定比例呢？"这类追问
   * 已登录用户携带令牌，问答自动持久化到云端
   *
   * @param question - 用户输入的问题
   */
  async function send(question: string) {
    // 组装对话历史（当前问题之前的消息，过滤空/错误占位消息，最多 6 条）
    const history: HistoryItem[] = messages.value
      .filter(m => m.content && !m.content.includes('⚠️'))
      .slice(-6)
      .map(m => ({ role: m.role, content: m.content }))

    // 添加用户消息到列表
    messages.value.push({
      role: 'user',
      content: question,
      time: new Date().toLocaleTimeString('zh-CN'),
    })

    // 先占位一条 AI 消息，流式过程中持续追加内容
    // 注意：必须通过 messages.value[i]（响应式代理）追加内容，
    // 直接改原始对象 Vue 检测不到变更——流式渲染与持久化 watch 都会失效
    messages.value.push({
      role: 'assistant',
      content: '',
      time: new Date().toLocaleTimeString('zh-CN'),
      sources: [],
    })
    const aiMessage = messages.value[messages.value.length - 1]
    loading.value = true

    try {
      // axios 不支持浏览器端流式读取，这里使用原生 fetch（带登录令牌供云端持久化）
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (authStore.token) {
        headers['Authorization'] = `Bearer ${authStore.token}`
      }
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers,
        body: JSON.stringify({ question, history }),
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
   * 清空聊天记录（已登录用户同时清空云端历史）
   */
  async function clear() {
    messages.value = []
    if (authStore.isLoggedIn) {
      try {
        await clearChatHistory()
      } catch {
        // 云端清理失败不阻断本地清空
      }
    }
  }

  return { messages, loading, send, clear, syncFromServer }
})
