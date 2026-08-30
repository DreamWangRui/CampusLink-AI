/**
 * 聊天 Store 持久化测试（stub localStorage，不依赖浏览器环境）
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

// localStorage 内存桩（Node 环境无此对象）
const storage = new Map<string, string>()
vi.stubGlobal('localStorage', {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => storage.delete(key),
})

const KEY = 'campuslink_chat_history'

import { useChatStore } from '../src/store/chat'

describe('chat store 持久化', () => {
  beforeEach(() => {
    storage.clear()
    setActivePinia(createPinia())
  })

  it('初始化时从 localStorage 恢复历史，过滤非法数据', async () => {
    storage.set(
      KEY,
      JSON.stringify([
        { role: 'user', content: '你好', time: '10:00' },
        { role: 'invalid', content: '坏数据' },
        { role: 'assistant', content: '', time: '10:01' },
        { content: '缺角色' },
        { role: 'assistant', content: '好的，请问有什么可以帮你？', time: '10:02' },
      ]),
    )
    const store = useChatStore()
    // 5 条中只有 2 条合法
    expect(store.messages.length).toBe(2)
    expect(store.messages[0].content).toBe('你好')
    expect(store.messages[1].content).toBe('好的，请问有什么可以帮你？')
  })

  it('损坏的 JSON 静默降级为空列表', async () => {
    storage.set(KEY, '{not valid json')
    const store = useChatStore()
    expect(store.messages).toEqual([])
  })

  it('消息变化时同步写入 localStorage', async () => {
    const store = useChatStore()
    store.messages.push({ role: 'user', content: '测试持久化', time: '10:00' })
    await nextTick()
    const saved = JSON.parse(storage.get(KEY) ?? '[]')
    expect(saved).toHaveLength(1)
    expect(saved[0].content).toBe('测试持久化')
  })

  it('清空对话后持久化空列表', async () => {
    storage.set(KEY, JSON.stringify([{ role: 'user', content: '历史消息', time: '10:00' }]))
    const store = useChatStore()
    expect(store.messages.length).toBe(1)

    store.clear()
    await nextTick()
    expect(JSON.parse(storage.get(KEY) ?? '[]')).toEqual([])
    expect(store.messages).toEqual([])
  })

  it('流式回答完成后持久化完整内容（回归：响应式代理变更检测）', async () => {
    // 模拟 SSE 流式响应
    const sseBody = [
      'data: {"type":"meta","sources":[{"filename":"a.pdf","distance":0.4}],"fallback":false}',
      'data: {"type":"delta","content":"回答第一段"}',
      'data: {"type":"delta","content":"回答第二段"}',
      'data: {"type":"done"}',
      '',
    ].join('\n\n')
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(sseBody, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })),
    )

    const store = useChatStore()
    await store.send('测试问题')
    await nextTick()

    const saved = JSON.parse(storage.get(KEY) ?? '[]')
    // 用户消息 + 完整的 AI 回答（此前 raw 对象变更不触发 watch，回答存成空串）
    expect(saved).toHaveLength(2)
    expect(saved[1].content).toBe('回答第一段回答第二段')
    expect(saved[1].sources).toHaveLength(1)
  })

  it('恢复的历史可继续用于多轮追问的历史组装（上限校验）', async () => {
    storage.set(
      KEY,
      JSON.stringify(
        Array.from({ length: 60 }, (_, i) => ({
          role: i % 2 ? 'assistant' : 'user',
          content: `消息${i}`,
          time: '10:00',
        })),
      ),
    )
    const store = useChatStore()
    // 超过 50 条上限时只保留最近 50 条
    expect(store.messages.length).toBe(50)
    expect(store.messages[0].content).toBe('消息10')
  })
})
