"""
RAG 服务（检索增强生成核心编排层）
串联检索和生成流程：
1. 用户提问 → 向量化
2. 语义检索 → Top K 相关片段
3. 构造 Prompt → 调用 LLM 生成回答
"""

from app.services.embedding_service import embed_texts
from app.database.chroma_client import search_similar, get_all_documents
from app.services.llm_service import generate_answer
from app.config import TOP_K, SIMILARITY_DISTANCE_THRESHOLD


# ==================== 元问题（询问助手自身）识别 ====================
# "你是谁 / 你能做什么 / 你可以回答哪些问题"这类问题无法也不应通过知识库检索回答，
# 提前识别并直接返回自我介绍（含知识库当前收录内容），避免落入生硬的兜底话术。
# 打招呼类要求整句精确匹配（防止"你好，奖学金金额是多少"被误判），
# 能力询问类允许子串匹配。
_META_EXACT = {"你好", "您好", "在吗", "嗨", "hi", "hello", "帮助", "help"}
_META_CONTAINS = (
    "你是谁", "你叫什么", "你能做什么", "你可以做什么", "你会做什么",
    "你能干什么", "自我介绍", "介绍一下自己", "介绍下自己",
    "你可以回答", "你能回答", "能回答什么", "回答哪些", "哪些问题", "什么问题",
    "有什么功能", "你的功能",
)


def _is_meta_question(question: str) -> bool:
    """判断用户问题是否为询问助手自身能力的元问题"""
    q = question.strip().lower()
    return q in _META_EXACT or any(keyword in q for keyword in _META_CONTAINS)


def _build_scope_summary() -> str:
    """
    生成知识库收录内容的摘要清单（用于自我介绍和兜底话术的主题导航）
    """
    docs = get_all_documents()
    if not docs:
        return "（知识库目前还没有文档，请在「知识库管理」页面上传校园相关文档）"
    lines = [
        f"- {doc['folder'] or '未分类'}｜{doc['filename']}（{doc['chunk_count']} 个片段）"
        for doc in sorted(docs, key=lambda x: (x["folder"], x["filename"]))
    ]
    return "\n".join(lines)


def _meta_answer() -> str:
    """生成助手自我介绍（动态列出知识库收录内容）"""
    return (
        "你好！我是校园智能助手 CampusLink AI 🎓\n\n"
        "我可以基于知识库回答校园相关问题，目前知识库收录了：\n\n"
        f"{_build_scope_summary()}\n\n"
        "你可以直接问与上述内容相关的问题；也欢迎在「知识库管理」页面上传更多文档"
        "（如食堂、宿舍、校历等），我就能回答更多啦～"
    )


def rag_query(question: str) -> tuple[str, list[dict]]:
    """
    执行完整的 RAG 问答流程

    流程：
        元问题识别 → 向量检索 → 相似度过滤 → Top K 相关片段 → DeepSeek 生成 → 返回答案

    Args:
        question: 用户原始问题

    Returns:
        tuple[str, list[dict]]: (AI回答, 通过相似度过滤的文档片段列表)
    """
    # 步骤 0：元问题（询问助手自身）直接自我介绍，不进入检索流程（零 token、零延迟）
    if _is_meta_question(question):
        return _meta_answer(), []

    # 步骤 1+2：语义检索
    # ChromaDB 的 query 方法内部会自动调用 EmbeddingFunction 将问题向量化
    # 然后使用余弦相似度检索最相关的 Top K 个文档片段
    retrieved_docs = search_similar(query=question, top_k=TOP_K)

    # 知识库整体为空
    if not retrieved_docs:
        return "知识库中暂无内容，请先上传校园相关文档。", []

    # 步骤 3：相似度阈值过滤
    # 距离超过阈值说明内容与问题不相关，继续送入 Prompt 反而可能误导模型，
    # 全部被过滤时直接短路返回，不再调用 LLM（节省 token 且避免编造）。
    # 兜底话术附带知识库主题导航，引导用户换问法或提问已有内容。
    relevant_docs = [
        doc for doc in retrieved_docs
        if doc["distance"] <= SIMILARITY_DISTANCE_THRESHOLD
    ]
    if not relevant_docs:
        return (
            f"关于「{question}」，目前知识库中暂无相关信息，请咨询学校相关部门。\n\n"
            f"目前知识库收录了以下内容，你可以这样提问：\n{_build_scope_summary()}\n\n"
            "也可以换个问法再试试～"
        ), []

    # 步骤 4：提取检索到的文本内容并调用 LLM 生成回答
    context_chunks = [doc["document"] for doc in relevant_docs if doc["document"]]
    answer = generate_answer(question=question, context_chunks=context_chunks)

    return answer, relevant_docs
