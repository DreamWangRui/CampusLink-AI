"""
聊天 API 路由
处理用户的问答请求：POST /api/chat
"""

from fastapi import APIRouter, HTTPException
from app.models.schemas import ChatRequest, ChatResponse
from app.services.rag_service import rag_query

# 创建聊天路由
router = APIRouter(prefix="/api", tags=["聊天"])


@router.post("/chat", response_model=ChatResponse, summary="发送问题进行问答")
async def chat(request: ChatRequest) -> ChatResponse:
    """
    接收用户问题，通过 RAG 流程检索知识库并生成回答

    请求示例：
        {"question": "校园卡丢了怎么办？"}

    响应示例：
        {"answer": "根据校园卡管理规定..."}

    Args:
        request: 包含用户问题的请求体

    Returns:
        ChatResponse: 包含 AI 回答的响应体
    """
    try:
        # 调用 RAG 服务执行完整的问答流程：
        # 用户提问 → 向量检索 → Top5 相关片段 → DeepSeek 生成回答
        answer, retrieved_docs = rag_query(request.question)
        return ChatResponse(answer=answer)
    except Exception as e:
        # 捕获所有异常，返回友好的错误提示
        raise HTTPException(status_code=500, detail=f"问答处理失败: {str(e)}")
