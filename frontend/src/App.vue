<!--
  CampusLink AI 主布局
  包含：
  - 顶部导航栏（用户登录入口 / 用户信息）
  - 侧边菜单切换（聊天 / 知识库管理）
  - 主内容区（路由视图）
  - 登录/注册弹窗
-->
<template>
  <el-config-provider :locale="zhCn">
    <el-container class="app-layout">
      <!-- 顶部导航栏 -->
      <el-header class="app-header">
        <div class="header-left">
          <span class="header-logo">🎓</span>
          <span class="header-title">CampusLink AI</span>
          <span class="header-subtitle">校园智能助手</span>
        </div>
        <div class="header-right">
          <el-tag size="small" type="info">V2.0</el-tag>
          <!-- 已登录：显示用户名与退出 -->
          <template v-if="authStore.isLoggedIn">
            <span class="header-user">
              👤 {{ authStore.username }}
              <el-tag v-if="authStore.isAdmin" size="small" type="warning" class="role-tag">管理员</el-tag>
            </span>
            <el-button text class="header-btn" @click="handleLogout">退出</el-button>
          </template>
          <!-- 未登录：登录/注册入口 -->
          <el-button v-else text class="header-btn" @click="openAuth('login')">
            登录 / 注册
          </el-button>
        </div>
      </el-header>

      <el-container class="app-body">
        <!-- 侧边导航菜单 -->
        <el-aside class="app-sidebar" width="200px">
          <el-menu
            :default-active="activeMenu"
            :router="true"
            class="sidebar-menu"
          >
            <el-menu-item index="/">
              <el-icon><ChatDotRound /></el-icon>
              <span>智能问答</span>
            </el-menu-item>
            <el-menu-item index="/knowledge">
              <el-icon><FolderOpened /></el-icon>
              <span>知识库管理</span>
            </el-menu-item>
          </el-menu>
        </el-aside>

        <!-- 主内容区域 -->
        <el-main class="app-main">
          <router-view />
        </el-main>
      </el-container>
    </el-container>

    <!-- 登录/注册弹窗 -->
    <el-dialog
      v-model="authDialogVisible"
      :title="authMode === 'login' ? '登录' : '注册'"
      width="380px"
      :close-on-click-modal="false"
    >
      <div class="auth-mode-switch">
        <el-radio-group v-model="authMode" size="small">
          <el-radio-button value="login">登录</el-radio-button>
          <el-radio-button value="register">注册新账号</el-radio-button>
        </el-radio-group>
      </div>
      <el-input
        v-model="authForm.username"
        placeholder="账号（2-32 位，字母/数字/下划线/中文）"
        class="auth-field"
        @keyup.enter="submitAuth"
      />
      <el-input
        v-model="authForm.password"
        type="password"
        placeholder="密码（注册至少 6 位）"
        show-password
        class="auth-field"
        @keyup.enter="submitAuth"
      />
      <template #footer>
        <el-button @click="authDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAuth">
          {{ authMode === 'login' ? '登录' : '注册并登录' }}
        </el-button>
      </template>
    </el-dialog>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
// 显式使用的 ElMessage 需手动补样式（unplugin 只处理模板中的组件）
import 'element-plus/es/components/message/style/css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { ChatDotRound, FolderOpened } from '@element-plus/icons-vue'
import { useAuthStore } from './store/auth'
import { extractApiError } from './utils/apiError'

// ==================== 路由状态 ====================
const route = useRoute()

// 当前激活的菜单项（根据路由路径自动计算）
const activeMenu = computed(() => route.path)

// ==================== 认证 ====================
const authStore = useAuthStore()
const authDialogVisible = ref(false)
const authMode = ref<'login' | 'register'>('login')
const authForm = ref({ username: '', password: '' })
const submitting = ref(false)

function openAuth(mode: 'login' | 'register') {
  authMode.value = mode
  authForm.value = { username: '', password: '' }
  authDialogVisible.value = true
}

async function submitAuth() {
  const username = authForm.value.username.trim()
  const password = authForm.value.password
  if (!username || !password) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  // 注册模式前置校验：把常见错误拦在请求发出前
  if (authMode.value === 'register') {
    if (username.length < 2) {
      ElMessage.warning('用户名至少 2 个字符')
      return
    }
    if (password.length < 6) {
      ElMessage.warning('密码至少 6 位')
      return
    }
  }
  submitting.value = true
  try {
    if (authMode.value === 'register') {
      await authStore.register(username, password)
      ElMessage.success('注册并登录成功，聊天记录将云端同步')
    } else {
      await authStore.login(username, password)
      ElMessage.success('登录成功，已同步云端聊天记录')
    }
    authDialogVisible.value = false
    authForm.value = { username: '', password: '' }
  } catch (error: any) {
    ElMessage.error(extractApiError(error, '操作失败'))
  } finally {
    submitting.value = false
  }
}

async function handleLogout() {
  authStore.logout()
  ElMessage.success('已退出登录')
}
</script>

<style scoped>
/* ==================== 全局布局 ==================== */
.app-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ==================== 顶部导航栏 ==================== */
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, #409eff 0%, #337ecc 100%);
  color: #fff;
  padding: 0 24px;
  height: 56px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-logo {
  font-size: 24px;
}

.header-title {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.header-subtitle {
  font-size: 12px;
  opacity: 0.8;
  margin-left: 8px;
  padding-left: 12px;
  border-left: 1px solid rgba(255, 255, 255, 0.4);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-user {
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.role-tag {
  margin-left: 4px;
}

.header-btn {
  color: #fff;
}

.header-btn:hover {
  color: #d9ecff;
}

/* ==================== 登录弹窗 ==================== */
.auth-mode-switch {
  display: flex;
  justify-content: center;
  margin-bottom: 14px;
}

.auth-field {
  margin-bottom: 10px;
}

/* ==================== 侧边栏 ==================== */
.app-body {
  flex: 1;
  overflow: hidden;
}

.app-sidebar {
  background: #fff;
  border-right: 1px solid #e4e7ed;
}

.sidebar-menu {
  border-right: none;
  height: 100%;
  padding-top: 8px;
}

.sidebar-menu .el-menu-item {
  font-size: 14px;
}

/* ==================== 主内容区 ==================== */
.app-main {
  padding: 0;
  overflow: hidden;
  background: #f5f7fa;
}
</style>
