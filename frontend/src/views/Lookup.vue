<template>
  <div>
    <div class="page-heading">
      <div>
        <h2 class="page-title">IP 查找</h2>
        <p class="page-desc">按 IP 地址或 CIDR 地址段快速检索所属 Region 和网络平面</p>
      </div>
    </div>

    <el-card shadow="never" class="search-card">
      <el-form :inline="true" @submit.prevent="handleSearch">
        <el-form-item label="IP / CIDR">
          <el-input
            v-model="query"
            placeholder="例如: 10.0.0.5 或 10.0.0.0/24"
            style="width: 300px"
            clearable
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="匹配模式">
          <el-radio-group v-model="exact" size="default">
            <el-radio-button :value="true">精确匹配</el-radio-button>
            <el-radio-button :value="false">包含匹配</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch" :loading="searching" :icon="Search">查找</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Results -->
    <el-card shadow="never" v-if="searched">
      <template #header>
        <div class="card-header">
          <span class="card-title">查找结果</span>
          <el-tag size="small" effect="plain" type="info">共 {{ total }} 条匹配</el-tag>
        </div>
      </template>
      <el-table
        class="lookup-results-table"
        :data="results"
        row-key="id"
        default-expand-all
        :tree-props="{ children: 'children' }"
        stripe
        border
        v-loading="searching"
        empty-text="未找到匹配的网络平面"
        table-layout="auto"
        :fit="false"
        scrollbar-always-on
        show-overflow-tooltip
      >
        <el-table-column prop="cidr" label="CIDR" min-width="300">
          <template #default="{ row }">
            <span class="cidr-cell">
              <span class="plane-address-text">{{ row.cidr }}</span>
              <el-tag v-if="row.is_match" size="small" type="success" effect="plain">命中</el-tag>
              <el-tag v-else size="small" type="info" effect="plain">上下文</el-tag>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="plane_type_name" label="网络平面" min-width="160" show-overflow-tooltip />
        <el-table-column prop="scope" label="作用域" width="110" />
        <el-table-column prop="vlan_id" label="VLAN ID" width="90" align="center" />
        <el-table-column prop="gateway_ip" label="网关IP" width="140" show-overflow-tooltip />
        <el-table-column prop="gateway_position" label="网关位置" min-width="180" show-overflow-tooltip />
        <el-table-column prop="region_name" label="所属 Region" width="160" show-overflow-tooltip />
      </el-table>
    </el-card>

    <!-- Empty state -->
    <el-empty v-else-if="!searching" :image-size="100" class="search-hint">
      <template #description>
        <span style="color: var(--color-text-tertiary)">输入 IP 或 CIDR 开始搜索</span>
      </template>
    </el-empty>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { lookupIP } from '@/api/lookup'
import { Search } from '@element-plus/icons-vue'

const query = ref('')
const exact = ref(true)
const searching = ref(false)
const searched = ref(false)
const results = ref([])
const total = ref(0)

async function handleSearch() {
  if (!query.value.trim()) return
  searching.value = true
  searched.value = true
  try {
    const res = await lookupIP(query.value.trim(), exact.value)
    results.value = res.results || []
    total.value = res.total || 0
  } catch (e) {
    results.value = []
    total.value = 0
  } finally {
    searching.value = false
  }
}
</script>

<style scoped>
.page-heading { margin-bottom: var(--spacing-lg); }
.page-title { font-size: var(--font-size-xl); font-weight: 700; color: var(--color-text-primary); margin: 0; }
.page-desc { font-size: var(--font-size-sm); color: var(--color-text-tertiary); margin-top: 4px; }
.search-card { margin-bottom: var(--spacing-md); }
.card-header { display: flex; align-items: center; justify-content: space-between; }
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
.cidr-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
}
.plane-address-text {
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
}
.cidr-cell :deep(.el-tag) {
  flex: 0 0 auto;
}
.lookup-results-table :deep(.cell) {
  overflow: hidden;
  text-overflow: clip;
  white-space: nowrap;
}
.search-hint { margin-top: 40px; }
</style>
