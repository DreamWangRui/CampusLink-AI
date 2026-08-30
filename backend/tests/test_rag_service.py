"""
RAG 服务单元测试（mock 检索与 LLM，不加载模型、不访问网络）
"""
import pytest

from app.services import rag_service


def _fake_doc(distance: float, text: str = "测试片段内容") -> dict:
    return {
        "id": "doc_0",
        "document": text,
        "metadata": {"filename": "测试.pdf", "chunk_index": 0},
        "distance": distance,
    }


@pytest.fixture(autouse=True)
def _patch_llm(monkeypatch):
    """所有用例中 LLM 生成都打桩，避免真实调用"""
    monkeypatch.setattr(rag_service, "generate_answer", lambda question, context_chunks: "LLM回答")


# ==================== 元问题识别 ====================

@pytest.mark.parametrize("question", ["你是谁", "你好", "您可以做什么", "你可以回答哪些问题", "帮助"])
def test_meta_questions_short_circuit(monkeypatch, question):
    """元问题直接返回自我介绍，不触发检索与 LLM"""
    monkeypatch.setattr(
        rag_service, "search_similar",
        lambda **kw: pytest.fail("元问题不应触发检索"),
    )
    answer, docs = rag_service.rag_query(question)
    assert "CampusLink AI" in answer
    assert docs == []


@pytest.mark.parametrize("question", ["你好，奖学金金额是多少", "介绍下奖学金评定办法"])
def test_mixed_or_normal_questions_not_meta(monkeypatch, question):
    """混合句与普通问题不应被误判为元问题"""
    monkeypatch.setattr(rag_service, "search_similar", lambda **kw: [_fake_doc(0.5)])
    monkeypatch.setattr(rag_service, "_build_scope_summary", lambda: "清单")
    answer, _ = rag_service.rag_query(question)
    assert answer == "LLM回答"


# ==================== 阈值过滤与兜底 ====================

def test_threshold_filters_irrelevant_chunks(monkeypatch):
    docs = [_fake_doc(0.5, "相关内容"), _fake_doc(0.95, "无关内容")]
    captured = {}
    monkeypatch.setattr(rag_service, "search_similar", lambda **kw: docs)
    monkeypatch.setattr(
        rag_service, "generate_answer",
        lambda question, context_chunks: captured.update(chunks=context_chunks) or "LLM回答",
    )
    answer, relevant = rag_service.rag_query("奖学金金额")
    assert answer == "LLM回答"
    assert len(relevant) == 1
    assert captured["chunks"] == ["相关内容"]


def test_all_filtered_returns_fallback(monkeypatch):
    monkeypatch.setattr(
        rag_service, "search_similar",
        lambda **kw: [_fake_doc(1.3), _fake_doc(1.5)],
    )
    monkeypatch.setattr(rag_service, "_build_scope_summary", lambda: "- 清单项")
    monkeypatch.setattr(
        rag_service, "generate_answer",
        lambda **kw: pytest.fail("兜底场景不应调用 LLM"),
    )
    answer, docs = rag_service.rag_query("今天天气怎么样")
    assert "今天天气怎么样" in answer
    assert "清单项" in answer
    assert docs == []


def test_empty_kb_returns_hint(monkeypatch):
    monkeypatch.setattr(rag_service, "search_similar", lambda **kw: [])
    answer, docs = rag_service.rag_query("任意问题")
    assert "暂无内容" in answer and docs == []


# ==================== 检索阶段拆分（流式复用同一入口） ====================

def test_retrieve_returns_chunks_and_no_fallback(monkeypatch):
    monkeypatch.setattr(rag_service, "search_similar", lambda **kw: [_fake_doc(0.4, "片段A")])
    chunks, docs, fallback = rag_service.retrieve("正常问题")
    assert chunks == ["片段A"]
    assert len(docs) == 1
    assert fallback is None


def test_meta_short_circuit_via_retrieve(monkeypatch):
    monkeypatch.setattr(
        rag_service, "search_similar",
        lambda **kw: pytest.fail("不应触发检索"),
    )
    _chunks, _docs, fallback = rag_service.retrieve("您能做什么")
    assert fallback is not None and "CampusLink AI" in fallback
