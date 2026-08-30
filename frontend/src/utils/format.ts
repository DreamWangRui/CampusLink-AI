/**
 * 通用格式化工具函数
 */

/**
 * 格式化文件大小为可读字符串
 *
 * @param bytes - 字节数
 * @returns 可读字符串（B / KB / MB）
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
