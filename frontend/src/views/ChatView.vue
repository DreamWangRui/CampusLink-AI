<!--
  聊天问答页面（首页）
  功能：
  - 聊天消息展示区（用户消息 / AI 回复，支持 Markdown 渲染）
  - 消息输入框和发送按钮
  - 打字等待动画
-->
<template>
  <div class="chat-container">
    <!-- 聊天消息展示区 -->
    <div class="chat-messages" ref="messagesContainer">
      <!-- 空状态：未开始聊天时显示欢迎信息 -->
      <div v-if="chatStore.messages.length === 0" class="welcome-section">
        <div class="welcome-icon">🎓</div>
        <h2>欢迎使用 CampusLink AI</h2>
        <p>我是校园智能助手，可以回答关于宿舍、食堂、校园卡、图书馆、驾校、奖学金、校医院等问题。</p>
        <div class="suggestions">
          <span class="suggestion-label">你可以试试问：</span>
          <el-tag
            v-for="q in suggestedQuestions"
            :key="q"
            class="suggestion-tag"
            @click="askQuestion(q)"
          >
            {{ q }}
          </el-tag>
        </div>
      </div>

      <!-- 聊天消息列表 -->
      <div
        v-for="(msg, index) in chatStore.messages"
        :key="index"
        class="message-wrapper"
        :class="msg.role"
      >
        <!-- 消息头像 -->
        <div class="message-avatar">
          <el-avatar v-if="msg.role === 'user'" :size="36" icon="UserFilled" />
          <el-avatar v-else :size="36" style="background-color: #409eff">
            🎓
          </el-avatar>
        </div>
        <!-- 消息内容 -->
        <div class="message-content">
          <div class="message-role">{{ msg.role === 'user' ? '我' : '校园助手' }}</div>
          <!-- AI 回复使用 Markdown 渲染，用户消息纯文本 -->
          <div
            v-if="msg.role === 'assistant'"
            class="message-text markdown-body"
            v-html="renderMarkdown(msg.content)"
          ></div>
          <div v-else class="message-text">{{ msg.content }}</div>
          <div class="message-time">{{ msg.time }}</div>
        </div>
      </div>

      <!-- 等待 AI 回复时的加载动画 -->
      <div v-if="chatStore.loading" class="message-wrapper assistant">
        <div class="message-avatar">
          <el-avatar :size="36" style="background-color: #409eff">🎓</el-avatar>
        </div>
        <div class="message-content">
          <div class="message-role">校园助手</div>
          <div class="typing-indicator">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部输入区域 -->
    <div class="chat-input-area">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="2"
        placeholder="输入你的问题，例如：校园卡丢了怎么办？"
        :disabled="chatStore.loading"
        resize="none"
        @keydown.enter.exact.prevent="handleSend"
      />
      <div class="input-actions">
        <span class="input-hint">按 Enter 发送</span>
        <el-button
          type="primary"
          :icon="'Promotion'"
          :loading="chatStore.loading"
          :disabled="!inputText.trim()"
          @click="handleSend"
        >
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import { useChatStore } from '../store/chat'
import MarkdownIt from 'markdown-it'

// ==================== 聊天状态管理 ====================
const chatStore = useChatStore()

// ==================== 输入框绑定 ====================
const inputText = ref('')

// ==================== 消息容器引用（用于自动滚动） ====================
const messagesContainer = ref<HTMLElement | null>(null)

// ==================== Markdown 渲染器 ====================
// 配置 markdown-it 解析器
const md = new MarkdownIt({
  html: false,       // 禁用 HTML 标签（安全考虑）
  breaks: true,      // 将换行符转换为 <br>
  linkify: true,     // 自动将 URL 转换为链接
})

/**
 * 渲染 Markdown 文本为 HTML
 *
 * @param text - Markdown 格式文本
 * @returns HTML 字符串
 */
function renderMarkdown(text: string): string {
  try {
    return md.render(text)
  } catch {
    return text
  }
}

// ==================== 推荐问题 ====================
const suggestedQuestions = [
  '校园卡丢了怎么办？',
  '第三食堂营业到几点？',
  '图书馆周末开放吗？',
  '驾校在哪里报名？',
]

// ==================== 发送消息 ====================
async function handleSend() {
  const question = inputText.value.trim()
  if (!question || chatStore.loading) return

  // 清空输入框
  inputText.value = ''

  // 发送消息并获取回复
  await chatStore.send(question)

  // 滚动到底部
  await nextTick()
  scrollToBottom()
}

/**
 * 点击推荐问题时触发
 */
async function askQuestion(question: string) {
  inputText.value = question
  await handleSend()
}

/**
 * 滚动聊天窗口到底部
 */
function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// ==================== 监听消息变化自动滚动 ====================
watch(
  () => chatStore.messages.length,
  async () => {
    await nextTick()
    scrollToBottom()
  }
)

onMounted(() => {
  // 页面加载完成后显示欢迎界面（无需额外操作）
})
</script>

<style scoped>
/* ==================== 聊天容器整体布局 ==================== */
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f5f7fa;
}

/* ==================== 消息展示区 ==================== */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  scroll-behavior: smooth;
}

/* ==================== 欢迎界面 ==================== */
.welcome-section {
  text-align: center;
  padding: 80px 20px;
  color: #606266;
}

.welcome-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

.welcome-section h2 {
  font-size: 24px;
  color: #303133;
  margin-bottom: 12px;
}

.welcome-section p {
  font-size: 14px;
  margin-bottom: 24px;
  line-height: 1.6;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  align-items: center;
}

.suggestion-label {
  font-size: 13px;
  color: #909399;
}

.suggestion-tag {
  cursor: pointer;
  transition: all 0.3s;
}

.suggestion-tag:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.3);
}

/* ==================== 消息条目 ==================== */
.message-wrapper {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 用户消息靠右 */
.message-wrapper.user {
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

.message-content {
  max-width: 75%;
}

.message-wrapper.user .message-content {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.message-role {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.message-text {
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

/* 用户消息样式 */
.message-wrapper.user .message-text {
  background: #409eff;
  color: #fff;
  border-bottom-right-radius: 4px;
}

/* AI 消息样式 */
.message-wrapper.assistant .message-text {
  background: #fff;
  color: #303133;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.message-time {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 4px;
}

/* ==================== Markdown 渲染样式 ==================== */
.markdown-body :deep(p) {
  margin: 0 0 8px 0;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(code) {
  background: #f0f2f5;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 13px;
}

.markdown-body :deep(pre) {
  background: #f0f2f5;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 20px;
  margin: 4px 0;
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid #409eff;
  padding-left: 12px;
  margin: 8px 0;
  color: #606266;
}

/* ==================== 打字指示器动画 ==================== */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 12px 16px;
  background: #fff;
  border-radius: 12px;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #c0c4cc;
  animation: typing 1.4s infinite ease-in-out both;
}

.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
.typing-indicator span:nth-child(3) { animation-delay: 0s; }

@keyframes typing {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* ==================== 底部输入区域 ==================== */
.chat-input-area {
  padding: 16px 24px 24px;
  background: #fff;
  border-top: 1px solid #e4e7ed;
}

.chat-input-area :deep(.el-textarea__inner) {
  border-radius: 8px;
  font-size: 14px;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}

.input-hint {
  font-size: 12px;
  color: #c0c4cc;
}
</style>
