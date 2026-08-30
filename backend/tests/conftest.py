"""
pytest 全局夹具
"""
import pytest

from app import config


@pytest.fixture(autouse=True)
def _disable_admin_auth(monkeypatch):
    """默认关闭管理面鉴权（多数用例不关心 401）；鉴权专用用例自行覆盖 ADMIN_KEY"""
    monkeypatch.setattr(config, "ADMIN_KEY", "")
