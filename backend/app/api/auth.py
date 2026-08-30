"""
管理面鉴权
知识库管理接口（上传/删除/移动/列表）要求管理员密钥；聊天问答保持公开。
密钥通过环境变量 ADMIN_KEY 配置；未配置时放行（开发模式）并已在启动日志告警。
"""

import logging
import secrets

from fastapi import HTTPException, Request

from app import config

logger = logging.getLogger(__name__)

ADMIN_KEY_HEADER = "X-Admin-Key"


def require_admin(request: Request) -> None:
    """
    FastAPI 依赖：校验管理面请求的管理员密钥

    校验使用 secrets.compare_digest 防时序攻击；
    ADMIN_KEY 未配置时放行（开发模式）。

    Raises:
        HTTPException: 401 密钥缺失或错误
    """
    expected = config.ADMIN_KEY
    if not expected:
        return  # 开发模式：未配置密钥

    provided = request.headers.get(ADMIN_KEY_HEADER, "")
    if not provided or not secrets.compare_digest(provided, expected):
        logger.warning("管理接口鉴权失败: %s %s", request.method, request.url.path)
        raise HTTPException(
            status_code=401,
            detail="需要管理员密钥（X-Admin-Key 请求头）",
            headers={"WWW-Authenticate": "ApiKey"},
        )
