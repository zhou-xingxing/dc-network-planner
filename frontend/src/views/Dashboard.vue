<template>
  <div class="dashboard">
    <div class="page-heading">
      <h2 class="page-title">仪表盘</h2>
      <p class="page-desc">系统概览与统计数据</p>
    </div>

    <!-- Stat Cards -->
    <el-row :gutter="20" class="stat-row">
      <el-col :xs="12" :sm="12" :md="6" v-for="card in statCards" :key="card.label">
        <RouterLink class="stat-card-link" :to="card.to" :aria-label="`查看${card.label}`">
          <div class="stat-card" :style="{ '--card-gradient': card.gradient, '--card-accent': card.accent }">
            <div class="stat-card-body">
              <div class="stat-icon-wrap">
                <el-icon :size="24"><component :is="card.icon" /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats[card.key] }}</div>
                <div class="stat-label">{{ card.label }}</div>
              </div>
            </div>
            <div class="stat-card-bar"></div>
          </div>
        </RouterLink>
      </el-col>
    </el-row>

    <!-- Charts Row -->
    <el-row :gutter="20" class="charts-row">
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">按公网/私网分布</span>
            </div>
          </template>
          <div v-if="Object.keys(stats.plane_by_scope).length === 0" class="empty-state">
            <el-icon :size="40" color="#d1d5db"><Coin /></el-icon>
            <p>暂无数据</p>
          </div>
          <div v-else class="status-list">
            <div v-for="(count, scope) in stats.plane_by_scope" :key="scope" class="status-bar-row">
              <div class="status-bar-label">
                <el-tag :type="scope === '私网' ? 'success' : 'warning'" size="small" effect="plain">{{ scope }}</el-tag>
                <span class="status-count">{{ count }}</span>
              </div>
              <el-progress
                :percentage="calcPercent(count, stats.total_region_planes)"
                :color="scope === '私网' ? '#34a853' : '#fbbc04'"
                :stroke-width="8"
                :show-text="false"
                class="status-progress"
              />
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">按区域分布</span>
            </div>
          </template>
          <div v-if="stats.plane_by_region.length === 0" class="empty-state">
            <el-icon :size="40" color="#d1d5db"><MapLocation /></el-icon>
            <p>暂无数据</p>
          </div>
          <div v-else class="region-chart">
            <div v-for="item in stats.plane_by_region" :key="item.region_name" class="region-bar-row">
              <div class="region-bar-label">
                <span class="region-name">{{ item.region_name }}</span>
                <span class="region-count">{{ item.count }}</span>
              </div>
              <el-progress
                :percentage="calcPercent(item.count, stats.total_region_planes)"
                color="var(--color-primary)"
                :stroke-width="8"
                :show-text="false"
                class="region-progress"
              />
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Recent Changes -->
    <el-card shadow="never" class="recent-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">最近变更</span>
          <el-button size="small" text type="primary" @click="$router.push('/change-logs')">查看全部</el-button>
        </div>
      </template>
      <el-table :data="stats.recent_changes" stripe style="width: 100%" v-loading="loading" empty-text="暂无变更记录">
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="entity_type" label="类型" width="130">
          <template #default="{ row }">
            {{ entityLabel(row.entity_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="action" label="操作" width="80">
          <template #default="{ row }">
            <el-tag :type="actionTag(row.action)" size="small" effect="plain">{{ actionLabel(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="operator" label="操作者" width="100" />
        <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { fetchStats } from '@/api/excel'
import { Coin, MapLocation, Monitor, Connection as ConnectionIcon, Document } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/time'

const loading = ref(false)
const stats = ref({
  total_regions: 0,
  total_plane_types: 0,
  total_region_planes: 0,
  total_change_logs: 0,
  plane_by_scope: {},
  plane_by_region: [],
  recent_changes: [],
})

const statCards = [
  {
    key: 'total_regions',
    label: '区域总数',
    to: '/regions',
    icon: Monitor,
    gradient: 'linear-gradient(135deg, #1a73e8 0%, #4a90d9 100%)',
    accent: '#1a73e8',
  },
  {
    key: 'total_plane_types',
    label: '网络平面类型',
    to: '/plane-types',
    icon: ConnectionIcon,
    gradient: 'linear-gradient(135deg, #34a853 0%, #66bb6a 100%)',
    accent: '#34a853',
  },
  {
    key: 'total_region_planes',
    label: '网段总数',
    to: '/lookup',
    icon: Coin,
    gradient: 'linear-gradient(135deg, #f57c00 0%, #ffb74d 100%)',
    accent: '#f57c00',
  },
  {
    key: 'total_change_logs',
    label: '变更总数',
    to: '/change-logs',
    icon: Document,
    gradient: 'linear-gradient(135deg, #7c4dff 0%, #b388ff 100%)',
    accent: '#7c4dff',
  },
]

function calcPercent(value, total) {
  if (!total) return 0
  return Math.round((value / total) * 100)
}

function entityLabel(t) {
  const map = { region: '区域', network_plane_type: '网络平面类型', region_network_plane: '区域网络平面' }
  return map[t] || t
}

function actionTag(a) {
  const map = { create: 'success', update: 'warning', delete: 'danger', import: 'primary' }
  return map[a] || 'info'
}

function actionLabel(a) {
  const map = { create: '创建', update: '更新', delete: '删除', import: '导入' }
  return map[a] || a
}

onMounted(async () => {
  loading.value = true
  try {
    stats.value = await fetchStats()
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.dashboard {
  max-width: 1200px;
}

/* ---- Page Heading ---- */
.page-heading {
  margin-bottom: var(--spacing-lg);
}
.page-title {
  font-size: var(--font-size-xl);
  font-weight: 700;
  color: var(--color-text-primary);
  margin: 0;
}
.page-desc {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

/* ---- Stat Cards ---- */
.stat-row {
  margin-bottom: var(--spacing-lg);
}

.stat-card-link {
  display: block;
  color: inherit;
  text-decoration: none;
}

.stat-card-link:focus-visible {
  outline: 3px solid rgba(26, 115, 232, 0.35);
  outline-offset: 3px;
  border-radius: var(--radius-lg);
}

.stat-card {
  position: relative;
  background: var(--card-gradient);
  border-radius: var(--radius-lg);
  padding: 20px;
  overflow: hidden;
  transition: transform var(--transition-base), box-shadow var(--transition-base);
  cursor: pointer;
}
.stat-card-link:hover .stat-card {
  transform: translateY(-3px);
  box-shadow: var(--shadow-lg);
}

.stat-card-body {
  display: flex;
  align-items: center;
  gap: 16px;
  position: relative;
  z-index: 1;
}

.stat-icon-wrap {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: var(--font-size-2xl);
  font-weight: 700;
  color: #fff;
  line-height: 1.2;
}

.stat-label {
  font-size: var(--font-size-sm);
  color: rgba(255, 255, 255, 0.8);
  margin-top: 2px;
}

.stat-card-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: rgba(0, 0, 0, 0.1);
}

/* ---- Charts Row ---- */
.charts-row {
  margin-bottom: var(--spacing-lg);
}

.chart-card {
  margin-bottom: var(--spacing-md);
  height: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
  position: relative;
  padding-left: 12px;
}
.card-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 2px;
  bottom: 2px;
  width: 3px;
  background: var(--color-primary);
  border-radius: 2px;
}

/* ---- Status Distribution ---- */
.status-list {
  padding: 4px 0;
}

.status-bar-row {
  margin-bottom: 16px;
}
.status-bar-row:last-child {
  margin-bottom: 0;
}

.status-bar-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.status-count {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text-primary);
}

/* ---- Region Distribution ---- */
.region-chart {
  padding: 4px 0;
}

.region-bar-row {
  margin-bottom: 16px;
}
.region-bar-row:last-child {
  margin-bottom: 0;
}

.region-bar-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.region-name {
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  font-weight: 500;
}

.region-count {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-primary);
}

/* ---- Empty State ---- */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 0;
  gap: 8px;
  color: var(--color-text-tertiary);
}

/* ---- Recent Changes ---- */
.recent-card {
  margin-top: 0;
}
</style>
