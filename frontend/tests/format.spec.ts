/**
 * 格式化工具函数单元测试
 */
import { describe, expect, it } from 'vitest'
import { formatFileSize } from '../src/utils/format'

describe('formatFileSize', () => {
  it('小于 1KB 显示字节', () => {
    expect(formatFileSize(0)).toBe('0 B')
    expect(formatFileSize(512)).toBe('512 B')
    expect(formatFileSize(1023)).toBe('1023 B')
  })

  it('KB 区间保留一位小数', () => {
    expect(formatFileSize(1024)).toBe('1.0 KB')
    expect(formatFileSize(1536)).toBe('1.5 KB')
  })

  it('MB 区间保留一位小数', () => {
    expect(formatFileSize(1024 * 1024)).toBe('1.0 MB')
    expect(formatFileSize(2.5 * 1024 * 1024)).toBe('2.5 MB')
  })
})
