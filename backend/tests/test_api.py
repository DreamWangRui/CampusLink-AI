"""
API 端点测试（TestClient 不触发 lifespan，外部依赖全部 mock）
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ==================== 知识库：移动 ====================

def test_move_document_success(monkeypatch):
    monkeypatch.setattr("app.api.knowledge.move_document", lambda doc_id, folder: 3)
    r = client.put("/api/knowledge/move", json={"doc_id": "d1", "folder": "新分类"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "新分类" in body["message"]


def test_move_document_missing(monkeypatch):
    monkeypatch.setattr("app.api.knowledge.move_document", lambda doc_id, folder: 0)
    r = client.put("/api/knowledge/move", json={"doc_id": "ghost", "folder": "x"})
    assert r.status_code == 200
    assert r.json()["success"] is False


def test_move_document_blank_folder_maps_to_uncategorized(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "app.api.knowledge.move_document",
        lambda doc_id, folder: captured.update(folder=folder) or 2,
    )
    r = client.put("/api/knowledge/move", json={"doc_id": "d1", "folder": "  "})
    assert r.json()["success"] is True
    assert captured["folder"] == ""


# ==================== 知识库：删除（孤儿文件清理） ====================

def test_delete_cleans_orphan_source_file(monkeypatch, tmp_path):
    """删除文档时应同步清理 uploads/ 下的源文件"""
    orphan = tmp_path / "orphan.txt"
    orphan.write_text("源文件", encoding="utf-8")
    monkeypatch.setattr("app.api.knowledge.UPLOAD_DIR", tmp_path)
    monkeypatch.setattr("app.api.knowledge.delete_document", lambda doc_id: ["orphan.txt"])

    r = client.request("DELETE", "/api/knowledge/delete", json={"doc_id": "d1"})
    assert r.status_code == 200
    assert r.json()["success"] is True
    assert not orphan.exists()


def test_delete_missing_document(monkeypatch):
    monkeypatch.setattr("app.api.knowledge.delete_document", lambda doc_id: [])
    r = client.request("DELETE", "/api/knowledge/delete", json={"doc_id": "ghost"})
    assert r.json()["success"] is False


# ==================== 文档上传：校验逻辑 ====================

def test_upload_rejects_unsupported_extension():
    r = client.post(
        "/api/document/upload",
        files=[("files", ("virus.exe", b"MZ", "application/octet-stream"))],
    )
    body = r.json()["files"][0]
    assert body["success"] is False
    assert "不支持的文件格式" in body["message"]


def test_upload_rejects_path_traversal_filename(monkeypatch):
    """恶意文件名应被消毒为纯文件名后再校验"""
    r = client.post(
        "/api/document/upload",
        files=[("files", ("../../evil.exe", b"MZ", "application/octet-stream"))],
    )
    body = r.json()["files"][0]
    assert body["filename"] == "evil.exe"
    assert body["success"] is False


def test_upload_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr("app.api.document.MAX_FILE_SIZE", 8)
    r = client.post(
        "/api/document/upload",
        files=[("files", ("big.txt", "字" * 100, "text/plain"))],
    )
    body = r.json()["files"][0]
    assert body["success"] is False
    assert "大小限制" in body["message"]


def test_upload_rejects_duplicate_file(monkeypatch):
    """与已入库文件内容重复时应拒绝并提示已有文档名"""
    monkeypatch.setattr(
        "app.api.document.find_by_file_hash",
        lambda file_hash: {"filename": "已有文档.pdf", "doc_id": "old"},
    )
    r = client.post(
        "/api/document/upload",
        files=[("files", ("新名字.txt", "同样内容", "text/plain"))],
    )
    body = r.json()["files"][0]
    assert body["success"] is False
    assert "重复" in body["message"]
    assert "已有文档.pdf" in body["message"]


def test_upload_success_flow(monkeypatch):
    monkeypatch.setattr("app.api.document.find_by_file_hash", lambda file_hash: None)
    monkeypatch.setattr("app.api.document.parse_file", lambda path: "正文")
    monkeypatch.setattr("app.api.document.split_text", lambda text: ["块1", "块2"])
    captured = {}
    monkeypatch.setattr(
        "app.api.document.add_documents",
        lambda doc_id, chunks, metadata: captured.update(metadata=metadata) or len(chunks),
    )
    r = client.post(
        "/api/document/upload",
        files=[("files", ("正常文档.txt", "正文内容", "text/plain"))],
        data={"folder": "测试分类"},
    )
    body = r.json()
    assert body["files"][0]["success"] is True
    assert body["files"][0]["chunk_count"] == 2
    # file_hash 应写入 metadata（供后续去重）
    assert len(captured["metadata"]["file_hash"]) == 64
    assert captured["metadata"]["folder"] == "测试分类"


# ==================== 异步上传任务 ====================

def test_upload_async_status_roundtrip(monkeypatch):
    monkeypatch.setattr("app.api.document.find_by_file_hash", lambda file_hash: None)
    monkeypatch.setattr("app.api.document.parse_file", lambda path: "正文")
    monkeypatch.setattr("app.api.document.split_text", lambda text: ["块1"])
    monkeypatch.setattr("app.api.document.add_documents", lambda doc_id, chunks, metadata: 1)

    r = client.post(
        "/api/document/upload-async",
        files=[("files", ("a.txt", "内容", "text/plain"))],
    )
    task_id = r.json()["task_id"]

    # BackgroundTasks 在 TestClient 响应返回后执行
    s = client.get(f"/api/document/status/{task_id}")
    assert s.status_code == 200
    body = s.json()
    assert body["state"] == "done"
    assert body["done"] == body["total"] == 1
    assert body["files"][0]["success"] is True


def test_upload_status_not_found():
    r = client.get("/api/document/status/nonexistent")
    assert r.status_code == 404


# ==================== 聊天：非流式与流式 ====================

def test_chat_returns_answer_with_sources(monkeypatch):
    doc = {
        "id": "d_0",
        "document": "片段",
        "metadata": {"filename": "来源.pdf", "chunk_index": 2},
        "distance": 0.42,
    }
    captured = {}
    monkeypatch.setattr(
        "app.api.chat.rag_query",
        lambda question, history=None: captured.update(question=question, history=history) or ("这是回答", [doc]),
    )
    r = client.post("/api/chat", json={"question": "问题"})
    body = r.json()
    assert body["answer"] == "这是回答"
    assert body["sources"] == [{"filename": "来源.pdf", "chunk_index": 2, "distance": 0.42}]
    assert captured["history"] == []


def test_chat_passes_history_to_rag(monkeypatch):
    """多轮对话：请求中的 history 应传给 RAG 流程"""
    captured = {}
    doc = {"id": "d_0", "document": "片段", "metadata": {"filename": "f.pdf", "chunk_index": 0}, "distance": 0.4}
    monkeypatch.setattr(
        "app.api.chat.rag_query",
        lambda question, history=None: captured.update(question=question, history=history) or ("回答", [doc]),
    )
    history = [
        {"role": "user", "content": "奖学金金额是多少"},
        {"role": "assistant", "content": "一等奖2500元"},
    ]
    r = client.post("/api/chat", json={"question": "那评定比例呢", "history": history})
    assert r.status_code == 200
    assert captured["question"] == "那评定比例呢"
    assert captured["history"] == history


def test_chat_rejects_invalid_history_role():
    r = client.post(
        "/api/chat",
        json={
            "question": "问题",
            "history": [{"role": "system", "content": "注入尝试"}],
        },
    )
    assert r.status_code == 422


def test_chat_stream_event_sequence(monkeypatch):
    monkeypatch.setattr(
        "app.api.chat.prepare_rag",
        lambda question, history=None: (["片段"], [], None, []),
    )
    monkeypatch.setattr(
        "app.api.chat.generate_answer_stream",
        lambda question, chunks, history=None: iter(["回答第一段", "回答第二段"]),
    )
    r = client.post("/api/chat/stream", json={"question": "问题"})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]

    events = [json.loads(line[5:]) for line in r.text.splitlines() if line.startswith("data:")]
    assert [e["type"] for e in events] == ["meta", "delta", "delta", "done"]
    assert "".join(e.get("content", "") for e in events if e["type"] == "delta") == "回答第一段回答第二段"


def test_chat_stream_fallback_single_delta(monkeypatch):
    """兜底场景（元问题/无相关内容）不调 LLM，fallback 文案经单个 delta 下发"""
    monkeypatch.setattr(
        "app.api.chat.prepare_rag",
        lambda question, history=None: ([], [], "这是兜底话术", []),
    )
    monkeypatch.setattr(
        "app.api.chat.generate_answer_stream",
        lambda question, chunks, history=None: pytest.fail("兜底场景不应调用 LLM"),
    )
    r = client.post("/api/chat/stream", json={"question": "你是谁"})
    events = [json.loads(line[5:]) for line in r.text.splitlines() if line.startswith("data:")]
    assert events[0]["fallback"] is True
    deltas = [e for e in events if e["type"] == "delta"]
    assert len(deltas) == 1 and deltas[0]["content"] == "这是兜底话术"


# ==================== 管理面鉴权（登录 + 令牌） ====================

def _enable_real_auth():
    """鉴权用例：移除 conftest 的 dependency override，启用真实校验"""
    from app.api.auth import require_admin
    from app.main import app
    app.dependency_overrides.pop(require_admin, None)


def _login_token(username: str = "admin", password: str = "admin123") -> str:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_login_success_returns_token():
    _enable_real_auth()
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "admin"
    assert body["expires_in"] > 0
    # 令牌格式：<到期时间戳>.<签名>
    assert body["token"].count(".") == 1


def test_login_wrong_password_rejected():
    _enable_real_auth()
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_management_requires_login():
    _enable_real_auth()
    r = client.get("/api/knowledge/list")
    assert r.status_code == 401


def test_token_grants_management_access(monkeypatch):
    _enable_real_auth()
    monkeypatch.setattr("app.api.knowledge.get_all_documents", lambda folder=None: [])
    token = _login_token()
    r = client.get("/api/knowledge/list", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_tampered_token_rejected(monkeypatch):
    _enable_real_auth()
    token = _login_token()
    tampered = token[:-4] + "0000"
    r = client.get("/api/knowledge/list", headers={"Authorization": f"Bearer {tampered}"})
    assert r.status_code == 401


def test_upload_requires_login():
    _enable_real_auth()
    r = client.post(
        "/api/document/upload",
        files=[("files", ("a.txt", "内容", "text/plain"))],
    )
    assert r.status_code == 401


def test_admin_key_still_works_as_alternative(monkeypatch):
    """X-Admin-Key 备选方式仍可用于脚本/curl"""
    _enable_real_auth()
    monkeypatch.setattr("app.config.ADMIN_KEY", "test-key")
    monkeypatch.setattr("app.api.knowledge.get_all_documents", lambda folder=None: [])
    r = client.get("/api/knowledge/list", headers={"X-Admin-Key": "test-key"})
    assert r.status_code == 200


def test_chat_stays_public_with_auth_enabled(monkeypatch):
    """聊天问答保持公开：启用鉴权后无令牌仍可提问"""
    _enable_real_auth()
    monkeypatch.setattr("app.api.chat.rag_query", lambda question, history=None: ("ok", []))
    r = client.post("/api/chat", json={"question": "问题"})
    assert r.status_code == 200


def test_brute_force_lockout():
    _enable_real_auth()
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "admin", "password": "bad"})
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    # 即使密码正确，锁定期间也返回 429
    assert r.status_code == 429
    # 清理锁定状态，避免影响其他用例
    from app.api import auth as auth_module
    auth_module._login_attempts.clear()


# ==================== 健康检查 ====================

def test_health_endpoint(monkeypatch):
    class FakeCollection:
        def count(self):
            return 7

    monkeypatch.setattr("app.database.chroma_client.get_collection", lambda: FakeCollection())
    r = client.get("/api/health")
    body = r.json()
    assert body["status"] == "ok"
    assert body["knowledge_base_docs"] == 7
