"""
管理面鉴权
知识库管理接口（上传/删除/移动/列表）需要登录；聊天问答保持公开。

两种通过方式：
1. Authorization: Bearer <token> —— POST /api/auth/login 签发（前端使用）
2. X-Admin-Key: <ADMIN_KEY>      —— 脚本/curl 备选（配置了 ADMIN_KEY 时可用）

默认账号 admin / admin123（ADMIN_USER / ADMIN_PASSWORD 可覆盖）。
令牌为 HMAC-SHA256 签名的到期时间戳（无状态、防篡改）；
SECRET_KEY 未配置时每次启动随机生成，重启后需重新登录。
"""

import hashlib
import hmac
import logging
import secrets
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import config

logger = logging.getLogger(__name__)

ADMIN_KEY_HEADER = "X-Admin-Key"
TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 令牌有效期 7 天

# 登录防爆破：同 IP 连续失败 5 次锁定 5 分钟
_MAX_ATTEMPTS = 5
_LOCK_SECONDS = 300
_login_attempts: dict[str, list] = {}  # ip -> [失败次数, 锁定截止时间戳]

# 模块级随机密钥（SECRET_KEY 未配置时用，保证进程内签名一致）
_fallback_secret = secrets.token_hex(32)

router = APIRouter(prefix="/api/auth", tags=["鉴权"])


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="账号", min_length=1, max_length=50)
    password: str = Field(..., description="密码", min_length=1, max_length=100)


class LoginResponse(BaseModel):
    """登录响应"""
    token: str = Field(..., description="访问令牌（Authorization: Bearer <token>）")
    expires_in: int = Field(..., description="令牌有效期（秒）")
    username: str = Field(..., description="登录账号")


def _secret() -> bytes:
    return (config.SECRET_KEY or _fallback_secret).encode()


def _issue_token() -> str:
    """签发签名令牌：<到期时间戳>.<HMAC 签名>"""
    expiry = str(int(time.time()) + TOKEN_TTL_SECONDS)
    signature = hmac.new(_secret(), expiry.encode(), hashlib.sha256).hexdigest()
    return f"{expiry}.{signature}"


def verify_token(token: str) -> bool:
    """校验令牌签名与有效期"""
    try:
        expiry, signature = token.split(".", 1)
        if int(expiry) < time.time():
            return False
        expected = hmac.new(_secret(), expiry.encode(), hashlib.sha256).hexdigest()
        return secrets.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


@router.post("/login", summary="管理员登录，签发访问令牌")
def login(request: Request, body: LoginRequest) -> LoginResponse:
    """
    账号密码登录，成功后返回访问令牌。
    同 IP 连续失败 5 次将锁定 5 分钟（防暴力破解）。
    """
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    attempts, locked_until = _login_attempts.get(ip, [0, 0])
    if now < locked_until:
        raise HTTPException(
            status_code=429,
            detail=f"失败次数过多，已临时锁定，请 {int(locked_until - now) + 1} 秒后重试",
        )

    user_ok = secrets.compare_digest(body.username.encode(), config.ADMIN_USER.encode())
    pass_ok = secrets.compare_digest(body.password.encode(), config.ADMIN_PASSWORD.encode())
    if not (user_ok and pass_ok):
        attempts += 1
        if attempts >= _MAX_ATTEMPTS:
            _login_attempts[ip] = [0, now + _LOCK_SECONDS]
            logger.warning("IP %s 登录连续失败 %d 次，临时锁定", ip, _MAX_ATTEMPTS)
        else:
            _login_attempts[ip] = [attempts, 0]
        raise HTTPException(status_code=401, detail="账号或密码错误")

    _login_attempts.pop(ip, None)
    logger.info("管理员 %s 登录成功（%s）", config.ADMIN_USER, ip)
    return LoginResponse(
        token=_issue_token(),
        expires_in=TOKEN_TTL_SECONDS,
        username=config.ADMIN_USER,
    )


def require_admin(request: Request) -> None:
    """
    FastAPI 依赖：校验管理面请求

    通过条件（满足其一）：
    1. Authorization: Bearer <有效令牌>
    2. X-Admin-Key 与 ADMIN_KEY 匹配（配置了 ADMIN_KEY 时）

    Raises:
        HTTPException: 401 未登录/令牌过期/密钥错误
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        if verify_token(auth_header[7:].strip()):
            return
        raise HTTPException(
            status_code=401,
            detail="登录已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    admin_key = config.ADMIN_KEY
    provided = request.headers.get(ADMIN_KEY_HEADER, "")
    if admin_key and provided and secrets.compare_digest(provided, admin_key):
        return

    logger.warning("管理接口鉴权失败: %s %s", request.method, request.url.path)
    raise HTTPException(
        status_code=401,
        detail="请先登录（管理员账号）",
        headers={"WWW-Authenticate": "Bearer"},
    )
