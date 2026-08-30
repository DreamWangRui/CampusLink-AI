"""
文本切分服务
将长文档切分为合适大小的文本块（Chunk），用于向量化存储和语义检索
采用"按段落优先 + 滑动窗口兜底"的策略，尽可能保持语义完整性
"""

import re

from app.config import CHUNK_OVERLAP, CHUNK_SIZE


def split_text(text: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    将长文本切分为重叠的文本块

    策略（优先级从高到低）：
    1. 先按段落边界切分（保留自然语义单元）
    2. 短段落合并，直到接近 chunk_size
    3. 超长段落降级为滑动窗口切分

    这样"省政府奖学金金额为5000元"这种紧密关联的信息
    会尽量保留在同一个 Chunk 内，不会被硬生生切断。

    Args:
        text: 待切分的原始文本
        chunk_size: 每个文本块的最大字符数（默认 800）
        chunk_overlap: 相邻文本块之间的重叠字符数（默认 200）

    Returns:
        list[str]: 切分后的文本块列表
    """
    if not text or not text.strip():
        return []

    # 如果文本很短，直接返回
    if len(text) <= chunk_size:
        return [text.strip()]

    # ========== 第1步：按段落切分 ==========
    # 以空行、标题标记(#)、列表标记(-/*)等自然边界切分
    paragraphs = _split_by_paragraphs(text)

    # ========== 第2步：合并短段落 ==========
    merged = _merge_short_paragraphs(paragraphs, chunk_size)

    # ========== 第3步：超长段落降级为滑动窗口 ==========
    chunks = []
    for para in merged:
        if len(para) <= chunk_size:
            chunks.append(para)
        else:
            # 超长段落用滑动窗口切分，但增大 overlap 保证信息不丢失
            chunks.extend(_sliding_window_split(para, chunk_size, chunk_overlap))

    return chunks


def _split_by_paragraphs(text: str) -> list[str]:
    """
    按自然段落边界切分文本
    边界包括：空行、Markdown标题、列表项开始
    """
    # 先按空行切分
    raw_paragraphs = re.split(r'\n\s*\n', text)

    result = []
    for para in raw_paragraphs:
        para = para.strip()
        if not para:
            continue
        # 对于含有多个标题/列表的段落，进一步按行切分
        # 检测是否包含多个"标题开头"的行
        lines = para.split('\n')
        current = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # 遇到标题行或列表项开始，将之前累积的作为一个段落
            if _is_section_boundary(stripped) and current:
                result.append('\n'.join(current))
                current = [stripped]
            else:
                current.append(stripped)
        if current:
            result.append('\n'.join(current))

    return result


def _is_section_boundary(line: str) -> bool:
    """判断一行是否是语义边界（标题、列表项等）"""
    return bool(re.match(r'^(#{1,6}\s|第[一二三四五六七八九十\d]+[章节条款]|[①②③④⑤⑥⑦⑧⑨⑩\d+][\.\、\)）]|[-*•]\s)', line))


def _merge_short_paragraphs(paragraphs: list[str], target_size: int) -> list[str]:
    """
    将短段落合并，使每个 chunk 尽量接近 target_size
    同时保证语义相关的内容在一起
    """
    if not paragraphs:
        return []

    merged = []
    buffer = ""
    buffer_len = 0

    for para in paragraphs:
        para_len = len(para)

        # 如果当前段落本身就接近 target_size，直接作为一个 chunk
        if para_len >= target_size * 0.7:
            if buffer:
                merged.append(buffer)
                buffer = ""
                buffer_len = 0
            merged.append(para)
            continue

        # 如果将当前段落加入 buffer 会超出 target_size，先保存 buffer
        if buffer_len + para_len > target_size and buffer:
            merged.append(buffer)
            buffer = para
            buffer_len = para_len
        else:
            # 合并到 buffer 中
            if buffer:
                buffer += "\n\n" + para
            else:
                buffer = para
            buffer_len = len(buffer)

    # 处理剩余的 buffer
    if buffer:
        merged.append(buffer)

    return merged


def _sliding_window_split(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """
    滑动窗口切分（兜底策略，用于超长段落）
    """
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        # 计算下一个窗口起始位置
        step = chunk_size - chunk_overlap
        if step <= 0:
            step = chunk_size // 2  # 防止死循环
        start += step

    return chunks
