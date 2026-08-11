"""
知识库管理 API 路由
提供知识库文档列表查看（支持按文件夹筛选）、文件夹列表和文档删除功能
"""

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    KnowledgeDocument,
    KnowledgeListResponse,
    DeleteDocumentRequest,
    DeleteDocumentResponse,
    FolderInfo,
)
from app.database.chroma_client import get_all_documents, get_all_folders, delete_document

# 创建知识库路由
router = APIRouter(prefix="/api/knowledge", tags=["知识库管理"])


@router.get("/list", response_model=KnowledgeListResponse, summary="获取知识库文档列表（支持按文件夹筛选）")
async def list_documents(folder: str = Query(None, description="可选，按文件夹名称筛选")) -> KnowledgeListResponse:
    """
    获取知识库中所有文档的统计信息
    包含文档名称、所属文件夹、上传时间、Chunk 数量
    可通过 folder 参数按文件夹筛选

    Args:
        folder: 文件夹名称（可选），不传则返回全部

    Returns:
        KnowledgeListResponse: 文档列表和总数
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
        raise HTTPException(status_code=500, detail=f"获取文档列表失败: {str(e)}")


@router.get("/folders", summary="获取所有文件夹/分类列表")
async def list_folders():
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
        raise HTTPException(status_code=500, detail=f"获取文件夹列表失败: {str(e)}")


@router.delete("/delete", response_model=DeleteDocumentResponse, summary="删除知识库文档")
async def delete_knowledge_document(request: DeleteDocumentRequest) -> DeleteDocumentResponse:
    """
    删除指定文档的所有 Chunk

    Args:
        request: 包含要删除的文档 ID

    Returns:
        DeleteDocumentResponse: 操作结果
    """
    try:
        success = delete_document(request.doc_id)
        if success:
            return DeleteDocumentResponse(
                success=True,
                message=f"文档 '{request.doc_id}' 已成功删除",
            )
        else:
            return DeleteDocumentResponse(
                success=False,
                message=f"删除文档 '{request.doc_id}' 失败",
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}")
