"""
文档上传 API 路由
支持批量上传和文件夹分类：
- POST /api/document/upload        同步批量上传（保留用于脚本/调试）
- POST /api/document/upload-async  异步批量上传（前端使用，返回任务 ID 轮询进度）
- GET  /api/document/status/{id}   查询上传任务进度
"""

import hashlib
import logging
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form

from app.config import UPLOAD_DIR, SUPPORTED_EXTENSIONS, MAX_FILE_SIZE
from app.models.schemas import BatchUploadResponse, BatchUploadFileResult
from app.services.document_service import parse_file
from app.services.splitter_service import split_text
from app.database.chroma_client import add_documents, find_by_file_hash

logger = logging.getLogger(__name__)

# 创建文档路由
router = APIRouter(prefix="/api/document", tags=["文档管理"])

# ==================== 异步上传任务表 ====================
# 内存任务表：单 worker 部署下可用；服务重启后任务记录丢失（文档入库不受影响）
_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()
_TASK_TTL_SECONDS = 30 * 60  # 任务记录保留 30 分钟


def _update_task(task_id: str, **fields) -> None:
    with _tasks_lock:
        _tasks.setdefault(task_id, {}).update(fields)


def _purge_expired_tasks() -> None:
    """清理超过 TTL 的任务记录，防止内存无限增长"""
    now = time.time()
    with _tasks_lock:
        expired = [
            tid for tid, t in _tasks.items()
            if now - t.get("created_at", now) > _TASK_TTL_SECONDS
        ]
        for tid in expired:
            _tasks.pop(tid, None)


def _process_batch(task_id: str, files: list[UploadFile], folder: str) -> None:
    """后台批量处理文件：逐个入库并实时更新任务进度"""
    results: list[BatchUploadFileResult] = []
    for i, file in enumerate(files):
        try:
            result = _process_single_file(file, folder)
        except Exception as e:
            logger.exception("文件处理异常: %s", file.filename)
            result = BatchUploadFileResult(
                success=False,
                filename=file.filename or "未知文件",
                message=f"处理异常: {str(e)}",
            )
        logger.info("文件入库[%d/%d] %s: %s", i + 1, len(files), result.filename, result.message)
        results.append(result)
        # 序列化为 dict 存入任务表，避免与状态轮询的读取产生竞态
        _update_task(task_id, files=[r.model_dump() for r in results], done=i + 1)

    success_count = sum(1 for r in results if r.success)
    total_chunks = sum(r.chunk_count for r in results)
    _update_task(
        task_id,
        state="done",
        message=f"批量上传完成：{success_count} 个成功，{len(results) - success_count} 个失败，共 {total_chunks} 个 Chunk",
    )


# ==================== 单文件处理内部函数 ====================

def _process_single_file(file: UploadFile, folder: str) -> BatchUploadFileResult:
    """
    处理单个文件：校验 → 保存 → 解析 → 切分 → 向量化 → 入库

    Args:
        file: 上传的文件对象
        folder: 所属文件夹名称

    Returns:
        BatchUploadFileResult: 该文件的处理结果
    """
    # ---- 校验文件名（取纯文件名，防止路径穿越）----
    if not file.filename:
        return BatchUploadFileResult(
            success=False, filename="未知文件", message="文件名不能为空"
        )
    # Path(...).name 剥离可能携带的目录成分（如 ../../evil.txt → evil.txt）
    safe_filename = Path(file.filename).name
    if not safe_filename:
        return BatchUploadFileResult(
            success=False, filename="未知文件", message="文件名不能为空"
        )

    # ---- 校验文件格式 ----
    extension = Path(safe_filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        return BatchUploadFileResult(
            success=False,
            filename=safe_filename,
            message=f"不支持的文件格式: {extension}，支持的格式: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    # ---- 保存文件到磁盘（限制大小，防止超大文件打爆内存/磁盘）----
    unique_filename = f"{uuid.uuid4().hex}_{safe_filename}"
    file_path = UPLOAD_DIR / unique_filename

    try:
        content = file.file.read(MAX_FILE_SIZE + 1)
        if not content:
            return BatchUploadFileResult(
                success=False, filename=safe_filename, message="上传的文件为空"
            )
        if len(content) > MAX_FILE_SIZE:
            return BatchUploadFileResult(
                success=False,
                filename=safe_filename,
                message=f"文件超过大小限制（最大 {MAX_FILE_SIZE // (1024 * 1024)}MB）",
            )
    except Exception as e:
        return BatchUploadFileResult(
            success=False, filename=safe_filename, message=f"文件保存失败: {str(e)}"
        )

    # ---- 重复文件检测（内容 SHA-256 哈希）----
    file_hash = hashlib.sha256(content).hexdigest()
    existing = find_by_file_hash(file_hash)
    if existing:
        existing_name = existing.get("filename", "未知文件")
        return BatchUploadFileResult(
            success=False,
            filename=safe_filename,
            message=f"与已有文档《{existing_name}》内容重复，已跳过",
        )

    # ---- 保存文件到磁盘 ----
    unique_filename = f"{uuid.uuid4().hex}_{safe_filename}"
    file_path = UPLOAD_DIR / unique_filename
    try:
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        return BatchUploadFileResult(
            success=False, filename=safe_filename, message=f"文件保存失败: {str(e)}"
        )

    # ---- 解析文本 ----
    try:
        text = parse_file(file_path)
    except ValueError as e:
        if file_path.exists():
            file_path.unlink()
        return BatchUploadFileResult(success=False, filename=safe_filename, message=str(e))
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        return BatchUploadFileResult(
            success=False, filename=safe_filename, message=f"文档解析失败: {str(e)}"
        )

    # ---- 文本切分 ----
    chunks = split_text(text)
    if not chunks:
        if file_path.exists():
            file_path.unlink()
        return BatchUploadFileResult(
            success=False, filename=safe_filename, message="文档内容为空，无法导入知识库"
        )

    # ---- 向量化并存入 ChromaDB ----
    doc_id = uuid.uuid4().hex

    metadata = {
        "doc_id": doc_id,
        "filename": safe_filename,
        "original_file": unique_filename,
        "folder": folder or "",
        "upload_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file_type": extension,
        "file_hash": file_hash,
    }

    try:
        chunk_count = add_documents(doc_id=doc_id, chunks=chunks, metadata=metadata)
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        return BatchUploadFileResult(
            success=False, filename=safe_filename, message=f"向量化存储失败: {str(e)}"
        )

    return BatchUploadFileResult(
        success=True,
        filename=safe_filename,
        chunk_count=chunk_count,
        message=f"导入成功，共 {chunk_count} 个 Chunk",
    )


# ==================== 批量上传接口 ====================

@router.post("/upload", response_model=BatchUploadResponse, summary="批量上传文档并导入知识库")
def upload_documents(
    files: list[UploadFile] = File(...),
    folder: str = Form(""),
) -> BatchUploadResponse:
    """
    批量上传文档（PDF/DOCX/TXT/MD），自动完成解析、切分、向量化、入库
    支持指定文件夹分类，单个文件失败不影响其他文件继续处理

    Args:
        files: 上传的文件列表
        folder: 文件夹/分类名称（可选，留空则归入"未分类"）

    Returns:
        BatchUploadResponse: 每个文件的处理结果和汇总信息

    Note:
        使用同步 def 而非 async def：文件读写、解析和向量化均为阻塞操作，
        FastAPI 会将同步端点放入线程池执行，避免阻塞事件循环。
    """
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")

    results: list[BatchUploadFileResult] = []
    total_chunks = 0

    for file in files:
        try:
            result = _process_single_file(file, folder)
        except Exception as e:
            result = BatchUploadFileResult(
                success=False,
                filename=file.filename or "未知文件",
                message=f"处理异常: {str(e)}",
            )
        results.append(result)
        if result.success:
            total_chunks += result.chunk_count

    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count

    return BatchUploadResponse(
        files=results,
        total_chunks=total_chunks,
        message=f"批量上传完成：{success_count} 个成功，{fail_count} 个失败，共 {total_chunks} 个 Chunk",
    )


# ==================== 异步批量上传接口 ====================

@router.post("/upload-async", summary="异步批量上传（返回任务 ID，配合状态轮询）")
def upload_documents_async(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    folder: str = Form(""),
) -> dict:
    """
    异步批量上传：接口立即返回任务 ID，解析/切分/向量化在后台执行，
    前端通过 GET /api/document/status/{task_id} 轮询逐文件进度。
    避免大批量文件串行处理导致的长时间 HTTP 等待与超时。

    Args:
        background_tasks: FastAPI 后台任务
        files: 上传的文件列表
        folder: 文件夹/分类名称（可选）

    Returns:
        dict: {"task_id": "..."}
    """
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")

    _purge_expired_tasks()
    task_id = uuid.uuid4().hex
    _update_task(
        task_id,
        state="processing",
        files=[],
        done=0,
        total=len(files),
        message="正在处理...",
        created_at=time.time(),
    )
    background_tasks.add_task(_process_batch, task_id, files, folder)
    return {"task_id": task_id}


@router.get("/status/{task_id}", summary="查询上传任务进度")
def upload_task_status(task_id: str) -> dict:
    """
    查询异步上传任务的实时进度

    Args:
        task_id: 任务 ID

    Returns:
        dict: {task_id, state, files(逐文件结果), done, total, message}
    """
    with _tasks_lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在或已过期")
        return {"task_id": task_id, **task}
