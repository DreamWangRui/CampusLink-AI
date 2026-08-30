"""
CampusLink AI 配置文件
管理所有环境变量和应用配置
"""

import os
from pathlib import Path

# ==================== 加载 .env 环境变量 ====================
# 从项目根目录加载 .env 文件（backend 的上一级）
from dotenv import load_dotenv

# 项目根目录（backend 的上一级）
# 本地开发：backend/app/config.py 向上三级 = 项目根目录
# Docker 容器：代码位于 /app/app/config.py，向上三级会错误地推到 /，
# 导致数据写入容器可写层（重建即丢失、挂载卷空转），因此支持
# 通过 APP_BASE_DIR 环境变量显式指定（Dockerfile 中设为 /app）
BASE_DIR = Path(os.getenv("APP_BASE_DIR", str(Path(__file__).resolve().parent.parent.parent)))

# 加载 .env 文件中的环境变量
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"[OK] 已加载环境变量文件: {env_path}")
else:
    print(f"[WARN] 未找到 .env 文件: {env_path}，将使用默认配置")

# 上传文件存储目录
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ChromaDB 持久化存储目录
CHROMA_DB_DIR = BASE_DIR / "chroma_db"
CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)

# ==================== DeepSeek API 配置 ====================
# 通过 OpenAI 兼容接口调用 DeepSeek
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "your_api_key_here")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-chat")

# ==================== Embedding 模型配置 ====================
# 使用 BAAI/bge-small-zh-v1.5，中文效果优秀，本地运行，资源占用低
EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
# 向量维度：512
EMBEDDING_DIMENSION = 512

# ==================== 文本切分配置 ====================
# 每个文本块的最大字符数（增大以保留更完整的语义单元）
CHUNK_SIZE = 800
# 相邻文本块之间的重叠字符数（增大以减少信息在边界丢失）
CHUNK_OVERLAP = 200

# ==================== RAG 检索配置 ====================
# 检索返回的 Top K 相关文档片段数（适当增大以提高命中率）
TOP_K = 7
# 相似度阈值（ChromaDB 余弦距离 = 1 - 余弦相似度，越小越相关）
# 实测标定：相关查询 distance 约 0.5~0.65，无关查询约 1.3+；超过阈值的片段
# 视为不相关，全部被过滤时直接返回"暂无相关信息"，避免弱相关内容污染回答
SIMILARITY_DISTANCE_THRESHOLD = 0.8

# ==================== ChromaDB 配置 ====================
# 知识库集合名称
COLLECTION_NAME = "campus_knowledge"

# ==================== 支持的文件类型 ====================
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

# ==================== 上传文件限制 ====================
# 单个文件大小上限（全量读入内存解析前校验，防止超大文件打爆内存）
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
