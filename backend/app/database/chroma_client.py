"""
ChromaDB 数据库服务
管理向量数据库的连接和基本操作，使用 PersistentClient 实现本地持久化
"""

import os
import uuid
from pathlib import Path
from typing import Optional

import chromadb
from chromadb import PersistentClient
from chromadb.utils import embedding_functions

from app.config import CHROMA_DB_DIR, COLLECTION_NAME, EMBEDDING_MODEL_NAME, EMBEDDING_DIMENSION


# ==================== 全局 ChromaDB 客户端 ====================
# 使用 PersistentClient 将向量数据持久化到本地磁盘
_client: Optional[PersistentClient] = None


def get_client() -> PersistentClient:
    """
    获取 ChromaDB PersistentClient 实例（懒加载单例模式）
    数据持久化存储在 chroma_db/ 目录下

    Returns:
        PersistentClient: ChromaDB 持久化客户端
    """
    global _client
    if _client is None:
        # 确保存储目录存在
        os.makedirs(str(CHROMA_DB_DIR), exist_ok=True)
        # 创建持久化客户端，数据保存到 chroma_db/ 目录
        _client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    return _client


# ==================== 自定义 Embedding Function ====================
# ChromaDB 的自定义嵌入函数，桥接我们的 embedding_service
class SentenceTransformerEmbeddingFunction(embedding_functions.EmbeddingFunction):
    """
    自定义 ChromaDB EmbeddingFunction
    使用本地 BAAI/bge-small-zh-v1.5 模型进行向量化
    """

    def __call__(self, input: list[str]) -> list[list[float]]:
        """
        批量将文本转换为向量

        Args:
            input: 文本列表

        Returns:
            list[list[float]]: 对应的向量列表
        """
        from app.services.embedding_service import embed_texts
        return embed_texts(input)


def get_collection():
    """
    获取 ChromaDB 知识库集合
    使用自定义 EmbeddingFunction 确保查询时自动向量化

    Returns:
        Collection: ChromaDB 集合实例
    """
    client = get_client()
    # 创建自定义嵌入函数实例
    embedding_fn = SentenceTransformerEmbeddingFunction()

    # 获取或创建集合
    # ChromaDB 使用余弦相似度（Cosine Similarity）作为默认距离度量
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={
            "description": "CampusLink AI 校园知识库",
            "embedding_model": EMBEDDING_MODEL_NAME,
            "dimension": EMBEDDING_DIMENSION,
        },
    )
    return collection


def add_documents(doc_id: str, chunks: list[str], metadata: dict) -> int:
    """
    将文档的文本块添加到 ChromaDB

    Args:
        doc_id: 文档唯一标识
        chunks: 文本块列表
        metadata: 文档元数据（文件名、上传时间等）

    Returns:
        int: 添加的 Chunk 数量
    """
    if not chunks:
        return 0

    collection = get_collection()
    # 为每个 chunk 生成唯一 ID：{doc_id}_{序号}
    ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
    # 为每个 chunk 附加元数据
    metadatas = [{**metadata, "chunk_index": i} for i in range(len(chunks))]

    collection.add(
        ids=ids,
        documents=chunks,
        metadatas=metadatas,
    )

    return len(chunks)


def search_similar(query: str, top_k: int = 5) -> list[dict]:
    """
    语义检索：根据查询文本检索最相似的文档片段

    Args:
        query: 用户查询文本
        top_k: 返回的 Top K 个最相似结果（默认 5）

    Returns:
        list[dict]: 检索结果列表，每个结果包含 id、document、metadata、distance
    """
    collection = get_collection()

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
    )

    # 将 ChromaDB 返回的结果转换为更友好的格式
    documents = []
    if results["ids"] and results["ids"][0]:
        for i in range(len(results["ids"][0])):
            documents.append({
                "id": results["ids"][0][i],
                "document": results["documents"][0][i] if results["documents"] else "",
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else 0.0,
            })

    return documents


def delete_document(doc_id: str) -> bool:
    """
    删除指定文档的所有 Chunk

    Args:
        doc_id: 文档唯一标识

    Returns:
        bool: 是否成功删除
    """
    collection = get_collection()

    try:
        # 获取该文档下的所有 chunk ID
        results = collection.get(
            where={"doc_id": doc_id},
        )
        if results["ids"]:
            # 批量删除所有 chunk
            collection.delete(ids=results["ids"])
        return True
    except Exception:
        return False


def get_all_documents(folder: str | None = None) -> list[dict]:
    """
    获取知识库中所有文档的统计信息
    按 doc_id 分组统计每个文档的 Chunk 数量

    Args:
        folder: 可选，按文件夹筛选。为 None 时返回全部文档

    Returns:
        list[dict]: 文档信息列表，每个包含 doc_id、filename、folder、upload_time、chunk_count
    """
    collection = get_collection()

    try:
        # 如果指定了文件夹，按 metadata 过滤
        if folder:
            all_data = collection.get(where={"folder": folder})
        else:
            all_data = collection.get()
    except Exception:
        return []

    if not all_data["ids"]:
        return []

    # 按 doc_id 分组统计
    doc_stats: dict[str, dict] = {}
    for i, metadata in enumerate(all_data["metadatas"]):
        doc_id = metadata.get("doc_id", "unknown")
        if doc_id not in doc_stats:
            doc_stats[doc_id] = {
                "doc_id": doc_id,
                "filename": metadata.get("filename", "未知文件"),
                "folder": metadata.get("folder", ""),
                "upload_time": metadata.get("upload_time", ""),
                "chunk_count": 0,
            }
        doc_stats[doc_id]["chunk_count"] += 1

    return list(doc_stats.values())


def get_all_folders() -> list[tuple[str, int]]:
    """
    获取所有文件夹/分类及其文档数量
    遍历所有 Chunk 的 metadata，按 folder 字段去重统计

    Returns:
        list[tuple[str, int]]: [(文件夹名称, 文档数量), ...]，按名称排序
    """
    collection = get_collection()

    try:
        all_data = collection.get()
    except Exception:
        return []

    if not all_data["ids"]:
        return []

    # 按文件夹名分组，统计每个文件夹下的唯一 doc_id 数量
    folder_docs: dict[str, set] = {}
    for metadata in all_data["metadatas"]:
        folder_name = metadata.get("folder", "").strip()
        # 空文件夹名统一为 "未分类"
        if not folder_name:
            folder_name = "未分类"
        if folder_name not in folder_docs:
            folder_docs[folder_name] = set()
        folder_docs[folder_name].add(metadata.get("doc_id", ""))

    # 转换为 (名称, 数量) 列表，按名称排序
    result = [(name, len(docs)) for name, docs in folder_docs.items()]
    result.sort(key=lambda x: x[0])
    return result
