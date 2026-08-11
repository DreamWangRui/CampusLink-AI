"""
RAG 服务（检索增强生成核心编排层）
串联检索和生成流程：
1. 用户提问 → 向量化
2. 语义检索 → Top K 相关片段
3. 构造 Prompt → 调用 LLM 生成回答
"""

from app.services.embedding_service import embed_text
from app.database.chroma_client import search_similar
from app.services.llm_service import generate_answer
from app.config import TOP_K


def rag_query(question: str) -> tuple[str, list[dict]]:
    """
    执行完整的 RAG 问答流程

    流程：
        用户提问 → 向量检索 → Top K 相关片段 → DeepSeek 生成 → 返回答案

    Args:
        question: 用户原始问题

    Returns:
        tuple[str, list[dict]]: (AI回答, 检索到的相关文档片段列表)
    """
    # 步骤 1+2：语义检索
    # ChromaDB 的 query 方法内部会自动调用 EmbeddingFunction 将问题向量化
    # 然后使用余弦相似度检索最相关的 Top K 个文档片段
    retrieved_docs = search_similar(query=question, top_k=TOP_K)

    # 步骤 3：提取检索到的文本内容
    context_chunks = [doc["document"] for doc in retrieved_docs if doc["document"]]

    # 如果知识库为空，返回友好提示
    if not context_chunks:
        return "知识库中暂无内容，请先上传校园相关文档。", []

    # 步骤 4：调用 LLM 生成回答
    # 将检索到的相关内容作为上下文，与用户问题一起送入 DeepSeek
    answer = generate_answer(question=question, context_chunks=context_chunks)

    return answer, retrieved_docs
