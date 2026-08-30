/**
 * API 错误提取单元测试
 */
import { describe, expect, it } from 'vitest'
import { extractApiError } from '../src/utils/apiError'

describe('extractApiError', () => {
  it('字符串 detail 原样返回（如 账号或密码错误）', () => {
    const error = { response: { data: { detail: '账号或密码错误' } } }
    expect(extractApiError(error)).toBe('账号或密码错误')
  })

  it('422 数组 detail 转为可读中文', () => {
    const error = {
      response: {
        data: {
          detail: [
            { type: 'string_too_short', loc: ['body', 'username'], msg: 'String should have at least 3 characters' },
          ],
        },
      },
    }
    expect(extractApiError(error)).toContain('长度不足')
    expect(extractApiError(error)).toContain('username')
  })

  it('后端自定义中文校验消息直接透传', () => {
    const error = {
      response: {
        data: {
          detail: [{ type: 'value_error', loc: ['body', 'password'], msg: '密码至少 6 位' }],
        },
      },
    }
    expect(extractApiError(error)).toBe('密码至少 6 位（password）')
  })

  it('无 detail 时回退到 axios message', () => {
    const error = { message: 'Request failed with status code 500' }
    expect(extractApiError(error, '请求失败')).toBe('Request failed with status code 500')
  })

  it('完全无信息时使用兜底文案', () => {
    expect(extractApiError({}, '操作失败')).toBe('操作失败')
  })
})
