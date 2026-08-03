<template>
  <div class="app-layout">
    <aside
      id="primary-navigation"
      class="sidebar"
      :class="{ 'is-collapsed': sidebarCollapsed }"
      :aria-hidden="isNarrowViewport && sidebarCollapsed"
      :inert="isNarrowViewport && sidebarCollapsed ? true : undefined"
    >
      <SideMenu :collapsed="sidebarCollapsed" />
    </aside>
    <button
      v-if="isNarrowViewport && !sidebarCollapsed"
      class="sidebar-backdrop"
      type="button"
      aria-label="关闭导航菜单"
      @click="closeMobileSidebar"
    ></button>
    <div class="main-container">
      <header class="app-header">
        <div class="header-left">
          <button
            class="menu-fold"
            type="button"
            :aria-label="sidebarCollapsed ? '展开导航菜单' : '收起导航菜单'"
            aria-controls="primary-navigation"
            :aria-expanded="!sidebarCollapsed"
            @click="toggleSidebar"
          >
            <el-icon>
              <Fold v-if="!sidebarCollapsed" />
              <Expand v-else />
            </el-icon>
          </button>
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

<script setup lang="ts">
import { UserFilled, Fold, Expand } from '@element-plus/icons-vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import SideMenu from './SideMenu.vue'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const isNarrowViewport = ref(false)
const mobileSidebarOpen = ref(false)
const sidebarCollapsed = computed(() =>
  isNarrowViewport.value ? !mobileSidebarOpen.value : appStore.sidebarCollapsed
)
let narrowViewportQuery: MediaQueryList | null = null

function handleLogout() {
  appStore.logout()
  router.push('/login')
}

function toggleSidebar() {
  if (isNarrowViewport.value) {
    mobileSidebarOpen.value = !mobileSidebarOpen.value
    return
  }
  appStore.toggleSidebar()
}

function closeMobileSidebar() {
  mobileSidebarOpen.value = false
}

function syncNarrowViewport(event: MediaQueryListEvent | MediaQueryList) {
  isNarrowViewport.value = event.matches
  if (!event.matches) mobileSidebarOpen.value = false
}

function handleWindowKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && mobileSidebarOpen.value) closeMobileSidebar()
}

watch(() => route.path, closeMobileSidebar)

onMounted(() => {
  narrowViewportQuery = window.matchMedia('(max-width: 760px)')
  syncNarrowViewport(narrowViewportQuery)
  narrowViewportQuery.addEventListener('change', syncNarrowViewport)
  window.addEventListener('keydown', handleWindowKeydown)
})

onBeforeUnmount(() => {
  narrowViewportQuery?.removeEventListener('change', syncNarrowViewport)
  window.removeEventListener('keydown', handleWindowKeydown)
})
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
  transition: width var(--transition-base);
}

.sidebar.is-collapsed {
  width: 64px;
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
  display: inline-flex;
  width: 36px;
  height: 36px;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 18px;
  transition: color var(--transition-fast), background var(--transition-fast);
}
.menu-fold:hover {
  color: var(--color-primary);
  background: var(--color-primary-lighter);
}
.menu-fold:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
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

.sidebar-backdrop {
  display: none;
}

@media (max-width: 760px) {
  .sidebar {
    position: fixed;
    inset: 0 auto 0 0;
    width: var(--sidebar-width);
    box-shadow: 12px 0 32px rgba(15, 23, 42, 0.24);
    transform: translateX(0);
    transition: transform var(--transition-base);
  }

  .sidebar.is-collapsed {
    width: var(--sidebar-width);
    transform: translateX(-100%);
  }

  .sidebar-backdrop {
    position: fixed;
    z-index: 9;
    display: block;
    inset: 0;
    border: none;
    background: rgba(15, 23, 42, 0.38);
  }

  .app-header {
    padding-inline: 12px;
  }

  .app-content {
    padding: 16px;
  }

  .operator-area {
    padding-inline: 8px;
  }
}
</style>
