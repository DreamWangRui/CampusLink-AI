/**
 * API 错误信息提取
 * FastAPI 的 422 校验错误 detail 是数组，需转成可读中文；其余取字符串 detail
 */

/** 常见校验错误类型的中文翻译 */
const TYPE_MAP: Record<string, string> = {
  string_too_short: '长度不足',
  string_too_long: '超过长度限制',
  string_pattern_mismatch: '包含不允许的字符',
  missing: '缺少必填项',
}

export function extractApiError(error: any, fallback = '请求失败'): string {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d: any) => {
        const field = (d.loc ?? []).filter((x: any) => x !== 'body').join('.')
        const msg = TYPE_MAP[d.type] ?? d.msg ?? '校验失败'
        return field ? `${msg}（${field}）` : msg
      })
      .join('；')
  }
  return error?.message || fallback
}
