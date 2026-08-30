"""
FastAPI 应用入口
创建并配置 FastAPI 应用，注册路由，配置 CORS 中间件
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.document import router as document_router
from app.api.knowledge import router as knowledge_router

logger = logging.getLogger(__name__)


# ==================== 应用生命周期管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 应用生命周期管理
    在应用启动时加载 Embedding 模型，关闭时清理资源
    """
    # 启动阶段：预加载 Embedding 模型（避免首次请求时等待）
    logger.info("=" * 20 + " CampusLink AI 后端服务启动中 " + "=" * 20)
    try:
        from app.services.embedding_service import get_embedding_model
        t0 = time.time()
        get_embedding_model()
        logger.info("Embedding 模型加载完成（%.1fs）", time.time() - t0)
    except Exception as e:
        logger.error("Embedding 模型加载失败: %s（将尝试在首次使用时下载）", e)

    logger.info("CampusLink AI 后端服务已启动：API 文档 http://localhost:8000/docs")

    # 管理面鉴权状态告警
    from app import config as app_config
    if app_config.ADMIN_PASSWORD == "admin123":
        logger.warning(
            "!! 管理员密码为默认值（admin/admin123），生产环境请在 .env 中设置 "
            "ADMIN_USER / ADMIN_PASSWORD !!"
        )
    if app_config.ADMIN_KEY:
        logger.info("X-Admin-Key 备选鉴权已启用")
    if not app_config.SECRET_KEY:
        logger.info("SECRET_KEY 未配置：令牌密钥为本次启动随机生成，重启后需重新登录")

    yield  # 应用运行期间

    # 关闭阶段
    logger.info("CampusLink AI 后端服务正在关闭")


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


# ==================== 请求耗时日志中间件 ====================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    # 健康检查与轮询请求噪音较大，仅记录耗时超过 1s 的或非轮询请求
    path = request.url.path
    if "/status/" not in path and path != "/api/health":
        logger.info("%s %s -> %d (%.0fms)", request.method, path, response.status_code, duration_ms)
    return response


# ==================== 注册路由 ====================
app.include_router(auth_router)        # 鉴权接口: POST /api/auth/login
app.include_router(chat_router)        # 聊天接口: POST /api/chat, /api/chat/stream
app.include_router(document_router)    # 文档上传接口
app.include_router(knowledge_router)   # 知识库管理接口


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
