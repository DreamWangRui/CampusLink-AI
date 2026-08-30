"""
LLM 服务
通过 OpenAI 兼容接口调用 DeepSeek 大模型生成回答
使用 OpenAI Python SDK，兼容 DeepSeek API
"""

import logging
import time

from openai import OpenAI

from app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME

logger = logging.getLogger(__name__)

# ==================== 系统提示词 ====================
# 定义 AI 助手的角色和行为规范
SYSTEM_PROMPT = """你是学校官方校园助手。

你的职责是回答学生关于宿舍、食堂、校园卡、图书馆、驾校、奖学金、校医院等问题。

重要规则：

1. 回答必须依据提供的知识库内容，从知识库中提取关键信息来组织答案
2. 如果知识库中有相关信息但不够完整，请基于已有信息尽力回答，同时诚实说明哪些信息来自知识库、哪些还不确定
3. 只有知识库中完全没有任何相关内容时，才回答"目前知识库暂无相关信息，请咨询学校相关部门。"
4. 不要凭空编造知识库中没有的事实和数据"""

# ==================== OpenAI 客户端（兼容 DeepSeek） ====================
# 通过设置 base_url 指向 DeepSeek API 地址，复用 OpenAI SDK
_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
)


def generate_answer(question: str, context_chunks: list[str]) -> str:
    """
    基于检索到的知识库上下文，调用 DeepSeek 生成回答

    Args:
        question: 用户原始问题
        context_chunks: 从知识库检索到的相关文本片段（Top 5）

    Returns:
        str: AI 生成的回答
    """
    # 构建用户 Prompt，包含知识库内容和用户问题
    user_message = _build_user_message(question, context_chunks)

    # 调用 DeepSeek Chat API
    t0 = time.time()
    response = _client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,  # 较低温度以保证回答的准确性和一致性
        max_tokens=2048,   # 增大回答长度限制，让回答更完整
    )
    usage = response.usage
    logger.info(
        "LLM 生成完成: %.1fs | 回答 %d 字 | tokens: 输入 %d / 输出 %d",
        time.time() - t0,
        len(response.choices[0].message.content or ""),
        usage.prompt_tokens if usage else -1,
        usage.completion_tokens if usage else -1,
    )

    # 提取模型生成的回答文本
    answer = response.choices[0].message.content
    return answer if answer else "抱歉，生成回答时出现错误，请稍后重试。"


def generate_answer_stream(question: str, context_chunks: list[str]):
    """
    流式生成回答：逐段 yield 模型输出的文本片段（用于 SSE 流式接口）

    Args:
        question: 用户原始问题
        context_chunks: 从知识库检索到的相关文本片段

    Yields:
        str: 模型增量输出的文本片段
    """
    stream = _client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(question, context_chunks)},
        ],
        temperature=0.3,
        max_tokens=2048,
        stream=True,
    )
    t0 = time.time()
    total_chars = 0
    for chunk in stream:
        if chunk.choices:
            delta = chunk.choices[0].delta.content
            if delta:
                total_chars += len(delta)
                yield delta
    logger.info("LLM 流式生成完成: %.1fs | 回答 %d 字", time.time() - t0, total_chars)


def _build_user_message(question: str, context_chunks: list[str]) -> str:
    """构建包含知识库上下文的用户 Prompt（普通生成与流式生成共用）"""
    context = "\n\n---\n\n".join(context_chunks)
    return f"""以下是从校园知识库中检索到的相关内容片段（共 {len(context_chunks)} 段）：

{context}

请根据以上知识库内容，回答用户的问题。注意：
- 仔细阅读所有片段，不同片段可能包含互补信息
- 如果某个片段的金额、时间等关键数据与问题相关，请务必引用
- 综合多个片段的信息来给出完整答案

用户问题：

{question}"""
