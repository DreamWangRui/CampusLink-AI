"""
聊天 API 路由
处理用户的问答请求：POST /api/chat（非流式）、POST /api/chat/stream（SSE 流式）
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.auth import require_user, verify_token
from app.database import user_db
from app.models.schemas import ChatRequest, ChatResponse, SourceRef
from app.services.llm_service import generate_answer_stream
from app.services.rag_service import prepare_rag, rag_query

logger = logging.getLogger(__name__)

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
        history = [item.model_dump() for item in request.history]
        answer, relevant_docs = rag_query(request.question, history)
        return ChatResponse(answer=answer, sources=_to_sources(relevant_docs))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"问答处理失败: {e!s}")


def _identity_from_request(request) -> tuple[str, str] | None:
    """从 Authorization 头解析登录身份；无头返回 None，无效令牌抛 401"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    parsed = verify_token(auth_header[7:].strip())
    if parsed is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return parsed


@router.get("/chat/history", summary="获取当前用户的云端聊天记录")
def get_chat_history(identity_tuple: tuple[str, str] = Depends(require_user)) -> dict:
    """
    返回当前登录用户的云端聊天记录（按时间正序，最多 200 条）。
    匿名聊天的记录不经过服务端，不在此列。
    """
    role, identity = identity_tuple
    return {"messages": user_db.get_chat_messages(f"{role}:{identity}")}


@router.delete("/chat/history", summary="清空当前用户的云端聊天记录")
def clear_chat_history(identity_tuple: tuple[str, str] = Depends(require_user)) -> dict:
    cleared = user_db.clear_chat_messages(f"{identity_tuple[0]}:{identity_tuple[1]}")
    return {"cleared": cleared}


@router.post("/chat/stream", summary="发送问题进行问答（SSE 流式）")
def chat_stream(http_request: Request, request: ChatRequest) -> StreamingResponse:
    """
    流式问答：以 Server-Sent Events 推送生成过程

    可选携带 Authorization: Bearer <token>（已登录用户）：
    问答完成后该轮对话会持久化到云端历史（GET /api/chat/history 可拉取）。

    事件序列（data: {json}\\n\\n）：
        {"type": "meta", "sources": [...], "fallback": bool}  —— 检索完成，携带参考来源
        {"type": "delta", "content": "..."}                    —— 增量回答文本（可多条）
        {"type": "error", "content": "..."}                    —— 生成过程出错
        {"type": "done"}                                       —— 结束

    兜底场景（元问题 / 无相关内容 / 知识库为空）不调用 LLM，
    fallback 文案通过单个 delta 事件直接下发。
    """
    question = request.question
    history = [item.model_dump() for item in request.history]

    # 可选登录：带令牌则问答后持久化到云端历史；无效令牌直接 401
    identity_pair = _identity_from_request(http_request)

    def event_stream():
        try:
            context_chunks, relevant_docs, fallback, clean_history = prepare_rag(question, history)
            sources = _to_sources(relevant_docs)
            yield f"data: {json.dumps({'type': 'meta', 'sources': [s.model_dump() for s in sources], 'fallback': fallback is not None}, ensure_ascii=False)}\n\n"

            answer_parts: list[str] = []
            had_error = False
            if fallback is not None:
                answer_parts.append(fallback)
                yield f"data: {json.dumps({'type': 'delta', 'content': fallback}, ensure_ascii=False)}\n\n"
            else:
                try:
                    for delta in generate_answer_stream(question, context_chunks, clean_history):
                        answer_parts.append(delta)
                        yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    had_error = True
                    yield f"data: {json.dumps({'type': 'error', 'content': f'生成回答时出错：{e!s}'}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

            # 已登录用户：问答完成后持久化到云端历史（出错的轮次不入库）
            if identity_pair and not had_error and answer_parts:
                role, identity = identity_pair
                try:
                    user_db.append_chat_message(
                        f"{role}:{identity}", "user", question, "[]",
                    )
                    user_db.append_chat_message(
                        f"{role}:{identity}", "assistant", "".join(answer_parts),
                        json.dumps([s.model_dump() for s in sources], ensure_ascii=False),
                    )
                except Exception:
                    logger.exception("云端聊天记录写入失败（不影响问答结果）")
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'问答处理失败：{e!s}'}, ensure_ascii=False)}\n\n"
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
