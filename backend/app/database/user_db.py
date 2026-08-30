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
                session_id TEXT,
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
        # 会话表（多会话支持）；旧库补列的迁移放在 try 里兼容已有部署
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                identity TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '新会话',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        try:
            _conn.execute("ALTER TABLE chat_messages ADD COLUMN session_id TEXT")
        except sqlite3.OperationalError:
            pass  # 列已存在
        _conn.commit()
    return _conn


# ==================== 会话 ====================

def create_session(identity: str, session_id: str, title: str = "新会话") -> dict:
    """创建会话（id 由调用方生成，前端本地/服务端共用同一 id）"""
    with _lock:
        _get_conn().execute(
            "INSERT OR IGNORE INTO chat_sessions (id, identity, title) VALUES (?, ?, ?)",
            (session_id, identity, title),
        )
        _get_conn().commit()
    return get_session(identity, session_id)


def get_session(identity: str, session_id: str) -> dict | None:
    """获取单个会话（校验归属）"""
    with _lock:
        row = _get_conn().execute(
            "SELECT id, title, created_at, updated_at FROM chat_sessions WHERE id = ? AND identity = ?",
            (session_id, identity),
        ).fetchone()
    return dict(row) if row else None


def list_sessions(identity: str) -> list[dict]:
    """
    按最近更新倒序返回该用户的会话列表。
    旧数据迁移：历史消息若无任何会话归属，自动归入「历史会话」。
    """
    conn = _get_conn()
    with _lock:
        # 一次性迁移：该身份存在无会话归属的旧消息，但没有可用会话
        legacy = conn.execute(
            "SELECT COUNT(*) AS n FROM chat_messages WHERE identity = ? AND session_id IS NULL",
            (identity,),
        ).fetchone()["n"]
        has_sessions = conn.execute(
            "SELECT COUNT(*) AS n FROM chat_sessions WHERE identity = ?", (identity,)
        ).fetchone()["n"]
        if legacy and not has_sessions:
            conn.execute(
                "INSERT INTO chat_sessions (id, identity, title) VALUES (?, ?, ?)",
                (secrets.token_hex(16), identity, "历史会话"),
            )
            conn.execute(
                "UPDATE chat_messages SET session_id = (SELECT id FROM chat_sessions WHERE identity = ? ORDER BY id LIMIT 1) "
                "WHERE identity = ? AND session_id IS NULL",
                (identity, identity),
            )
            conn.commit()

        rows = conn.execute(
            "SELECT id, title, created_at, updated_at FROM chat_sessions WHERE identity = ? ORDER BY updated_at DESC, id DESC",
            (identity,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_session(identity: str, session_id: str) -> bool:
    """删除会话及其全部消息"""
    with _lock:
        cur = _get_conn().execute(
            "DELETE FROM chat_sessions WHERE id = ? AND identity = ?",
            (session_id, identity),
        )
        _get_conn().execute(
            "DELETE FROM chat_messages WHERE identity = ? AND session_id = ?",
            (identity, session_id),
        )
        _get_conn().commit()
    return cur.rowcount > 0


def session_belongs_to(identity: str, session_id: str) -> bool:
    return get_session(identity, session_id) is not None


def get_session_messages(identity: str, session_id: str, limit: int = 200) -> list[dict]:
    with _lock:
        rows = _get_conn().execute(
            "SELECT role, content, sources_json, created_at FROM chat_messages "
            "WHERE identity = ? AND session_id = ? ORDER BY id DESC LIMIT ?",
            (identity, session_id, limit),
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


def clear_session_messages(identity: str, session_id: str) -> int:
    """清空会话内的消息（保留会话本身）"""
    with _lock:
        cur = _get_conn().execute(
            "DELETE FROM chat_messages WHERE identity = ? AND session_id = ?",
            (identity, session_id),
        )
        _get_conn().commit()
    return cur.rowcount


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


def update_password(username: str, password: str) -> None:
    """
    更新用户密码（新盐新哈希）

    Raises:
        ValueError: 用户不存在
    """
    salt = secrets.token_bytes(16)
    password_hash = f"{salt.hex()}${_hash_password(password, salt)}"
    with _lock:
        cur = _get_conn().execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (password_hash, username),
        )
        _get_conn().commit()
    if cur.rowcount == 0:
        raise ValueError(f"用户「{username}」不存在")


# ==================== 聊天记录 ====================

def append_chat_message(identity: str, session_id: str, role: str, content: str, sources_json: str = "[]") -> None:
    """
    追加一条聊天消息到指定会话，并刷新会话更新时间。
    会话标题仍为默认值时，首条用户消息自动成为标题（截取前 30 字）。
    """
    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO chat_messages (identity, session_id, role, content, sources_json) VALUES (?, ?, ?, ?, ?)",
            (identity, session_id, role, content, sources_json),
        )
        conn.execute(
            "UPDATE chat_sessions SET updated_at = datetime('now', 'localtime') WHERE id = ? AND identity = ?",
            (session_id, identity),
        )
        if role == "user":
            conn.execute(
                "UPDATE chat_sessions SET title = substr(?, 1, 30) WHERE id = ? AND identity = ? AND title = '新会话'",
                (content, session_id, identity),
            )
        conn.commit()


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
