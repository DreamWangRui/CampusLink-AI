"""
知识库管理 API 路由
提供知识库文档列表查看（支持按文件夹筛选）、文件夹列表和文档删除功能
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.auth import require_admin, require_user
from app.config import UPLOAD_DIR
from app.database.chroma_client import (
    delete_document,
    get_all_documents,
    get_all_folders,
    move_document,
)
from app.models.schemas import (
    DeleteDocumentRequest,
    DeleteDocumentResponse,
    FolderInfo,
    KnowledgeDocument,
    KnowledgeListResponse,
    MoveDocumentRequest,
    MoveDocumentResponse,
)

logger = logging.getLogger(__name__)

# 创建知识库路由
# 知识库权限模型：列表/分类对任意登录用户只读开放（普通用户可浏览），
# 移动/删除等写操作仅管理员（路由内逐一定义依赖）
router = APIRouter(prefix="/api/knowledge", tags=["知识库管理"])


@router.get("/list", response_model=KnowledgeListResponse, summary="获取知识库文档列表（支持按文件夹筛选）")
def list_documents(
    folder: str = Query(None, description="可选，按文件夹名称筛选"),
    _identity: tuple[str, str] = Depends(require_user),
) -> KnowledgeListResponse:
    """
    获取知识库中所有文档的统计信息
    包含文档名称、所属文件夹、上传时间、Chunk 数量
    可通过 folder 参数按文件夹筛选

    Args:
        folder: 文件夹名称（可选），不传则返回全部

    Returns:
        KnowledgeListResponse: 文档列表和总数

    Note:
        使用同步 def：ChromaDB 查询为阻塞操作，由 FastAPI 线程池执行
    """
    try:
        docs = get_all_documents(folder=folder)
        # 将数据库返回的数据转换为 Pydantic 模型
        documents = [
            KnowledgeDocument(
                id=doc["doc_id"],
                filename=doc["filename"],
                folder=doc.get("folder", ""),
                upload_time=doc.get("upload_time", ""),
                chunk_count=doc["chunk_count"],
            )
            for doc in docs
        ]
        # 按上传时间倒序排列（最新的在前）
        documents.sort(key=lambda x: x.upload_time, reverse=True)
        return KnowledgeListResponse(documents=documents, total=len(documents))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文档列表失败: {e!s}")


@router.get("/folders", summary="获取所有文件夹/分类列表")
def list_folders(_identity: tuple[str, str] = Depends(require_user)):
    """
    获取所有文件夹及其下的文档数量

    Returns:
        dict: 包含 folders 列表，每项有 name 和 document_count
    """
    try:
        folders = get_all_folders()
        return {
            "folders": [
                FolderInfo(name=name, document_count=count)
                for name, count in folders
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件夹列表失败: {e!s}")


@router.delete("/delete", response_model=DeleteDocumentResponse, summary="删除知识库文档")
def delete_knowledge_document(
    request: DeleteDocumentRequest,
    _admin: None = Depends(require_admin),
) -> DeleteDocumentResponse:
    """
    删除指定文档的所有 Chunk，并同步清理 uploads/ 下的原始文件
    （否则磁盘上的源文件会成为永久残留的孤儿文件）

    Args:
        request: 包含要删除的文档 ID

    Returns:
        DeleteDocumentResponse: 操作结果
    """
    try:
        original_files = delete_document(request.doc_id)
        if not original_files:
            return DeleteDocumentResponse(
                success=False,
                message=f"文档 '{request.doc_id}' 不存在或删除失败",
            )

        # 清理磁盘上的原始上传文件（缺失时忽略，不阻断删除流程）
        removed = 0
        for filename in original_files:
            file_path = UPLOAD_DIR / filename
            try:
                if file_path.is_file():
                    file_path.unlink()
                    removed += 1
            except OSError:
                pass

        message = f"文档 '{request.doc_id}' 已成功删除"
        if removed:
            message += f"，并清理了 {removed} 个源文件"
        return DeleteDocumentResponse(success=True, message=message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文档失败: {e!s}")


@router.put("/move", response_model=MoveDocumentResponse, summary="移动文档到其他文件夹")
def move_knowledge_document(
    request: MoveDocumentRequest,
    _admin: None = Depends(require_admin),
) -> MoveDocumentResponse:
    """
    将文档移动到指定文件夹（更新其所有 Chunk 的 folder 元数据）
    输入不存在的文件夹名称即视为创建新分类；留空归入未分类

    Args:
        request: 包含文档 ID 和目标文件夹名称

    Returns:
        MoveDocumentResponse: 操作结果
    """
    folder = request.folder.strip()
    try:
        moved = move_document(request.doc_id, folder)
        if not moved:
            return MoveDocumentResponse(
                success=False,
                message=f"文档 '{request.doc_id}' 不存在",
            )
        display = folder if folder else "未分类"
        logger.info("文档 %s 已移动到「%s」（%d 个 Chunk）", request.doc_id, display, moved)
        return MoveDocumentResponse(
            success=True,
            message=f"已成功移动 {moved} 个 Chunk 到「{display}」",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"移动文档失败: {e!s}")
