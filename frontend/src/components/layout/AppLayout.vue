<template>
  <div class="app-layout">
    <aside class="sidebar">
      <SideMenu />
    </aside>
    <div class="main-container">
      <header class="app-header">
        <div class="header-left">
          <el-icon class="menu-fold" @click="isCollapsed = !isCollapsed">
            <Fold v-if="!isCollapsed" />
            <Expand v-else />
          </el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.meta.title">{{ route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <div class="operator-area">
            <el-icon><UserFilled /></el-icon>
            <button class="operator-name" type="button" @click="router.push('/profile')">
              {{ appStore.currentUser?.username }}
            </button>
            <el-button size="small" text @click="handleLogout">退出</el-button>
          </div>
        </div>
      </header>
      <main class="app-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { UserFilled, Fold, Expand } from '@element-plus/icons-vue'
import SideMenu from './SideMenu.vue'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const isCollapsed = ref(false)

function handleLogout() {
  appStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
  background: var(--color-bg-sidebar);
  overflow-y: auto;
  overflow-x: hidden;
  z-index: 10;
}

.main-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-bg);
}

.app-header {
  height: var(--header-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--spacing-lg);
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  flex-shrink: 0;
  z-index: 5;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.menu-fold {
  font-size: 18px;
  color: var(--color-text-secondary);
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}
.menu-fold:hover {
  color: var(--color-primary);
  background: var(--color-primary-lighter);
}

.header-right {
  display: flex;
  align-items: center;
}

.operator-area {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: var(--color-bg);
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
}
.operator-area:hover {
  background: var(--color-border-light);
}
.operator-area .el-icon {
  font-size: 16px;
  color: var(--color-text-tertiary);
}

.operator-name {
  max-width: 180px;
  overflow: hidden;
  border: none;
  background: transparent;
  font-family: inherit;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
  cursor: pointer;
  font-weight: 600;
  line-height: 1.4;
  padding: 0;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.operator-name:hover {
  color: var(--color-primary);
}

.app-content {
  flex: 1;
  padding: var(--spacing-lg);
  overflow-y: auto;
  overflow-x: hidden;
}
</style>
