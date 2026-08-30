"""
RAG 服务（检索增强生成核心编排层）
串联检索和生成流程：
1. 用户提问 → 向量化
2. 语义检索 → Top K 相关片段
3. 构造 Prompt → 调用 LLM 生成回答
"""

import logging
import time

from app.config import SIMILARITY_DISTANCE_THRESHOLD, TOP_K
from app.database.chroma_client import get_all_documents, search_similar
from app.services.llm_service import generate_answer

logger = logging.getLogger(__name__)


# ==================== 元问题（询问助手自身）识别 ====================
# "你是谁 / 你能做什么 / 你可以回答哪些问题"这类问题无法也不应通过知识库检索回答，
# 提前识别并直接返回自我介绍（含知识库当前收录内容），避免落入生硬的兜底话术。
# 打招呼类要求整句精确匹配（防止"你好，奖学金金额是多少"被误判），
# 能力询问类允许子串匹配。
_META_EXACT = {"你好", "您好", "在吗", "嗨", "hi", "hello", "帮助", "help"}
_META_CONTAINS = (
    "你是谁", "您是谁", "你叫什么", "您叫什么",
    "你能做什么", "您能做什么", "你可以做什么", "您可以做什么",
    "你会做什么", "您会做什么", "你能干什么", "您能干什么", "自我介绍", "介绍一下自己", "介绍下自己",
    "你可以回答", "你能回答", "您可以回答", "能回答什么", "回答哪些",
    "哪些问题", "什么问题", "有什么功能", "你的功能",
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


def retrieve(question: str) -> tuple[list[str], list[dict], str | None]:
    """
    执行检索阶段：元问题短路 → 向量检索 → 相似度过滤

    Args:
        question: 用户原始问题

    Returns:
        tuple[list[str], list[dict], str | None]:
            (相关片段文本列表, 通过过滤的片段列表, 兜底回答或 None)
            兜底回答非 None 时表示无需调用 LLM，直接返回该文案
    """
    # 步骤 0：元问题（询问助手自身）直接自我介绍，不进入检索流程（零 token、零延迟）
    if _is_meta_question(question):
        logger.info("元问题短路: %s", question[:50])
        return [], [], _meta_answer()

    # 步骤 1+2：语义检索
    # ChromaDB 的 query 方法内部会自动调用 EmbeddingFunction 将问题向量化
    # 然后使用余弦相似度检索最相关的 Top K 个文档片段
    t0 = time.time()
    retrieved_docs = search_similar(query=question, top_k=TOP_K)
    logger.info("检索完成: %d 条命中 (%.0fms)", len(retrieved_docs), (time.time() - t0) * 1000)

    # 知识库整体为空
    if not retrieved_docs:
        return [], [], "知识库中暂无内容，请先上传校园相关文档。"

    # 步骤 3：相似度阈值过滤
    # 距离超过阈值说明内容与问题不相关，继续送入 Prompt 反而可能误导模型，
    # 全部被过滤时直接短路返回，不再调用 LLM（节省 token 且避免编造）。
    # 兜底话术附带知识库主题导航，引导用户换问法或提问已有内容。
    relevant_docs = [
        doc for doc in retrieved_docs
        if doc["distance"] <= SIMILARITY_DISTANCE_THRESHOLD
    ]
    if not relevant_docs:
        logger.info("全部 %d 条命中被阈值 %.2f 过滤，走兜底话术", len(retrieved_docs), SIMILARITY_DISTANCE_THRESHOLD)
        return [], [], (
            f"关于「{question}」，目前知识库中暂无相关信息，请咨询学校相关部门。\n\n"
            f"目前知识库收录了以下内容，你可以这样提问：\n{_build_scope_summary()}\n\n"
            "也可以换个问法再试试～"
        )

    context_chunks = [doc["document"] for doc in relevant_docs if doc["document"]]
    return context_chunks, relevant_docs, None


def _sanitize_history(history: list[dict] | None) -> list[dict]:
    """清洗对话历史：只保留合法角色与非空内容，最多 6 条"""
    clean = [
        {"role": item["role"], "content": item["content"]}
        for item in (history or [])
        if item.get("role") in ("user", "assistant") and item.get("content")
    ]
    return clean[-6:]


def prepare_rag(question: str, history: list[dict] | None = None) -> tuple[list[str], list[dict], str | None, list[dict]]:
    """
    RAG 准备阶段（非流式/流式共用）：追问改写 → 检索 → 阈值过滤

    Args:
        question: 用户最新问题
        history: 最近对话历史（有历史时先做追问改写再检索）

    Returns:
        tuple: (相关片段文本, 过滤后片段列表, 兜底回答或 None, 清洗后的历史)
    """
    clean_history = _sanitize_history(history)

    # 追问改写：有历史时把"那评定比例呢？"改写成独立问题再检索
    search_question = question
    if clean_history:
        from app.services.llm_service import rewrite_question
        rewritten = rewrite_question(question, clean_history)
        if rewritten != question:
            logger.info("追问改写: %r -> %r", question, rewritten)
        search_question = rewritten

    context_chunks, relevant_docs, fallback = retrieve(search_question)
    return context_chunks, relevant_docs, fallback, clean_history


def rag_query(question: str, history: list[dict] | None = None) -> tuple[str, list[dict]]:
    """
    执行完整的 RAG 问答流程（非流式）

    流程：
        元问题识别 → 追问改写 → 向量检索 → 相似度过滤 → DeepSeek 生成（带历史）→ 返回答案

    Args:
        question: 用户原始问题
        history: 最近对话历史（多轮对话）

    Returns:
        tuple[str, list[dict]]: (AI回答, 通过相似度过滤的文档片段列表)
    """
    context_chunks, relevant_docs, fallback, clean_history = prepare_rag(question, history)
    if fallback is not None:
        return fallback, relevant_docs

    answer = generate_answer(question=question, context_chunks=context_chunks, history=clean_history)
    return answer, relevant_docs
