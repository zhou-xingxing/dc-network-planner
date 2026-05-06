<template>
  <div>
    <div class="page-heading">
      <div>
        <h2 class="page-title">变更历史</h2>
        <p class="page-desc">所有数据操作的完整审计日志，支持多维度筛选</p>
      </div>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filters" label-width="80px">
        <el-form-item label="实体类型">
          <el-select v-model="filters.entity_type" placeholder="全部" clearable style="width: 150px">
            <el-option label="Region" value="region" />
            <el-option label="网络平面类型" value="network_plane_type" />
            <el-option label="Region 网络平面" value="region_network_plane" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作类型">
          <el-select v-model="filters.action" placeholder="全部" clearable style="width: 120px">
            <el-option label="创建" value="create" />
            <el-option label="更新" value="update" />
            <el-option label="删除" value="delete" />
            <el-option label="导入" value="import" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作者">
          <el-input v-model="filters.operator" placeholder="操作者" style="width: 150px" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchData" :icon="Search">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table :data="items" stripe v-loading="loading" empty-text="暂无变更记录" :max-height="600">
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="entity_type" label="实体类型" width="130">
          <template #default="{ row }">
            {{ entityTypeLabel(row.entity_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="action" label="操作" width="80">
          <template #default="{ row }">
            <el-tag :type="actionTag(row.action)" size="small" effect="plain">{{ actionLabel(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="operator" label="操作者" width="100" />
        <el-table-column prop="field_name" label="字段" width="100" />
        <el-table-column prop="old_value" label="旧值" min-width="200" show-overflow-tooltip />
        <el-table-column prop="new_value" label="新值" min-width="200" show-overflow-tooltip />
        <el-table-column prop="comment" label="备注" width="120" show-overflow-tooltip />
      </el-table>
      <el-pagination
        v-if="total > 0"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end"
        @current-change="fetchData"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { fetchChangeLogs } from '@/api/excel'
import { Search } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/time'

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filters = reactive({
  entity_type: '',
  action: '',
  operator: '',
})

function entityTypeLabel(t) {
  const map = { region: 'Region', network_plane_type: '网络平面类型', region_network_plane: 'Region 网络平面' }
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

async function fetchData() {
  loading.value = true
  try {
    const params = { skip: (page.value - 1) * pageSize.value, limit: pageSize.value }
    if (filters.entity_type) params.entity_type = filters.entity_type
    if (filters.action) params.action = filters.action
    if (filters.operator) params.operator = filters.operator
    const res = await fetchChangeLogs(params)
    items.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.entity_type = ''
  filters.action = ''
  filters.operator = ''
  page.value = 1
  fetchData()
}

onMounted(fetchData)
</script>

<style scoped>
.page-heading { margin-bottom: var(--spacing-lg); }
.page-title { font-size: var(--font-size-xl); font-weight: 700; color: var(--color-text-primary); margin: 0; }
.page-desc { font-size: var(--font-size-sm); color: var(--color-text-tertiary); margin-top: 4px; }
.filter-card { margin-bottom: var(--spacing-md); }
</style>
