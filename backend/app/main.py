"""
FastAPI 应用入口
创建并配置 FastAPI 应用，注册路由，配置 CORS 中间件
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.document import router as document_router
from app.api.knowledge import router as knowledge_router


# ==================== 应用生命周期管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 应用生命周期管理
    在应用启动时加载 Embedding 模型，关闭时清理资源
    """
    # 启动阶段：预加载 Embedding 模型
    print("=" * 50)
    print("CampusLink AI 后端服务启动中...")
    print("=" * 50)
    # 预加载 embedding 模型（避免首次请求时等待）
    try:
        from app.services.embedding_service import get_embedding_model
        get_embedding_model()
        print("[OK] Embedding 模型加载完成")
    except Exception as e:
        print(f"[ERROR] Embedding 模型加载失败: {e}")
        print("请确保网络连接正常，模型将在首次使用时自动下载")

    print("[OK] ChromaDB 持久化目录已就绪")
    print("=" * 50)
    print("CampusLink AI 后端服务已启动！")
    print("API 文档: http://localhost:8000/docs")
    print("=" * 50)

    yield  # 应用运行期间

    # 关闭阶段：清理资源
    print("CampusLink AI 后端服务正在关闭...")


# ==================== 创建 FastAPI 应用 ====================
app = FastAPI(
    title="CampusLink AI",
    description="基于 RAG 的校园智能问答系统 API",
    version="1.0.0",
    lifespan=lifespan,
)

# ==================== CORS 中间件配置 ====================
# 允许前端跨域访问（前后端分离架构）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite 开发服务器
        "http://localhost:3000",   # 备用端口
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)

# ==================== 注册路由 ====================
app.include_router(chat_router)        # 聊天接口: POST /api/chat
app.include_router(document_router)     # 文档上传接口: POST /api/document/upload
app.include_router(knowledge_router)    # 知识库管理接口: GET /api/knowledge/list, DELETE /api/knowledge/delete


# ==================== 健康检查接口 ====================
@app.get("/api/health", tags=["系统"])
async def health_check():
    """
    健康检查接口，用于验证服务是否正常运行

    Returns:
        dict: 包含服务状态信息的字典
    """
    from app.database.chroma_client import get_collection
    try:
        collection = get_collection()
        doc_count = collection.count()
        return {
            "status": "ok",
            "service": "CampusLink AI",
            "version": "1.0.0",
            "knowledge_base_docs": doc_count,
        }
    except Exception as e:
        return {
            "status": "error",
            "service": "CampusLink AI",
            "version": "1.0.0",
            "error": str(e),
        }
