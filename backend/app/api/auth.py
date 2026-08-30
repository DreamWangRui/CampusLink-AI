"""
管理面鉴权
知识库管理接口（上传/删除/移动/列表）需要管理员登录；聊天问答保持公开，
普通用户可选注册/登录以同步聊天记录。

两种通过方式：
1. Authorization: Bearer <token> —— POST /api/auth/login 签发（前端使用）
2. X-Admin-Key: <ADMIN_KEY>      —— 脚本/curl 备选（配置了 ADMIN_KEY 时可用）

令牌为 HMAC-SHA256 签名的「角色.身份.到期时间」（无状态、防篡改），分两种角色：
- admin：知识库管理员（默认 admin / admin123，可 env 覆盖）
- user：注册的普通用户
"""

import base64
import hashlib
import hmac
import logging
import secrets
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import config
from app.database import user_db

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


class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(
        ...,
        description="用户名（3-32 位，字母/数字/下划线/中文）",
        min_length=3,
        max_length=32,
        pattern=r"^[\w]+$",
    )
    password: str = Field(..., description="密码（至少 6 位）", min_length=6, max_length=100)


class LoginResponse(BaseModel):
    """登录响应"""
    token: str = Field(..., description="访问令牌（Authorization: Bearer <token>）")
    expires_in: int = Field(..., description="令牌有效期（秒）")
    username: str = Field(..., description="登录身份")
    role: str = Field(..., description="角色：admin / user")


def _secret() -> bytes:
    return (config.SECRET_KEY or _fallback_secret).encode()


def _issue_token(role: str, identity: str, ttl: int = TOKEN_TTL_SECONDS) -> str:
    """
    签发签名令牌：base64url(<角色>.<身份>.<到期时间戳>) . <HMAC 签名>
    整体 base64url 编码保证 HTTP 头 ASCII 安全（用户名可含中文）
    """
    expiry = str(int(time.time()) + ttl)
    payload = f"{role}.{identity}.{expiry}"
    signature = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    encoded = base64.urlsafe_b64encode(payload.encode()).decode()
    return f"{encoded}.{signature}"


def verify_token(token: str) -> tuple[str, str] | None:
    """校验令牌签名与有效期，有效返回 (角色, 身份)，否则 None"""
    try:
        encoded, signature = token.rsplit(".", 1)
        payload = base64.urlsafe_b64decode(encoded.encode()).decode()
        role, identity, expiry = payload.split(".", 2)
        if int(expiry) < time.time():
            return None
        expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not secrets.compare_digest(signature, expected):
            return None
        if role not in ("admin", "user"):
            return None
        return role, identity
    except (ValueError, TypeError):
        return None


@router.post("/register", summary="注册普通用户")
def register(body: RegisterRequest) -> dict:
    """
    注册普通用户账号（用户名唯一）。管理员账号为内置账号，不可通过注册占用。
    """
    if body.username == config.ADMIN_USER:
        raise HTTPException(status_code=409, detail="该用户名为保留账号，请换一个")
    try:
        user_db.create_user(body.username, body.password)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    logger.info("新用户注册: %s", body.username)
    return {"username": body.username}


@router.post("/login", summary="登录（管理员或普通用户），签发访问令牌")
def login(request: Request, body: LoginRequest) -> LoginResponse:
    """
    统一登录入口：管理员账号与管理员后台配置匹配则签发 admin 令牌；
    否则尝试普通用户表。同 IP 连续失败 5 次将锁定 5 分钟（防暴力破解）。
    """
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    attempts, locked_until = _login_attempts.get(ip, [0, 0])
    if now < locked_until:
        raise HTTPException(
            status_code=429,
            detail=f"失败次数过多，已临时锁定，请 {int(locked_until - now) + 1} 秒后重试",
        )

    def _fail() -> HTTPException:
        nonlocal attempts
        attempts += 1
        if attempts >= _MAX_ATTEMPTS:
            _login_attempts[ip] = [0, now + _LOCK_SECONDS]
            logger.warning("IP %s 登录连续失败 %d 次，临时锁定", ip, _MAX_ATTEMPTS)
        else:
            _login_attempts[ip] = [attempts, 0]
        return HTTPException(status_code=401, detail="账号或密码错误")

    user_ok = secrets.compare_digest(body.username.encode(), config.ADMIN_USER.encode())
    pass_ok = secrets.compare_digest(body.password.encode(), config.ADMIN_PASSWORD.encode())
    if user_ok and pass_ok:
        _login_attempts.pop(ip, None)
        logger.info("管理员 %s 登录成功（%s）", config.ADMIN_USER, ip)
        return LoginResponse(
            token=_issue_token("admin", config.ADMIN_USER),
            expires_in=TOKEN_TTL_SECONDS,
            username=config.ADMIN_USER,
            role="admin",
        )

    if user_db.verify_user(body.username, body.password):
        _login_attempts.pop(ip, None)
        logger.info("用户 %s 登录成功（%s）", body.username, ip)
        return LoginResponse(
            token=_issue_token("user", body.username),
            expires_in=TOKEN_TTL_SECONDS,
            username=body.username,
            role="user",
        )

    raise _fail()


def require_user(request: Request) -> tuple[str, str]:
    """
    FastAPI 依赖：要求任意有效登录身份（管理员或普通用户），
    返回 (角色, 身份)，用于按身份存取数据

    Raises:
        HTTPException: 401 未登录/令牌过期
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        parsed = verify_token(auth_header[7:].strip())
        if parsed:
            return parsed
        raise HTTPException(
            status_code=401,
            detail="登录已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    raise HTTPException(
        status_code=401,
        detail="请先登录",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_admin(request: Request) -> None:
    """
    FastAPI 依赖：要求管理员身份
    通过条件（满足其一）：
    1. Authorization: Bearer <admin 角色令牌>
    2. X-Admin-Key 与 ADMIN_KEY 匹配（配置了 ADMIN_KEY 时）

    Raises:
        HTTPException: 401 未登录/令牌过期/权限不足/密钥错误
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        parsed = verify_token(auth_header[7:].strip())
        if parsed is None:
            raise HTTPException(
                status_code=401,
                detail="登录已过期，请重新登录",
                headers={"WWW-Authenticate": "Bearer"},
            )
        role, _identity = parsed
        if role == "admin":
            return
        raise HTTPException(
            status_code=403,
            detail="需要管理员权限",
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
