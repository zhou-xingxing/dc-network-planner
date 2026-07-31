<template>
  <div>
    <div class="page-heading">
      <div>
        <h2 class="page-title">机柜管理</h2>
        <p class="page-desc">按机房和机柜列聚合 Region 内的机柜，快速查看资源分布与使用情况</p>
      </div>
      <div v-if="canManageSelectedRegion" class="page-actions">
        <el-button
          class="rack-create-button"
          type="primary"
          :icon="Plus"
          :disabled="!selectedRegionId"
          @click="openCreatePage"
        >
          添加机柜
        </el-button>
      </div>
    </div>

    <el-card shadow="never" class="filter-card">
      <div class="filter-row">
        <div class="filter-field region-filter">
          <span class="filter-label">Region</span>
          <el-select v-model="selectedRegionId" placeholder="请选择 Region" filterable @change="handleRegionChange">
            <el-option v-for="region in regions" :key="region.id" :label="region.name" :value="region.id" />
          </el-select>
        </div>
        <div class="filter-field search-filter">
          <span class="filter-label">机柜名称</span>
          <el-input
            v-model="search"
            clearable
            placeholder="输入名称搜索"
            :prefix-icon="Search"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
        </div>
        <el-button :disabled="!selectedRegionId" @click="handleSearch">查询</el-button>
      </div>
    </el-card>

    <el-alert
      v-if="selectedRegionId && !canManageSelectedRegion"
      class="permission-alert"
      type="info"
      :closable="false"
      show-icon
      title="当前 Region 为只读模式；只有获得该 Region 授权的普通用户可修改机柜。"
    />

    <div class="summary-grid" aria-label="机柜资源汇总">
      <div class="summary-item">
        <span>机柜列</span>
        <strong>{{ totalColumns }}</strong>
      </div>
      <div class="summary-item">
        <span>机柜总数</span>
        <strong>{{ totalRacks }}</strong>
      </div>
      <div class="summary-guide">
        <el-icon><Grid /></el-icon>
        <strong>按列浏览</strong>
      </div>
    </div>

    <el-card shadow="never" class="groups-card" v-loading="loading">
      <el-empty
        v-if="!loading && columnGroups.length === 0"
        :image-size="80"
        :description="selectedRegionId ? '暂无机柜' : '请先选择 Region'"
      />
      <el-collapse v-else v-model="expandedGroupKeys" class="rack-groups" @change="handleExpandChange">
        <el-collapse-item v-for="group in columnGroups" :key="groupKey(group)" :name="groupKey(group)">
          <template #title>
            <div class="group-header">
              <span class="group-marker">{{ group.rack_column }}</span>
              <div class="group-identity">
                <strong>{{ group.room_name }} 机房</strong>
                <span>{{ group.rack_column }} 列</span>
              </div>
              <div class="group-stats">
                <span><strong>{{ group.rack_count }}</strong> 个机柜</span>
                <span><strong>{{ group.switch_count }}</strong> 台交换机</span>
                <span><strong>{{ group.cable_count }}</strong> 条线缆</span>
              </div>
            </div>
          </template>

          <div class="group-content" v-loading="groupState(group).loading">
            <el-table :data="groupState(group).racks" stripe border empty-text="暂无匹配机柜">
              <el-table-column label="机柜编号" width="90" align="center">
                <template #default="{ row }">
                  <span class="rack-number">{{ String(row.rack_number).padStart(2, '0') }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="name" label="机柜名称" min-width="210">
                <template #default="{ row }">
                  <div class="rack-name-cell">
                    <span class="rack-marker">{{ rackInitial(row.name) }}</span>
                    <strong>{{ row.name }}</strong>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="u_height" label="总 U 数" width="110" align="center">
                <template #default="{ row }"><el-tag effect="plain">{{ row.u_height }}U</el-tag></template>
              </el-table-column>
              <el-table-column prop="switch_count" label="交换机数量" width="120" align="center">
                <template #default="{ row }"><span class="count-value">{{ row.switch_count }}</span></template>
              </el-table-column>
              <el-table-column prop="cable_count" width="125" align="center">
                <template #header>
                  <span class="column-title-with-tip">
                    线缆数量
                    <el-tooltip content="仅统计服务器侧位于该机柜的线缆数量" placement="top">
                      <el-icon class="column-tip-icon" tabindex="0" aria-label="查看线缆数量统计说明">
                        <InfoFilled />
                      </el-icon>
                    </el-tooltip>
                  </span>
                </template>
                <template #default="{ row }"><span class="count-value">{{ row.cable_count }}</span></template>
              </el-table-column>
              <el-table-column prop="updated_at" label="更新时间" width="175">
                <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
              </el-table-column>
              <el-table-column v-if="canManageSelectedRegion" label="操作" width="150" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" type="warning" link @click="openEditDialog(row)">编辑</el-button>
                  <el-button size="small" type="danger" link @click="handleDelete(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-pagination
              v-if="groupState(group).total > groupState(group).pageSize"
              :current-page="groupState(group).page"
              :page-size="groupState(group).pageSize"
              :total="groupState(group).total"
              layout="total, prev, pager, next"
              class="inner-pagination"
              @current-change="handleGroupPage(group, $event)"
            />
          </div>
        </el-collapse-item>
      </el-collapse>

      <el-pagination
        v-if="totalColumns > columnPageSize"
        v-model:current-page="columnPage"
        :page-size="columnPageSize"
        :total="totalColumns"
        layout="total, prev, pager, next"
        class="table-pagination"
        @current-change="fetchData"
      />
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      title="编辑机柜"
      width="540px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div class="dialog-context">
        <span>Region</span>
        <strong>{{ selectedRegionName || '-' }}</strong>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="机房名" prop="room_name">
          <el-input v-model="form.room_name" maxlength="100" placeholder="例如：A1-403" />
        </el-form-item>
        <el-form-item label="机柜列" prop="rack_column">
          <el-input v-model="form.rack_column" maxlength="20" placeholder="例如：A" />
        </el-form-item>
        <el-form-item label="机柜编号" prop="rack_number">
          <el-input-number v-model="form.rack_number" :min="1" :step="1" controls-position="right" />
        </el-form-item>
        <el-form-item label="最终名称">
          <el-input :model-value="editNamePreview" disabled />
        </el-form-item>
        <el-form-item label="总 U 数" prop="u_height">
          <el-input-number
            v-model="form.u_height"
            class="rack-height-input"
            :min="1"
            :step="1"
            controls-position="right"
          />
          <span class="field-hint">常见机柜为 42U 或 48U</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="submitting" @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Grid, InfoFilled, Plus, Search } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { deleteRack, fetchRackColumns, fetchRacks, updateRack } from '@/api/racks'
import { fetchRegions } from '@/api/regions'
import { useAppStore } from '@/stores/app'
import type { EntityId, Rack, RackColumnSummary, Region } from '@/types'
import { formatDateTime } from '@/utils/time'

interface RackGroupState {
  racks: Rack[]
  total: number
  page: number
  pageSize: number
  loading: boolean
}

interface RackEditForm {
  room_name: string
  rack_column: string
  rack_number: number
  u_height: number
}

const appStore = useAppStore()
const route = useRoute()
const router = useRouter()
const regions = ref<Region[]>([])
const selectedRegionId = ref<EntityId>('')
const search = ref('')
const columnGroups = ref<RackColumnSummary[]>([])
const loading = ref(false)
const totalColumns = ref(0)
const totalRacks = ref(0)
const columnPage = ref(1)
const columnPageSize = 20
const expandedGroupKeys = ref<string[]>([])
const groupStates = reactive<Record<string, RackGroupState>>({})
const dialogVisible = ref(false)
const submitting = ref(false)
const editingRack = ref<Rack | null>(null)
const formRef = ref<FormInstance>()
const form = ref<RackEditForm>({ room_name: '', rack_column: '', rack_number: 1, u_height: 42 })
let columnRequestVersion = 0

const selectedRegionName = computed(
  () => regions.value.find((region) => region.id === selectedRegionId.value)?.name || ''
)
const canManageSelectedRegion = computed(
  () => Boolean(selectedRegionId.value) && appStore.canManageRegionBusiness(selectedRegionId.value)
)
const editNamePreview = computed(() => {
  if (!form.value.room_name || !form.value.rack_column || form.value.rack_number < 1) return ''
  return `${form.value.room_name}-${form.value.rack_column}${String(form.value.rack_number).padStart(2, '0')}`
})
const rules: FormRules<RackEditForm> = {
  room_name: [{ required: true, message: '请输入机房名', trigger: 'blur' }],
  rack_column: [{ required: true, message: '请输入机柜列', trigger: 'blur' }],
  rack_number: [{ required: true, message: '请输入机柜编号', trigger: 'change' }],
  u_height: [{ required: true, message: '请输入机柜总 U 数', trigger: 'change' }],
}

async function initialize() {
  const response = await fetchRegions({ skip: 0, limit: 500 })
  regions.value = response.items
  const requestedRegionId = typeof route.query.region_id === 'string' ? route.query.region_id : ''
  const preferredRegion =
    regions.value.find(
      (region) => region.id === requestedRegionId && appStore.canManageRegionBusiness(region.id)
    ) || regions.value.find((region) => appStore.canManageRegionBusiness(region.id)) || regions.value[0]
  selectedRegionId.value = preferredRegion?.id || ''
  await fetchData()
}

async function fetchData() {
  const requestVersion = ++columnRequestVersion
  const regionId = selectedRegionId.value
  const searchTerm = search.value.trim() || undefined
  expandedGroupKeys.value = []
  columnGroups.value = []
  totalColumns.value = 0
  totalRacks.value = 0
  clearGroupStates()
  loading.value = Boolean(regionId)
  if (!regionId) return

  try {
    const response = await fetchRackColumns(regionId, {
      skip: (columnPage.value - 1) * columnPageSize,
      limit: columnPageSize,
      search: searchTerm,
    })
    if (requestVersion !== columnRequestVersion || selectedRegionId.value !== regionId) return

    for (const group of response.items) {
      groupStates[groupKey(group)] = emptyGroupState()
    }
    columnGroups.value = response.items
    totalColumns.value = response.total_columns
    totalRacks.value = response.total_racks
  } finally {
    if (requestVersion === columnRequestVersion) loading.value = false
  }
}

function handleRegionChange() {
  columnPage.value = 1
  fetchData()
}

function handleSearch() {
  columnPage.value = 1
  fetchData()
}

function openCreatePage() {
  router.push({ path: '/switch-cabling/racks/create', query: { region_id: selectedRegionId.value } })
}

function groupKey(group: RackColumnSummary) {
  return `${encodeURIComponent(group.room_name)}::${encodeURIComponent(group.rack_column)}`
}

function emptyGroupState(): RackGroupState {
  return { racks: [], total: 0, page: 1, pageSize: 20, loading: false }
}

function groupState(group: RackColumnSummary): RackGroupState {
  return groupStates[groupKey(group)]
}

function clearGroupStates() {
  for (const key of Object.keys(groupStates)) delete groupStates[key]
}

async function handleExpandChange(activeNames: string | string[]) {
  const names = Array.isArray(activeNames) ? activeNames : [activeNames]
  const pending = columnGroups.value.filter((group) => {
    const key = groupKey(group)
    return names.includes(key) && groupState(group).racks.length === 0
  })
  await Promise.all(pending.map((group) => fetchGroupRacks(group)))
}

async function fetchGroupRacks(group: RackColumnSummary) {
  const key = groupKey(group)
  const state = groupState(group)
  const regionId = selectedRegionId.value
  const searchTerm = search.value.trim() || undefined
  state.loading = true
  try {
    const response = await fetchRacks(regionId, {
      skip: (state.page - 1) * state.pageSize,
      limit: state.pageSize,
      search: searchTerm,
      room_name: group.room_name,
      rack_column: group.rack_column,
    })
    if (selectedRegionId.value !== regionId || groupStates[key] !== state) return

    state.racks = response.items
    state.total = response.total
  } finally {
    if (groupStates[key] === state) state.loading = false
  }
}

async function handleGroupPage(group: RackColumnSummary, page: number) {
  groupState(group).page = page
  await fetchGroupRacks(group)
}

function openEditDialog(rack: Rack) {
  editingRack.value = rack
  form.value = {
    room_name: rack.room_name,
    rack_column: rack.rack_column,
    rack_number: rack.rack_number,
    u_height: rack.u_height,
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid || !selectedRegionId.value || !editingRack.value) return
  submitting.value = true
  try {
    await updateRack(selectedRegionId.value, editingRack.value.id, form.value)
    ElMessage.success('机柜已更新')
    dialogVisible.value = false
    await fetchData()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(rack: Rack) {
  if (rack.switch_count || rack.cable_count) {
    ElMessage.warning(
      `机柜 ${rack.name} 仍有 ${rack.switch_count} 台交换机、${rack.cable_count} 条线缆引用，不能删除`
    )
    return
  }
  try {
    await ElMessageBox.confirm(`确定删除机柜“${rack.name}”吗？`, '删除机柜', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  await deleteRack(selectedRegionId.value, rack.id)
  ElMessage.success('机柜已删除')
  if (columnGroups.value.length === 1 && columnPage.value > 1) columnPage.value -= 1
  await fetchData()
}

function rackInitial(name: string) {
  return name.trim().slice(0, 2).toUpperCase() || 'RK'
}

onMounted(initialize)
</script>

<style scoped>
.page-heading { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: var(--spacing-lg); }
.page-title { margin: 0; color: var(--color-text-primary); font-size: var(--font-size-xl); font-weight: 700; }
.page-desc { margin-top: 4px; color: var(--color-text-tertiary); font-size: var(--font-size-sm); }
.page-actions { display: flex; align-items: center; gap: 8px; }
.rack-create-button :deep(*) { pointer-events: none; }
.filter-card { margin-bottom: var(--spacing-md); }
.filter-row { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; }
.filter-field { display: flex; flex-direction: column; gap: 6px; }
.filter-label { color: var(--color-text-secondary); font-size: var(--font-size-xs); font-weight: 600; }
.region-filter { width: 260px; }
.search-filter { width: 280px; }
.permission-alert { margin-bottom: var(--spacing-md); }
.summary-grid { display: grid; grid-template-columns: 180px 180px minmax(300px, 1fr); gap: 12px; margin-bottom: var(--spacing-md); }
.summary-item, .summary-guide { min-height: 88px; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: #fff; }
.summary-item { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 16px; }
.summary-item > span { color: var(--color-text-secondary); font-size: var(--font-size-xs); font-weight: 600; }
.summary-item > strong { color: var(--color-primary); font-size: 28px; font-variant-numeric: tabular-nums; line-height: 1; }
.summary-guide { display: flex; align-items: center; gap: 12px; padding: 14px 18px; background: linear-gradient(135deg, #f8fbff, #f3f7fd); }
.summary-guide > .el-icon { flex: 0 0 auto; width: 38px; height: 38px; border-radius: 9px; background: #e7f0fd; color: var(--color-primary); font-size: 20px; }
.summary-guide strong { color: var(--color-text-primary); font-size: var(--font-size-sm); }
.groups-card { min-height: 180px; }
.rack-groups { border-top: 0; }
.rack-groups :deep(.el-collapse-item__header) { min-height: 72px; height: auto; padding: 10px 14px; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: #fff; line-height: normal; }
.rack-groups :deep(.el-collapse-item + .el-collapse-item) { margin-top: 10px; }
.rack-groups :deep(.el-collapse-item__wrap) { border-bottom: 0; }
.rack-groups :deep(.el-collapse-item__content) { padding: 10px 0 4px; }
.rack-groups :deep(.el-collapse-item.is-active .el-collapse-item__header) { border-color: #b9d1f5; background: #f8fbff; }
.group-header { display: flex; width: 100%; min-width: 0; align-items: center; gap: 12px; padding-right: 12px; }
.group-marker { display: inline-flex; width: 42px; height: 42px; flex: 0 0 auto; align-items: center; justify-content: center; border: 1px solid #c9dcf7; border-radius: 9px; background: #edf4fe; color: var(--color-primary-dark); font-size: var(--font-size-md); font-weight: 800; }
.group-identity { display: flex; min-width: 150px; flex-direction: column; gap: 4px; }
.group-identity strong { color: var(--color-text-primary); font-size: var(--font-size-sm); }
.group-identity span { color: var(--color-text-tertiary); font-size: var(--font-size-sm); }
.group-stats { display: flex; margin-left: auto; align-items: center; gap: 24px; color: var(--color-text-tertiary); font-size: var(--font-size-xs); }
.group-stats span { white-space: nowrap; }
.group-stats strong { margin-right: 3px; color: var(--color-text-primary); font-size: var(--font-size-sm); font-variant-numeric: tabular-nums; }
.group-content { min-height: 72px; padding: 0 2px 8px 54px; }
.rack-number { color: var(--color-primary-dark); font-variant-numeric: tabular-nums; font-weight: 700; }
.rack-name-cell { display: flex; align-items: center; gap: 10px; }
.rack-marker { display: inline-flex; width: 34px; height: 28px; align-items: center; justify-content: center; border: 1px solid #d7e5fb; border-radius: 6px; background: #f3f7fd; color: var(--color-primary-dark); font-size: 11px; font-weight: 700; letter-spacing: .4px; }
.count-value { color: var(--color-text-secondary); font-variant-numeric: tabular-nums; font-weight: 600; }
.column-title-with-tip { display: inline-flex; align-items: center; gap: 4px; }
.column-tip-icon { color: var(--color-text-tertiary); cursor: help; font-size: 14px; outline: none; }
.column-tip-icon:hover, .column-tip-icon:focus-visible { color: var(--color-primary); }
.table-pagination, .inner-pagination { margin-top: 16px; justify-content: flex-end; }
.dialog-context { display: flex; justify-content: space-between; margin: -4px 0 20px; padding: 10px 14px; border: 1px solid var(--color-border); border-radius: var(--radius-md); background: #f8fafc; color: var(--color-text-secondary); font-size: var(--font-size-sm); }
.dialog-context strong { color: var(--color-text-primary); }
.rack-height-input :deep(.el-input__inner) { text-align: left; }
.field-hint { margin-left: 10px; color: var(--color-text-tertiary); font-size: var(--font-size-xs); }
@media (max-width: 900px) {
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .summary-guide { grid-column: 1 / -1; }
  .group-stats { gap: 10px; }
}
@media (max-width: 760px) {
  .page-heading { gap: 16px; }
  .filter-field, .region-filter, .search-filter { width: 100%; }
  .summary-grid { grid-template-columns: 1fr 1fr; }
  .group-header { align-items: flex-start; flex-wrap: wrap; }
  .group-stats { width: 100%; margin-left: 54px; justify-content: space-between; }
  .group-content { padding-left: 0; }
}
</style>
