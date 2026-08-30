"""
聊天 API 路由
处理用户的问答请求：POST /api/chat（非流式）、POST /api/chat/stream（SSE 流式）
"""

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.schemas import ChatRequest, ChatResponse, SourceRef
from app.services.rag_service import rag_query, retrieve
from app.services.llm_service import generate_answer_stream

# 创建聊天路由
router = APIRouter(prefix="/api", tags=["聊天"])


def _to_sources(relevant_docs: list[dict]) -> list[SourceRef]:
    """将检索结果转换为来源引用列表"""
    return [
        SourceRef(
            filename=doc["metadata"].get("filename", "未知文档"),
            chunk_index=doc["metadata"].get("chunk_index"),
            distance=round(doc["distance"], 3),
        )
        for doc in relevant_docs
    ]


@router.post("/chat", response_model=ChatResponse, summary="发送问题进行问答（非流式）")
def chat(request: ChatRequest) -> ChatResponse:
    """
    接收用户问题，通过 RAG 流程检索知识库并生成回答

    请求示例：
        {"question": "校园卡丢了怎么办？"}

    响应示例：
        {"answer": "根据校园卡管理规定...", "sources": [{"filename": "xxx.pdf", ...}]}

    Args:
        request: 包含用户问题的请求体

    Returns:
        ChatResponse: 包含 AI 回答与参考来源的响应体

    Note:
        使用同步 def 而非 async def：RAG 流程包含 CPU 密集的向量化计算和
        阻塞的 LLM 网络调用，FastAPI 会将同步端点放入线程池执行，
        避免阻塞事件循环导致其他请求排队。
    """
    try:
        answer, relevant_docs = rag_query(request.question)
        return ChatResponse(answer=answer, sources=_to_sources(relevant_docs))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"问答处理失败: {str(e)}")


@router.post("/chat/stream", summary="发送问题进行问答（SSE 流式）")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    """
    流式问答：以 Server-Sent Events 推送生成过程

    事件序列（data: {json}\\n\\n）：
        {"type": "meta", "sources": [...], "fallback": bool}  —— 检索完成，携带参考来源
        {"type": "delta", "content": "..."}                    —— 增量回答文本（可多条）
        {"type": "error", "content": "..."}                    —— 生成过程出错
        {"type": "done"}                                       —— 结束

    兜底场景（元问题 / 无相关内容 / 知识库为空）不调用 LLM，
    fallback 文案通过单个 delta 事件直接下发。
    """
    question = request.question

    def event_stream():
        try:
            context_chunks, relevant_docs, fallback = retrieve(question)
            sources = _to_sources(relevant_docs)
            yield f"data: {json.dumps({'type': 'meta', 'sources': [s.model_dump() for s in sources], 'fallback': fallback is not None}, ensure_ascii=False)}\n\n"

            if fallback is not None:
                yield f"data: {json.dumps({'type': 'delta', 'content': fallback}, ensure_ascii=False)}\n\n"
            else:
                try:
                    for delta in generate_answer_stream(question, context_chunks):
                        yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'content': f'生成回答时出错：{str(e)}'}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'问答处理失败：{str(e)}'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            # 告知 Nginx 等反代关闭响应缓冲，否则流式事件会被攒到结束才下发
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        },
    )
