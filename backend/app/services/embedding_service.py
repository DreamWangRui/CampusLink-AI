"""
Embedding 向量化服务
使用 BAAI/bge-small-zh-v1.5 模型将文本转换为向量
模型特点：中文效果优秀、免费、本地运行、资源占用低
"""

import os
from pathlib import Path

from app.config import EMBEDDING_MODEL_NAME, EMBEDDING_DIMENSION

# ==================== HF 离线模式自动启用 ====================
# 模型已在本地缓存时跳过 huggingface_hub 的联网元数据校验：
# - 避免无代理网络下 SSL 失败后的多轮重试拖慢启动
# - 规避 huggingface_hub 1.x httpx 客户端被提前关闭的问题
# 首次在新环境运行（无缓存）时不启用，保证模型可以自动下载
# 注意：必须在此处（sentence_transformers / huggingface_hub 导入之前）设置，
#       huggingface_hub 在 import 时读取该环境变量
_hf_cache_dir = Path(
    os.environ.get("HF_HOME", str(Path.home() / ".cache" / "huggingface"))
) / "hub"
if (_hf_cache_dir / f"models--{EMBEDDING_MODEL_NAME.replace('/', '--')}").exists():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from sentence_transformers import SentenceTransformer  # noqa: E402

# ==================== 全局 Embedding 模型实例 ====================
# 模型在首次使用时加载，之后常驻内存
_embedding_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """
    获取 Embedding 模型实例（懒加载单例模式）

    Returns:
        SentenceTransformer: 已加载的 Embedding 模型
    """
    global _embedding_model
    if _embedding_model is None:
        print(f"正在加载 Embedding 模型: {EMBEDDING_MODEL_NAME} ...")
        # 加载 BAAI/bge-small-zh-v1.5 模型
        # 该模型向量维度为 512，中文语义理解效果优秀
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print(f"Embedding 模型加载完成，向量维度: {EMBEDDING_DIMENSION}")
    return _embedding_model


def embed_text(text: str) -> list[float]:
    """
    将单段文本转换为向量

    Args:
        text: 待向量化的文本

    Returns:
        list[float]: 512 维的向量表示
    """
    model = get_embedding_model()
    # encode 返回 numpy array，转换为 Python list
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    批量将文本转换为向量（用于文档导入时批量处理）

    Args:
        texts: 待向量化的文本列表

    Returns:
        list[list[float]]: 向量列表，每个向量为 512 维
    """
    model = get_embedding_model()
    # 批量编码，效率更高
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()
