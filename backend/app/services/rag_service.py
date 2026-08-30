"""
RAG 服务（检索增强生成核心编排层）
串联检索和生成流程：
1. 用户提问 → 向量化
2. 语义检索 → Top K 相关片段
3. 构造 Prompt → 调用 LLM 生成回答
"""

from app.services.embedding_service import embed_texts
from app.database.chroma_client import search_similar
from app.services.llm_service import generate_answer
from app.config import TOP_K, SIMILARITY_DISTANCE_THRESHOLD


def rag_query(question: str) -> tuple[str, list[dict]]:
    """
    执行完整的 RAG 问答流程

    流程：
        用户提问 → 向量检索 → 相似度过滤 → Top K 相关片段 → DeepSeek 生成 → 返回答案

    Args:
        question: 用户原始问题

    Returns:
        tuple[str, list[dict]]: (AI回答, 通过相似度过滤的文档片段列表)
    """
    # 步骤 1+2：语义检索
    # ChromaDB 的 query 方法内部会自动调用 EmbeddingFunction 将问题向量化
    # 然后使用余弦相似度检索最相关的 Top K 个文档片段
    retrieved_docs = search_similar(query=question, top_k=TOP_K)

    # 知识库整体为空
    if not retrieved_docs:
        return "知识库中暂无内容，请先上传校园相关文档。", []

    # 步骤 3：相似度阈值过滤
    # 距离超过阈值说明内容与问题不相关，继续送入 Prompt 反而可能误导模型，
    # 全部被过滤时直接短路返回，不再调用 LLM（节省 token 且避免编造）
    relevant_docs = [
        doc for doc in retrieved_docs
        if doc["distance"] <= SIMILARITY_DISTANCE_THRESHOLD
    ]
    if not relevant_docs:
        return "目前知识库暂无相关信息，请咨询学校相关部门。", []

    # 步骤 4：提取检索到的文本内容并调用 LLM 生成回答
    context_chunks = [doc["document"] for doc in relevant_docs if doc["document"]]
    answer = generate_answer(question=question, context_chunks=context_chunks)

    return answer, relevant_docs
