/**
 * 聊天 Store 多会话与持久化测试（stub localStorage + mock SSE 流）
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

const storage = new Map<string, string>()
vi.stubGlobal('localStorage', {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => storage.delete(key),
})

const SESSIONS_KEY = 'campuslink_chat_sessions'

vi.mock('../src/api/chat', () => ({
  getSessions: vi.fn(async () => ({ sessions: [] })),
  createSession: vi.fn(async () => ({ id: 'srv-1', title: '新会话', created_at: '', updated_at: '' })),
  getSessionMessages: vi.fn(async () => ({ messages: [] })),
  deleteSession: vi.fn(async () => ({ deleted: true })),
  clearSessionMessages: vi.fn(async () => ({ cleared: 0 })),
  getChatHistory: vi.fn(async () => ({ messages: [] })),
  clearChatHistory: vi.fn(async () => ({ cleared: 0 })),
}))

vi.mock('../src/api/auth', () => ({
  login: vi.fn(),
  adminLogin: vi.fn(),
  register: vi.fn(),
  changePassword: vi.fn(),
}))

import { useChatStore } from '../src/store/chat'

function mockSseAnswer(answerText: string) {
  const sseBody = [
    'data: {"type":"meta","sources":[{"filename":"a.pdf","distance":0.4}],"fallback":false}',
    `data: {"type":"delta","content":"${answerText}"}`,
    'data: {"type":"done"}',
    '',
  ].join('\n\n')
  vi.stubGlobal('fetch', vi.fn(async () => new Response(sseBody, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })))
}

describe('chat store：多会话与持久化（匿名本地模式）', () => {
  beforeEach(() => {
    storage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('无本地会话时自动创建一个新会话', () => {
    const store = useChatStore()
    expect(store.sessions).toHaveLength(1)
    expect(store.sessions[0].title).toBe('新会话')
    expect(store.activeId).toBe(store.sessions[0].id)
    expect(store.messages).toEqual([])
  })

  it('恢复本地会话：列表、激活会话与消息', () => {
    storage.set(
      SESSIONS_KEY,
      JSON.stringify([
        { id: 's2', title: '第二个会话', updatedAt: '10:00', messages: [{ role: 'user', content: 's2消息', time: '10:00' }] },
        { id: 's1', title: '第一个会话', updatedAt: '09:00', messages: [{ role: 'user', content: 's1消息', time: '09:00' }] },
      ]),
    )
    storage.set('campuslink_active_session', 's1')

    const store = useChatStore()
    expect(store.sessions.map(s => s.title)).toEqual(['第二个会话', '第一个会话'])
    // 激活的是上次离开时的 s1
    expect(store.activeId).toBe('s1')
    expect(store.messages[0].content).toBe('s1消息')
  })

  it('损坏的会话数据静默降级为新会话', () => {
    storage.set(SESSIONS_KEY, '{broken json')
    const store = useChatStore()
    expect(store.sessions).toHaveLength(1)
    expect(store.messages).toEqual([])
  })

  it('switchSession 切换后加载对应会话的消息', async () => {
    storage.set(
      SESSIONS_KEY,
      JSON.stringify([
        { id: 'a', title: '会话A', updatedAt: '10:00', messages: [{ role: 'user', content: 'A的消息', time: '10:00' }] },
        { id: 'b', title: '会话B', updatedAt: '09:00', messages: [{ role: 'user', content: 'B的消息', time: '09:00' }] },
      ]),
    )
    const store = useChatStore()
    // 默认激活 a
    expect(store.messages[0].content).toBe('A的消息')
    await store.switchSession('b')
    expect(store.activeId).toBe('b')
    expect(store.messages[0].content).toBe('B的消息')
  })

  it('send 后消息持久化进当前会话（回归：响应式代理变更检测）', async () => {
    mockSseAnswer('流式回答内容')
    const store = useChatStore()
    await store.send('测试问题')
    await nextTickTwice()

    expect(store.messages).toHaveLength(2)
    expect(store.messages[1].content).toBe('流式回答内容')

    // 持久化进当前会话
    const saved = JSON.parse(storage.get(SESSIONS_KEY) ?? '[]')
    const active = saved.find((s: any) => s.id === store.activeId)
    expect(active.messages).toHaveLength(2)
    expect(active.messages[1].content).toBe('流式回答内容')
  })

  it('首条用户消息自动成为会话标题', async () => {
    mockSseAnswer('好的')
    const store = useChatStore()
    await store.send('今天食堂几点开门')
    await nextTickTwice()

    const active = store.sessions.find(s => s.id === store.activeId)
    expect(active?.title).toBe('今天食堂几点开门')
  })

  it('clear 清空当前会话消息但保留会话', async () => {
    mockSseAnswer('回答')
    const store = useChatStore()
    await store.send('问题')
    await nextTickTwice()

    await store.clear()
    expect(store.messages).toEqual([])
    expect(store.sessions.length).toBe(1) // 会话保留
    const saved = JSON.parse(storage.get(SESSIONS_KEY) ?? '[]')
    expect(saved[0].messages).toEqual([])
  })

  it('newSession 新建并切换到空会话', async () => {
    mockSseAnswer('回答')
    const store = useChatStore()
    await store.send('第一条')
    await nextTickTwice()

    await store.newSession()
    expect(store.messages).toEqual([])
    expect(store.sessions).toHaveLength(2)
    expect(store.sessions[0].title).toBe('新会话')

    // 切回旧会话，消息还在
    const oldId = store.sessions[1].id
    await store.switchSession(oldId)
    expect(store.messages.length).toBeGreaterThan(0)
  })

  it('超过 50 个会话时截断保留最近的', () => {
    const list = Array.from({ length: 60 }, (_, i) => ({
      id: `s${i}`,
      title: `会话${i}`,
      updatedAt: '10:00',
      messages: [],
    }))
    storage.set(SESSIONS_KEY, JSON.stringify(list))

    const store = useChatStore()
    expect(store.sessions.length).toBe(50)
  })
})

async function nextTickTwice() {
  await nextTick()
  await nextTick()
}
