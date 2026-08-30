"""
Pydantic 数据模型定义
定义 API 请求和响应的数据结构
"""


from pydantic import BaseModel, Field

# ==================== 聊天相关模型 ====================

class HistoryItem(BaseModel):
    """对话历史条目（多轮对话用）"""
    role: str = Field(..., description="角色：user / assistant", pattern="^(user|assistant)$")
    content: str = Field(..., description="消息内容", min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    """聊天请求模型"""
    question: str = Field(..., description="用户提出的问题", min_length=1, max_length=2000)
    history: list[HistoryItem] = Field(
        default_factory=list,
        description="最近对话历史（用于追问改写与生成上下文），最多 10 条",
        max_length=10,
    )
    session_id: str | None = Field(
        default=None,
        description="目标会话 ID（已登录多会话用；不传则自动新建会话）",
        max_length=64,
    )


class SourceRef(BaseModel):
    """回答引用的知识库片段来源"""
    filename: str = Field(..., description="来源文档名称")
    chunk_index: int | None = Field(None, description="片段序号")
    distance: float = Field(..., description="与问题的余弦距离（越小越相关）")


class ChatResponse(BaseModel):
    """聊天响应模型"""
    answer: str = Field(..., description="AI 生成的回答")
    sources: list[SourceRef] = Field(default_factory=list, description="回答参考的知识库片段来源")


# ==================== 知识库管理模型 ====================

class KnowledgeDocument(BaseModel):
    """知识库文档信息模型"""
    id: str = Field(..., description="文档唯一标识（ChromaDB 中的文档 ID 前缀）")
    filename: str = Field(..., description="文档名称")
    folder: str = Field(default="", description="所属文件夹/分类")
    upload_time: str = Field(..., description="上传时间")
    chunk_count: int = Field(..., description="文档切分后的 Chunk 数量")


class KnowledgeListResponse(BaseModel):
    """知识库文档列表响应模型"""
    documents: list[KnowledgeDocument] = Field(default_factory=list, description="文档列表")
    total: int = Field(..., description="文档总数")


class DeleteDocumentRequest(BaseModel):
    """删除文档请求模型"""
    doc_id: str = Field(..., description="要删除的文档 ID")


class DeleteDocumentResponse(BaseModel):
    """删除文档响应模型"""
    success: bool = Field(..., description="是否删除成功")
    message: str = Field(..., description="操作结果消息")


class MoveDocumentRequest(BaseModel):
    """移动文档到其他文件夹请求模型"""
    doc_id: str = Field(..., description="要移动的文档 ID")
    folder: str = Field(..., description="目标文件夹名称（留空归入未分类，输入新名称即创建）", max_length=50)


class MoveDocumentResponse(BaseModel):
    """移动文档响应模型"""
    success: bool = Field(..., description="是否移动成功")
    message: str = Field(..., description="操作结果消息")


class BatchUploadFileResult(BaseModel):
    """批量上传中单个文件的结果"""
    success: bool = Field(..., description="该文件是否上传成功")
    filename: str = Field(..., description="文件名")
    chunk_count: int = Field(default=0, description="切分后的 Chunk 数量")
    message: str = Field(default="", description="处理结果消息")


class BatchUploadResponse(BaseModel):
    """批量上传响应模型"""
    files: list[BatchUploadFileResult] = Field(default_factory=list, description="每个文件的上传结果")
    total_chunks: int = Field(default=0, description="本次上传的总 Chunk 数")
    message: str = Field(default="", description="整体操作结果消息")


class FolderInfo(BaseModel):
    """文件夹/分类信息模型"""
    name: str = Field(..., description="文件夹名称")
    document_count: int = Field(..., description="该文件夹下的文档数量")
