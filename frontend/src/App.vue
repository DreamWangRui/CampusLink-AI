<!--
  CampusLink AI 主布局
  包含：
  - 顶部导航栏
  - 侧边菜单切换（聊天 / 知识库管理）
  - 主内容区（路由视图）
-->
<template>
  <el-container class="app-layout">
    <!-- 顶部导航栏 -->
    <el-header class="app-header">
      <div class="header-left">
        <span class="header-logo">🎓</span>
        <span class="header-title">CampusLink AI</span>
        <span class="header-subtitle">校园智能助手</span>
      </div>
      <div class="header-right">
        <el-tag size="small" type="info">V1.0 MVP</el-tag>
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
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

// ==================== 路由状态 ====================
const route = useRoute()

// 当前激活的菜单项（根据路由路径自动计算）
const activeMenu = computed(() => route.path)
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
