"""
用户与会话数据存储（SQLite）
存储注册用户与已登录用户的聊天记录，使聊天记录跨设备同步。
数据库文件位于 data/ 目录（Docker 中由 app_data 卷持久化）。
"""

import hashlib
import json
import logging
import secrets
import sqlite3
import threading
from pathlib import Path

from app.config import DATA_DIR

logger = logging.getLogger(__name__)

_DB_PATH = Path(DATA_DIR) / "campuslink.db"
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

# PBKDF2 迭代次数（密码哈希）
_PBKDF2_ITERATIONS = 200_000


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identity TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        _conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_identity ON chat_messages(identity, id)"
        )
        _conn.commit()
    return _conn


# ==================== 用户 ====================

def _hash_password(password: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return digest.hex()


def create_user(username: str, password: str) -> None:
    """
    注册用户（用户名唯一）

    Raises:
        ValueError: 用户名已存在
    """
    salt = secrets.token_bytes(16)
    password_hash = f"{salt.hex()}${_hash_password(password, salt)}"
    with _lock:
        try:
            _get_conn().execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            _get_conn().commit()
        except sqlite3.IntegrityError as e:
            raise ValueError(f"用户名「{username}」已被注册") from e


def verify_user(username: str, password: str) -> bool:
    """校验用户名密码（用户不存在时返回 False，不暴露账号是否存在）"""
    with _lock:
        row = _get_conn().execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    if not row:
        # 假哈希计算，保持与存在用户相近的响应时间
        _hash_password(password, b"0" * 16)
        return False
    salt_hex, stored_hash = row["password_hash"].split("$", 1)
    computed = _hash_password(password, bytes.fromhex(salt_hex))
    return secrets.compare_digest(computed, stored_hash)


# ==================== 聊天记录 ====================

def append_chat_message(identity: str, role: str, content: str, sources_json: str = "[]") -> None:
    """追加一条聊天消息到该用户的云端历史"""
    with _lock:
        _get_conn().execute(
            "INSERT INTO chat_messages (identity, role, content, sources_json) VALUES (?, ?, ?, ?)",
            (identity, role, content, sources_json),
        )
        _get_conn().commit()


def get_chat_messages(identity: str, limit: int = 200) -> list[dict]:
    """按时间正序返回该用户的聊天记录（最多 limit 条）"""
    with _lock:
        rows = _get_conn().execute(
            "SELECT role, content, sources_json, created_at FROM chat_messages "
            "WHERE identity = ? ORDER BY id DESC LIMIT ?",
            (identity, limit),
        ).fetchall()
    return [
        {
            "role": r["role"],
            "content": r["content"],
            "sources": json.loads(r["sources_json"]),
            "created_at": r["created_at"],
        }
        for r in reversed(rows)
    ]


def clear_chat_messages(identity: str) -> int:
    """清空该用户的云端聊天记录，返回删除条数"""
    with _lock:
        cur = _get_conn().execute(
            "DELETE FROM chat_messages WHERE identity = ?", (identity,)
        )
        _get_conn().commit()
    return cur.rowcount
