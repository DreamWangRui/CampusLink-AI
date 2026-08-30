/**
 * 聊天状态管理（Pinia Store）
 * 多会话支持：登录用户会话存服务端（跨设备同步）；匿名用户会话存 localStorage（本机可用）
 * 使用 SSE 流式接口逐字渲染回答；聊天记录持久化，刷新不丢失
 */
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { ChatMessage, HistoryItem, SessionMeta, SourceRef } from '../types'
import { useAuthStore } from './auth'
import {
  createSession,
  deleteSession as deleteSessionApi,
  clearSessionMessages as clearSessionMessagesApi,
  getSessionMessages,
  getSessions,
} from '../api/chat'

/** SSE 数据事件结构 */
interface StreamEvent {
  type: 'meta' | 'delta' | 'error' | 'done'
  sources?: SourceRef[]
  fallback?: boolean
  content?: string
  session_id?: string
}

/** 本地（匿名）会话结构：元数据 + 消息一体存储 */
interface LocalSession {
  id: string
  title: string
  updatedAt: string
  messages: ChatMessage[]
}

const LOCAL_SESSIONS_KEY = 'campuslink_chat_sessions'
const LOCAL_ACTIVE_KEY = 'campuslink_active_session'
const MAX_STORED = 50
const DEFAULT_TITLE = '新会话'

function newId(): string {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2) + Date.now().toString(36)
}

function nowTime(): string {
  return new Date().toLocaleTimeString('zh-CN')
}

function loadLocalSessions(): LocalSession[] {
  try {
    if (typeof localStorage === 'undefined') return []
    const raw = localStorage.getItem(LOCAL_SESSIONS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.slice(0, MAX_STORED) : []
  } catch {
    return []
  }
}

function saveLocalSessions(list: LocalSession[]): void {
  try {
    if (typeof localStorage === 'undefined') return
    localStorage.setItem(LOCAL_SESSIONS_KEY, JSON.stringify(list.slice(0, MAX_STORED)))
  } catch {
    // 隐私模式/配额不足时静默降级为仅内存
  }
}

export const useChatStore = defineStore('chat', () => {
  const authStore = useAuthStore()

  // ==================== 状态 ====================
  /** 会话列表（元数据，按最近更新倒序） */
  const sessions = ref<SessionMeta[]>([])
  /** 当前激活会话 */
  const activeId = ref<string | null>(null)
  /** 当前会话的消息列表 */
  const messages = ref<ChatMessage[]>([])
  /** 是否正在等待 AI 回复 */
  const loading = ref(false)

  // ==================== 匿名本地存取 ====================

  function localFind(id: string | null): LocalSession | undefined {
    return loadLocalSessions().find(s => s.id === id)
  }

  function localSaveSession(meta: SessionMeta, msgs: ChatMessage[]): void {
    const list = loadLocalSessions()
    const idx = list.findIndex(s => s.id === meta.id)
    const entry: LocalSession = { ...meta, messages: msgs.slice(-MAX_STORED) }
    if (idx >= 0) list[idx] = entry
    else list.unshift(entry)
    saveLocalSessions(list)
    localStorage.setItem(LOCAL_ACTIVE_KEY, meta.id)
  }

  // ==================== 初始化与登录切换 ====================

  async function initFromServer(): Promise<void> {
    try {
      const resp = await getSessions()
      sessions.value = resp.sessions.map(x => ({ id: x.id, title: x.title, updatedAt: x.updated_at }))
      if (sessions.value.length) {
        await switchSession(sessions.value[0].id)
      } else {
        await newSession()
      }
    } catch {
      initLocal()
    }
  }

  function initLocal(): void {
    const list = loadLocalSessions()
    if (!list.length) {
      const session: LocalSession = {
        id: newId(),
        title: DEFAULT_TITLE,
        updatedAt: nowTime(),
        messages: [],
      }
      saveLocalSessions([session])
    }
    const list2 = loadLocalSessions()
    sessions.value = list2.map(({ id, title, updatedAt }) => ({ id, title, updatedAt }))
    const savedActive = localStorage.getItem(LOCAL_ACTIVE_KEY)
    const active = list2.find(s => s.id === savedActive) ?? list2[0]
    activeId.value = active.id
    messages.value = active.messages
  }

  function init(): void {
    if (authStore.isLoggedIn) {
      initFromServer().catch(() => initLocal())
    } else {
      initLocal()
    }
  }

  // 初始化（登录拉云端会话 / 匿名加载本地会话）
  init()

  // 登录态变化：登录→拉服务端会话；退出→清空并回到本地
  watch(
    () => authStore.isLoggedIn,
    (loggedIn) => {
      messages.value = []
      activeId.value = null
      if (loggedIn) {
        initFromServer().catch(() => initLocal())
      } else {
        initLocal()
      }
    },
  )

  // ==================== 会话操作 ====================

  /** 切换会话并加载其消息 */
  async function switchSession(id: string): Promise<void> {
    activeId.value = id
    if (authStore.isLoggedIn) {
      loading.value = true
      try {
        const resp = await getSessionMessages(id)
        messages.value = resp.messages.map(m => ({
          role: m.role,
          content: m.content,
          time: (m.created_at || '').slice(11, 19) || nowTime(),
          sources: m.sources ?? [],
        }))
      } finally {
        loading.value = false
      }
    } else {
      messages.value = localFind(id)?.messages ?? []
    }
  }

  /** 新建会话 */
  async function newSession(): Promise<void> {
    if (authStore.isLoggedIn) {
      const s = await createSession()
      sessions.value.unshift({ id: s.id, title: s.title, updatedAt: s.updated_at })
      activeId.value = s.id
      messages.value = []
    } else {
      const session: LocalSession = { id: newId(), title: DEFAULT_TITLE, updatedAt: nowTime(), messages: [] }
      const list = loadLocalSessions()
      list.unshift(session)
      saveLocalSessions(list)
      sessions.value = list.map(({ id, title, updatedAt }) => ({ id, title, updatedAt }))
      activeId.value = session.id
      messages.value = []
    }
  }

  /** 删除会话（连同消息）；删除当前会话时自动切换 */
  async function removeSession(id: string): Promise<void> {
    if (authStore.isLoggedIn) {
      await deleteSessionApi(id)
    }
    const list = loadLocalSessions().filter(s => s.id !== id)
    saveLocalSessions(list)
    sessions.value = sessions.value.filter(s => s.id !== id)
    if (activeId.value === id) {
      if (sessions.value.length) {
        await switchSession(sessions.value[0].id)
      } else {
        await newSession()
      }
    }
  }

  /** 清空当前会话的消息（已登录同时清云端） */
  async function clear(): Promise<void> {
    messages.value = []
    if (authStore.isLoggedIn && activeId.value) {
      try {
        await clearSessionMessagesApi(activeId.value)
      } catch {
        // 云端清理失败不阻断本地清空
      }
    }
    if (!authStore.isLoggedIn && activeId.value) {
      const meta = sessions.value.find(s => s.id === activeId.value)
      localSaveSession(
        { id: activeId.value, title: meta?.title ?? DEFAULT_TITLE, updatedAt: nowTime() },
        [],
      )
    }
  }

  // ==================== 发送（SSE 流式） ====================

  /**
   * 发送用户消息到当前会话，SSE 流式渲染回答。
   * 已登录：携带会话 ID 与令牌，问答自动持久化到云端会话
   * （未指定会话时服务端自动新建并通过 meta 事件回传 ID）。
   * 自动携带最近对话历史，支持"那评定比例呢？"这类追问。
   */
  async function send(question: string) {
    // 确保有激活会话
    if (!activeId.value) {
      await newSession()
    }

    // 组装对话历史（当前问题之前的消息，过滤空/错误占位消息，最多 6 条）
    const history: HistoryItem[] = messages.value
      .filter(m => m.content && !m.content.includes('⚠️'))
      .slice(-6)
      .map(m => ({ role: m.role, content: m.content }))

    // 添加用户消息到列表
    messages.value.push({
      role: 'user',
      content: question,
      time: nowTime(),
    })

    // 占位 AI 消息：必须通过响应式代理追加（直接改原始对象 Vue 检测不到变更）
    messages.value.push({
      role: 'assistant',
      content: '',
      time: nowTime(),
      sources: [],
    })
    const aiMessage = messages.value[messages.value.length - 1]
    loading.value = true

    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (authStore.token) {
        headers['Authorization'] = `Bearer ${authStore.token}`
      }
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          question,
          history,
          session_id: authStore.isLoggedIn ? activeId.value : undefined,
        }),
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
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''
        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data:')) continue
          const event = JSON.parse(line.slice(5).trim()) as StreamEvent
          if (event.type === 'meta') {
            aiMessage.sources = event.sources ?? []
            // 服务端自动新建的会话：采纳其 ID 并加入会话列表
            if (authStore.isLoggedIn && event.session_id && event.session_id !== activeId.value) {
              activeId.value = event.session_id
              if (!sessions.value.some(s => s.id === event.session_id)) {
                sessions.value.unshift({
                  id: event.session_id,
                  title: question.slice(0, 30) || DEFAULT_TITLE,
                  updatedAt: nowTime(),
                })
              }
            }
          } else if (event.type === 'delta') {
            aiMessage.content += event.content ?? ''
          } else if (event.type === 'error') {
            aiMessage.content += `\n\n⚠️ ${event.content ?? '生成过程出错'}`
          }
        }
      }
    } catch (error: any) {
      const reason = error?.message || '网络错误'
      aiMessage.content += aiMessage.content ? `\n\n⚠️ ${reason}` : `抱歉，请求失败：${reason}`
    } finally {
      loading.value = false
      // 刷新会话元数据（标题/更新时间）
      if (authStore.isLoggedIn && activeId.value) {
        try {
          const resp = await getSessions()
          sessions.value = resp.sessions.map(x => ({ id: x.id, title: x.title, updatedAt: x.updated_at }))
        } catch {
          // 刷新失败不影响会话
        }
      } else if (activeId.value) {
        const existing = sessions.value.find(s => s.id === activeId.value)
        // 本地模式：会话标题仍为默认值时，首条提问自动成为标题（与服务端行为一致）
        const title = existing?.title === DEFAULT_TITLE ? question.slice(0, 30) : existing?.title ?? DEFAULT_TITLE
        const meta = { id: activeId.value, title, updatedAt: nowTime() }
        localSaveSession(meta, messages.value)
        const idx = sessions.value.findIndex(s => s.id === activeId.value)
        if (idx >= 0) sessions.value[idx] = meta
      }
    }
  }

  // 本地模式：消息变化同步进 localStorage（服务端模式由服务端持久化）
  watch(
    messages,
    () => {
      if (!authStore.isLoggedIn && activeId.value) {
        const meta = sessions.value.find(s => s.id === activeId.value)
        localSaveSession(
          { id: activeId.value, title: meta?.title ?? DEFAULT_TITLE, updatedAt: nowTime() },
          messages.value,
        )
      }
    },
    { deep: true },
  )

  return {
    sessions, activeId, messages, loading,
    switchSession, newSession, removeSession,
    send, clear,
  }
})
