<template>
  <div class="sidebar-wrapper" :class="{ 'is-collapsed': appStore.sidebarCollapsed }">
    <div class="sidebar-header">
      <div class="logo-icon">
        <svg viewBox="0 0 32 32" width="28" height="28" fill="none">
          <rect width="32" height="32" rx="8" fill="currentColor" opacity="0.2" />
          <path d="M8 16L12 12L16 16L20 12L24 16" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M12 22V14M20 22V14" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          <circle cx="16" cy="20" r="2" fill="currentColor" />
        </svg>
      </div>
      <div class="logo-text">
        <span class="logo-title">DC Network Planner</span>
        <span class="logo-sub">网络平面地址规划管理</span>
      </div>
    </div>

    <div class="nav-section-label">主菜单</div>

    <el-menu
      :default-active="activeMenu"
      router
      :collapse="appStore.sidebarCollapsed"
      background-color="transparent"
      text-color="var(--color-text-sidebar)"
      active-text-color="var(--color-text-sidebar-active)"
      class="sidebar-menu"
    >
      <el-menu-item index="/dashboard">
        <el-icon><DataAnalysis /></el-icon>
        <span>仪表盘</span>
      </el-menu-item>
      <el-menu-item index="/regions">
        <el-icon><Location /></el-icon>
        <span>Region 管理</span>
      </el-menu-item>
      <el-menu-item index="/plane-types">
        <el-icon><Connection /></el-icon>
        <span>网络平面类型</span>
      </el-menu-item>
      <el-menu-item index="/lookup">
        <el-icon><Search /></el-icon>
        <span>IP 查找</span>
      </el-menu-item>
      <el-menu-item index="/import-export">
        <el-icon><Upload /></el-icon>
        <span>导入 / 导出</span>
      </el-menu-item>
      <el-menu-item index="/change-logs">
        <el-icon><Clock /></el-icon>
        <span>变更历史</span>
      </el-menu-item>
      <el-menu-item index="/backup-config">
        <el-icon><Setting /></el-icon>
        <span>备份配置</span>
      </el-menu-item>
      <el-menu-item v-if="appStore.isAdministrator" index="/users">
        <el-icon><User /></el-icon>
        <span>用户管理</span>
      </el-menu-item>
      <el-menu-item v-if="appStore.isAdministrator" index="/external-access-tokens">
        <el-icon><Key /></el-icon>
        <span>外部 API 访问令牌</span>
      </el-menu-item>
    </el-menu>

    <div class="sidebar-footer">
      <div class="version-badge">v0.1.0</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useAppStore } from '@/stores/app'
import {
  Clock,
  Connection,
  DataAnalysis, Location,
  Key,
  Search,
  Setting,
  Upload,
  User
} from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const appStore = useAppStore()
const activeMenu = computed(() => route.path)
</script>

<style scoped>
.sidebar-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
}

/* ---- Logo Area ---- */
.sidebar-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.logo-icon {
  color: #60a5fa;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-text {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
  min-width: 0;
  transition: opacity var(--transition-fast);
}

.logo-title {
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 1px;
}

.logo-sub {
  color: var(--color-text-sidebar);
  font-size: 11px;
  font-weight: 400;
  opacity: 0.6;
}

/* ---- Nav Section ---- */
.nav-section-label {
  padding: 16px 20px 8px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--color-text-sidebar);
  opacity: 0.4;
  transition: opacity var(--transition-fast);
}

/* ---- Menu ---- */
.sidebar-menu {
  flex: 1;
  border-right: none !important;
  padding: 0 8px;
}

.sidebar-menu:not(.el-menu--collapse) {
  width: 100%;
}

.sidebar-wrapper.is-collapsed .sidebar-header {
  justify-content: center;
  padding: 20px 0;
}

.sidebar-wrapper.is-collapsed .logo-text,
.sidebar-wrapper.is-collapsed .nav-section-label,
.sidebar-wrapper.is-collapsed .sidebar-footer {
  display: none;
}

.sidebar-wrapper.is-collapsed .sidebar-menu {
  padding: 0 8px;
}

.sidebar-menu .el-menu-item {
  height: 42px;
  line-height: 42px;
  border-radius: var(--radius-md);
  margin: 2px 0;
  padding: 0 12px !important;
  color: var(--color-text-sidebar);
  transition: all var(--transition-base);
  position: relative;
}

.sidebar-menu .el-menu-item:hover {
  background: rgba(255, 255, 255, 0.08) !important;
  color: #e2e8f0 !important;
}

.sidebar-menu .el-menu-item.is-active {
  background: var(--color-primary) !important;
  color: #fff !important;
  font-weight: 500;
  box-shadow: 0 2px 8px rgba(26, 115, 232, 0.3);
}

.sidebar-menu .el-menu-item .el-icon {
  font-size: 18px;
  margin-right: 8px;
}

/* ---- Footer ---- */
.sidebar-footer {
  padding: 12px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.version-badge {
  font-size: 11px;
  color: var(--color-text-sidebar);
  opacity: 0.4;
  text-align: center;
}
</style>
