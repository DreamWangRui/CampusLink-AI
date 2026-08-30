"""
pytest 全局夹具
"""
import pytest


@pytest.fixture(autouse=True)
def _bypass_admin_auth():
    """
    默认跳过管理面鉴权（多数用例不关心 401）。
    使用 FastAPI 官方的 dependency_overrides 机制；
    鉴权专用用例需先 pop 掉 override 以启用真实校验（见 test_api.py 的 _enable_real_auth）。
    """
    from app.api.auth import require_admin
    from app.main import app

    app.dependency_overrides[require_admin] = lambda: None
    yield
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture(autouse=True)
def _clean_user_db():
    """每个用例前清空用户与会话表（SQLite 文件跨测试运行持久化）"""
    from app.database import user_db

    conn = user_db._get_conn()
    conn.execute("DELETE FROM chat_messages")
    conn.execute("DELETE FROM users")
    conn.commit()
    yield
