<!--
  知识库管理页面
  功能：
  - 批量文件上传（支持多选 PDF/DOCX/TXT/MD）
  - 文件夹/分类选择（可选择已有文件夹或输入新名称）
  - 按文件夹筛选文档列表
  - 文档删除
-->
<template>
  <div class="knowledge-container">
    <!-- 页面头部 -->
    <div class="knowledge-header">
      <h2>知识库管理</h2>
      <p>管理校园知识库中的文档，支持 PDF、DOCX、TXT、Markdown 格式，支持批量上传和文件夹分类</p>
    </div>

    <!-- 上传区域 -->
    <div v-if="authStore.isAdmin" class="upload-section">
      <el-upload
        ref="uploadRef"
        class="upload-area"
        :auto-upload="false"
        :show-file-list="false"
        :accept="'.pdf,.docx,.txt,.md'"
        :multiple="true"
        :on-change="handleFileChange"
      >
        <div class="upload-trigger">
          <el-icon class="upload-icon"><UploadFilled /></el-icon>
          <div class="upload-text">
            <span class="upload-primary">点击选择文件（支持多选）</span>
            <span class="upload-secondary">或将文件拖拽到此处</span>
          </div>
          <span class="upload-hint">支持 PDF / DOCX / TXT / MD，可一次选择多个文件</span>
        </div>
      </el-upload>

      <!-- 上传进度提示：整体进度 + 逐文件实时结果 -->
      <div v-if="knowledgeStore.uploading" class="upload-progress">
        <el-progress
          :percentage="knowledgeStore.taskTotal ? Math.round(knowledgeStore.taskDone / knowledgeStore.taskTotal * 100) : 0"
          :stroke-width="10"
        />
        <span>{{ knowledgeStore.taskDone }} / {{ knowledgeStore.taskTotal }} 个文件已处理</span>
      </div>
      <div v-if="knowledgeStore.uploading && knowledgeStore.taskFiles.length" class="upload-task-files">
        <div
          v-for="(f, i) in knowledgeStore.taskFiles"
          :key="i"
          class="task-file-item"
        >
          <el-icon v-if="f.success" class="task-ok"><CircleCheckFilled /></el-icon>
          <el-icon v-else class="task-fail"><CircleCloseFilled /></el-icon>
          <span class="task-file-name">{{ f.filename }}</span>
          <span class="task-file-msg" :class="f.success ? 'ok' : 'fail'">{{ f.message }}</span>
        </div>
      </div>

      <!-- 已选择的文件列表 + 文件夹选择 -->
      <div v-if="selectedFiles.length > 0" class="selected-files-panel">
        <!-- 文件夹/分类选择 -->
        <div class="folder-select-row">
          <span class="folder-label">分类：</span>
          <el-select
            v-model="uploadFolder"
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入文件夹名称"
            style="width: 280px"
            :disabled="knowledgeStore.uploading"
          >
            <el-option
              v-for="f in knowledgeStore.folders"
              :key="f.name"
              :label="`${f.name} (${f.document_count} 个文档)`"
              :value="f.name"
            />
          </el-select>
          <span class="folder-hint">可选择已有分类或直接输入新分类名（自动创建），留空归入"未分类"</span>
        </div>

        <!-- 文件列表 -->
        <div class="file-list">
          <div v-for="(f, i) in selectedFiles" :key="i" class="file-item">
            <el-icon class="file-icon"><Document /></el-icon>
            <span class="file-name">{{ f.name }}</span>
            <span class="file-size">{{ formatFileSize(f.size) }}</span>
            <el-button
              type="danger" link size="small"
              :disabled="knowledgeStore.uploading"
              @click="removeFile(i)"
            >
              <el-icon><Close /></el-icon>
            </el-button>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="upload-actions">
          <span class="file-count">已选 {{ selectedFiles.length }} 个文件</span>
          <el-button
            type="primary"
            :loading="knowledgeStore.uploading"
            @click="handleUpload"
          >
            确认上传（{{ selectedFiles.length }} 个文件）
          </el-button>
        </div>
      </div>
    </div>

    <!-- 文档列表区域 -->
    <div class="document-section">
      <div class="section-header">
        <h3>已导入文档（{{ knowledgeStore.total }}）</h3>
        <div class="header-actions">
          <el-button
            size="small"
            :type="knowledgeStore.needsAuth ? 'warning' : 'default'"
            :icon="Lock"
            @click="authDialogVisible = true"
          >
            {{ knowledgeStore.needsAuth ? '管理员验证' : '管理员' }}
          </el-button>
          <el-button :icon="Refresh" size="small" @click="refreshAll">
            刷新
          </el-button>
        </div>
      </div>

      <!-- 文件夹筛选栏 -->
      <div v-if="knowledgeStore.folders.length > 0" class="folder-filter">
        <span class="filter-label">按分类筛选：</span>
        <el-radio-group
          v-model="knowledgeStore.selectedFolder"
          size="small"
          @change="handleFolderChange"
        >
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button
            v-for="f in knowledgeStore.folders"
            :key="f.name"
            :value="f.name"
          >
            {{ f.name }} ({{ f.document_count }})
          </el-radio-button>
        </el-radio-group>
      </div>

      <!-- 加载中 -->
      <div v-if="knowledgeStore.loading" class="loading-state">
        <el-skeleton :rows="3" animated />
      </div>

      <!-- 空状态 -->
      <el-empty
        v-else-if="knowledgeStore.documents.length === 0"
        :description="knowledgeStore.selectedFolder ? `'${knowledgeStore.selectedFolder}' 下暂无文档` : '暂无文档，请上传校园相关知识文件'"
        :image-size="120"
      />

      <!-- 文档表格 -->
      <el-table
        v-else
        :data="knowledgeStore.documents"
        stripe
        style="width: 100%"
        :header-cell-style="{ background: '#f5f7fa', color: '#303133' }"
      >
        <el-table-column prop="filename" label="文档名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="folder" label="文件夹" width="140" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.folder" size="small" type="warning">{{ row.folder }}</el-tag>
            <span v-else style="color: #c0c4cc; font-size: 12px;">未分类</span>
          </template>
        </el-table-column>
        <el-table-column prop="upload_time" label="上传时间" width="180" />
        <el-table-column prop="chunk_count" label="Chunk 数量" width="120" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.chunk_count }} 个</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="authStore.isAdmin" label="操作" width="170" align="center">
          <template #default="{ row }">
            <el-button type="primary" size="small" :icon="Position" link
              @click="openMoveDialog(row)">
              移动
            </el-button>
            <el-popconfirm
              title="确定要删除该文档吗？"
              confirm-button-text="确认删除"
              cancel-button-text="取消"
              @confirm="handleDelete(row.id)"
            >
              <template #reference>
                <el-button type="danger" size="small" :icon="Delete" link>
                  删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 移动文档弹窗 -->
    <el-dialog
      v-model="moveDialogVisible"
      :title="`移动文档：${moveTargetDoc?.filename ?? ''}`"
      width="440px"
      :close-on-click-modal="false"
    >
      <div class="move-form-row">
        <span class="move-label">目标分类：</span>
        <el-select
          v-model="moveFolderInput"
          filterable
          allow-create
          default-first-option
          placeholder="选择已有分类或输入新分类名"
          style="flex: 1"
        >
          <el-option label="未分类" value="" />
          <el-option
            v-for="f in knowledgeStore.folders.filter(x => x.name !== '未分类')"
            :key="f.name"
            :label="`${f.name} (${f.document_count} 个文档)`"
            :value="f.name"
          />
        </el-select>
      </div>
      <p class="move-hint">输入列表中没有的分类名即自动创建新分类；留空归入"未分类"。</p>
      <template #footer>
        <el-button @click="moveDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="knowledgeStore.loading" @click="handleMove">
          确认移动
        </el-button>
      </template>
    </el-dialog>

    <!-- 管理员登录弹窗 -->
    <el-dialog
      v-model="authDialogVisible"
      title="管理员登录"
      width="400px"
      :close-on-click-modal="false"
    >
      <p class="auth-hint">
        登录后可查看知识库文档（普通用户只读）；管理员账号（默认 admin / admin123，可在 .env 修改）还可上传、删除与移动文档。
      </p>
      <el-input
        v-model="authUsername"
        placeholder="账号"
        class="auth-input"
        @keyup.enter="handleLogin"
      />
      <el-input
        v-model="authPassword"
        type="password"
        placeholder="密码"
        show-password
        class="auth-input"
        @keyup.enter="handleLogin"
      />
      <template #footer>
        <div class="auth-footer">
          <el-button v-if="authStore.isLoggedIn" text type="danger" @click="handleLogout">退出登录</el-button>
          <span class="auth-footer-actions">
            <el-button @click="authDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="knowledgeStore.loading" @click="handleLogin">
              登录并加载
            </el-button>
          </span>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
// 显式使用的 ElMessage 需手动补样式（unplugin 只处理模板中的组件）
import 'element-plus/es/components/message/style/css'
import {
  CircleCheckFilled,
  CircleCloseFilled,
  Close,
  Delete,
  Document,
  Lock,
  Position,
  Refresh,
  UploadFilled,
} from '@element-plus/icons-vue'
import { useAuthStore } from '../store/auth'
import { useKnowledgeStore } from '../store/knowledge'
import { formatFileSize } from '../utils/format'
import { extractApiError } from '../utils/apiError'
import type { UploadFile } from 'element-plus'
import type { KnowledgeDocument } from '../types'

// ==================== 状态管理 ====================
const knowledgeStore = useKnowledgeStore()
const authStore = useAuthStore()

// ==================== 文件选择状态 ====================
const selectedFiles = ref<File[]>([])

// ==================== 文件夹选择 ====================
const uploadFolder = ref('')

/**
 * 处理文件选择变化（支持多选）
 * Element Plus 在 multiple 模式下，每选择一个文件触发一次 change
 */
function handleFileChange(file: UploadFile) {
  if (!file.raw) return
  // 避免重复添加（按名称 + 大小去重）
  const exists = selectedFiles.value.some(
    f => f.name === file.name && f.size === file.size
  )
  if (!exists) {
    selectedFiles.value.push(file.raw)
  }
}

/**
 * 从已选列表中移除单个文件
 */
function removeFile(index: number) {
  selectedFiles.value.splice(index, 1)
}

/**
 * 处理批量上传
 */
async function handleUpload() {
  if (selectedFiles.value.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }

  try {
    const message = await knowledgeStore.upload(selectedFiles.value, uploadFolder.value)
    ElMessage.success(message)
    // 失败的文件保留在已选列表中便于重试，成功的移除
    const failedNames = new Set(
      knowledgeStore.taskFiles.filter(f => !f.success).map(f => f.filename)
    )
    selectedFiles.value = selectedFiles.value.filter(f => failedNames.has(f.name))
  } catch (error: any) {
    ElMessage.error(typeof error === 'string' ? error : error.message || '上传失败')
  }
}

/**
 * 处理文件夹筛选切换
 */
function handleFolderChange(_value: string) {
  knowledgeStore.loadDocuments()
}

/**
 * 处理文档删除
 */
async function handleDelete(docId: string) {
  try {
    const message = await knowledgeStore.removeDocument(docId)
    ElMessage.success(message)
  } catch (error: any) {
    ElMessage.error(typeof error === 'string' ? error : error.message || '删除失败')
  }
}

// ==================== 移动文档 ====================
/** 移动弹窗可见性 */
const moveDialogVisible = ref(false)

/** 待移动的文档 */
const moveTargetDoc = ref<KnowledgeDocument | null>(null)

/** 移动目标分类输入（空字符串 = 未分类） */
const moveFolderInput = ref('')

/**
 * 打开移动弹窗（预填当前所在分类）
 */
function openMoveDialog(doc: KnowledgeDocument) {
  moveTargetDoc.value = doc
  moveFolderInput.value = doc.folder
  moveDialogVisible.value = true
}

/**
 * 确认移动
 */
async function handleMove() {
  if (!moveTargetDoc.value) return
  try {
    const message = await knowledgeStore.moveDocument(moveTargetDoc.value.id, moveFolderInput.value.trim())
    ElMessage.success(message)
    moveDialogVisible.value = false
  } catch (error: any) {
    ElMessage.error(typeof error === 'string' ? error : error.message || '移动失败')
  }
}

/**
 * 刷新全部数据
 */
function refreshAll() {
  knowledgeStore.loadDocuments()
  knowledgeStore.loadFolders()
}

// ==================== 管理员登录 ====================
const authDialogVisible = ref(false)
const authUsername = ref('admin')
const authPassword = ref('')

// 鉴权失败（401）时自动弹出登录弹窗
watch(
  () => knowledgeStore.needsAuth,
  (needs) => {
    if (needs) authDialogVisible.value = true
  },
)

/** 登录：成功后关闭弹窗；账号/密码错误时提示并保持弹窗 */
async function handleLogin() {
  const username = authUsername.value.trim()
  const password = authPassword.value
  if (!username || !password) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  try {
    const role = await authStore.login(username, password)
    authDialogVisible.value = false
    authPassword.value = ''
    ElMessage.success(role === 'admin' ? '管理员登录成功' : '登录成功')
  } catch (error: any) {
    ElMessage.error(extractApiError(error, '登录失败'))
  }
}

/** 退出登录：清除令牌，管理接口将返回 401 并重新弹出登录弹窗 */
async function handleLogout() {
  await authStore.logout()
  ElMessage.success('已退出登录')
  await Promise.all([knowledgeStore.loadDocuments(), knowledgeStore.loadFolders()])
}

// ==================== 页面加载 ====================
onMounted(() => {
  knowledgeStore.loadDocuments()
  knowledgeStore.loadFolders()
})
</script>

<style scoped>
/* ==================== 整体布局 ==================== */
.knowledge-container {
  padding: 24px;
  height: 100%;
  overflow-y: auto;
  background: #f5f7fa;
}

/* ==================== 页面头部 ==================== */
.knowledge-header {
  margin-bottom: 24px;
}

.knowledge-header h2 {
  font-size: 20px;
  color: #303133;
  margin-bottom: 8px;
}

.knowledge-header p {
  font-size: 13px;
  color: #909399;
}

/* ==================== 上传区域 ==================== */
.upload-section {
  margin-bottom: 24px;
}

.upload-area {
  width: 100%;
}

.upload-trigger {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  transition: all 0.3s;
}

.upload-trigger:hover {
  border-color: #409eff;
  background: #ecf5ff;
}

.upload-icon {
  font-size: 36px;
  color: #c0c4cc;
  margin-bottom: 12px;
}

.upload-text {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  margin-bottom: 8px;
}

.upload-primary {
  font-size: 15px;
  color: #409eff;
  font-weight: 500;
}

.upload-secondary {
  font-size: 13px;
  color: #c0c4cc;
}

.upload-hint {
  font-size: 12px;
  color: #c0c4cc;
}

/* ==================== 上传进度 ==================== */
.upload-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
  padding: 12px 16px;
  background: #fff;
  border-radius: 6px;
  font-size: 13px;
  color: #606266;
}

.upload-progress :deep(.el-progress) {
  flex: 1;
}

/* 逐文件上传结果 */
.upload-task-files {
  margin-top: 8px;
  padding: 8px 16px;
  background: #fff;
  border-radius: 6px;
  max-height: 220px;
  overflow-y: auto;
}

.task-file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
  border-bottom: 1px solid #f5f7fa;
}

.task-file-item:last-child {
  border-bottom: none;
}

.task-ok {
  color: #67c23a;
}

.task-fail {
  color: #f56c6c;
}

.task-file-name {
  flex-shrink: 0;
  max-width: 40%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #303133;
}

.task-file-msg {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-file-msg.ok {
  color: #909399;
}

.task-file-msg.fail {
  color: #f56c6c;
}

/* ==================== 已选文件面板 ==================== */
.selected-files-panel {
  margin-top: 12px;
  padding: 16px;
  background: #fff;
  border-radius: 8px;
}

/* 文件夹选择行 */
.folder-select-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  padding-bottom: 14px;
  border-bottom: 1px solid #ebeef5;
}

.folder-label {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
  white-space: nowrap;
}

.folder-hint {
  font-size: 12px;
  color: #c0c4cc;
}

/* 文件列表 */
.file-list {
  max-height: 200px;
  overflow-y: auto;
  margin-bottom: 14px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  transition: background 0.2s;
}

.file-item:hover {
  background: #f5f7fa;
}

.file-icon {
  color: #409eff;
  font-size: 16px;
}

.file-name {
  flex: 1;
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

/* 上传操作按钮 */
.upload-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 14px;
  border-top: 1px solid #ebeef5;
}

.file-count {
  font-size: 13px;
  color: #606266;
}

/* ==================== 文档列表区域 ==================== */
.document-section {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ==================== 管理员登录弹窗 ==================== */
.auth-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: #909399;
  line-height: 1.6;
}

.auth-input {
  margin-bottom: 10px;
}

.auth-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.auth-footer-actions {
  display: flex;
  gap: 8px;
}

.section-header h3 {
  font-size: 16px;
  color: #303133;
  font-weight: 600;
}

/* ==================== 文件夹筛选 ==================== */
.folder-filter {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.filter-label {
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
}

.loading-state {
  padding: 20px;
}

/* ==================== 移动文档弹窗 ==================== */
.move-form-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.move-label {
  font-size: 14px;
  color: #303133;
  white-space: nowrap;
}

.move-hint {
  margin: 12px 0 0;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
</style>
