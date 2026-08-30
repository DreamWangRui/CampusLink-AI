"""
文本切分服务单元测试（纯函数，无外部依赖）
"""
from app.services.splitter_service import _sliding_window_split, split_text


def test_empty_text_returns_empty():
    assert split_text("") == []
    assert split_text("   \n  ") == []


def test_short_text_passthrough():
    text = "只有一句话的内容。"
    assert split_text(text) == [text]


def test_paragraphs_merged_into_chunks():
    # 多个短段落应被合并到接近 chunk_size 的块中，而不是一段一块
    paragraphs = [f"第{i}段：这是一段测试内容，关于校园奖学金的说明。" for i in range(30)]
    text = "\n\n".join(paragraphs)
    chunks = split_text(text, chunk_size=300, chunk_overlap=50)

    assert len(chunks) > 1
    # 除最后一块外，块应被合并到接近目标大小（而非每个小段落独立成块）
    assert all(len(c) > 50 for c in chunks)


def test_oversized_paragraph_sliding_window():
    # 超长段落降级为滑动窗口切分
    text = "长" * 1000
    chunks = split_text(text, chunk_size=300, chunk_overlap=100)

    assert len(chunks) >= 4
    assert all(len(c) <= 300 for c in chunks)
    # 相邻块之间应存在重叠
    assert chunks[0][-50:] in chunks[1] or chunks[1][:50] in chunks[0]


def test_sliding_window_step_prevents_infinite_loop():
    # overlap >= size 的非法参数不应死循环
    chunks = _sliding_window_split("字" * 100, chunk_size=50, chunk_overlap=60)
    assert len(chunks) >= 2


def test_semantic_boundaries_respected():
    # 标题行应作为语义边界，标题与其后内容尽量在同一块
    text = "## 奖学金评定\n金额为 5000 元。\n\n## 宿舍管理\n门禁时间为 23:00。\n\n## 校医院\n工作日开放。"
    chunks = split_text(text, chunk_size=200, chunk_overlap=20)
    joined = "\n".join(chunks)
    # 内容不丢失
    assert "5000" in joined and "门禁" in joined and "校医院" in joined
