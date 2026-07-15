<template>
  <div>
    <div class="page-heading">
      <div>
        <h2 class="page-title">导入 / 导出</h2>
        <p class="page-desc">通过 Excel 批量导入 Region 网络平面数据，或按 Region 导出为 Excel</p>
      </div>
    </div>

    <el-card shadow="never">
      <el-tabs v-model="activeTab" class="app-tabs">
        <el-tab-pane label="导入 Excel" name="import">
          <div class="permission-strip" :class="{ 'is-warning': importPermissionTip }">
            <div class="permission-main">
              <el-tag size="small" effect="plain">权限</el-tag>
              <span>{{ importPermissionMainText }}</span>
            </div>
            <span v-if="importPermissionTip" class="permission-note">{{ importPermissionTip }}</span>
          </div>

          <div class="import-actions">
            <div class="action-panel">
              <div class="action-index">01</div>
              <div class="action-body">
                <div class="action-title">下载模板</div>
                <p class="action-desc">按模板填写 Region 网络平面数据。</p>
                <div class="action-control">
                  <el-button class="template-button" :icon="Download" @click="downloadTemplate" :loading="downloading">
                    下载导入模板
                  </el-button>
                </div>
              </div>
            </div>

            <div class="action-panel action-panel-wide">
              <div class="action-index">02</div>
              <div class="action-body">
                <div class="action-title">上传并预览</div>
                <p class="action-desc">预览会提前标记无权限 Region 和格式错误。</p>
                <div class="upload-control">
                  <el-upload
                    ref="uploadRef"
                    action="#"
                    :auto-upload="false"
                    :show-file-list="false"
                    :limit="1"
                    accept=".xlsx"
                    :on-change="onFileChange"
                    :disabled="!canPreviewImport"
                    class="upload-area"
                  >
                    <template #trigger>
                      <el-button class="choose-file-button" type="primary" plain :icon="Upload" :disabled="!canPreviewImport">
                        选择文件
                      </el-button>
                    </template>
                  </el-upload>
                  <el-button
                    class="preview-button"
                    type="primary"
                    @click="previewUpload"
                    :loading="previewLoading"
                    :disabled="!selectedFile || !canPreviewImport"
                  >
                    预览
                  </el-button>
                </div>
                <div class="upload-tip">
                  {{ selectedFile?.name || '未选择文件' }}；单次最多导入 {{ IMPORT_MAX_ROWS }} 条数据，仅支持 .xlsx 文件
                </div>
              </div>
            </div>
          </div>

          <!-- 预览结果 -->
          <div v-if="previewData && !importResult" class="preview-panel">
            <div class="result-header">
              <div>
                <div class="result-title">预览结果</div>
                <p class="result-desc">确认前请检查有效行、错误行和涉及 Region。</p>
              </div>
              <div class="result-metrics">
                <div class="metric-item">
                  <span class="metric-value">{{ previewData.total_rows }}</span>
                  <span class="metric-label">总行数</span>
                </div>
                <div class="metric-item is-success">
                  <span class="metric-value">{{ previewData.valid_rows }}</span>
                  <span class="metric-label">可导入</span>
                </div>
                <div class="metric-item" :class="{ 'is-danger': previewData.error_rows.length > 0 }">
                  <span class="metric-value">{{ previewData.error_rows.length }}</span>
                  <span class="metric-label">错误</span>
                </div>
              </div>
            </div>
            <div v-if="involvedRegions.length > 0" class="region-summary">
              <span class="region-summary-label">涉及 Region</span>
              <el-tag
                v-for="region in involvedRegions"
                :key="region.name"
                :type="region.tagType"
                effect="plain"
                size="small"
              >
                {{ region.name }} · {{ region.label }}
              </el-tag>
            </div>
            <div v-if="previewData.error_rows.length > 0" style="margin-bottom: 16px">
              <h4 class="sub-title">错误详情：</h4>
              <el-table :data="previewData.error_rows" stripe border size="small">
                <el-table-column prop="row" label="行号" width="80" />
                <el-table-column prop="region_name" label="Region" width="130">
                  <template #default="{ row }">{{ row.region_name || '-' }}</template>
                </el-table-column>
                <el-table-column label="类型" width="100" align="center">
                  <template #default="{ row }">
                    <el-tag :type="errorTypeMeta(row.error_type).tagType" size="small" effect="plain">
                      {{ errorTypeMeta(row.error_type).label }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="errors" label="错误" min-width="300">
                  <template #default="{ row }">
                    <el-tag
                      v-for="err in row.errors"
                      :key="err"
                      :type="errorTypeMeta(row.error_type).tagType"
                      size="small"
                      style="margin: 2px"
                    >
                      {{ err }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <h4 class="sub-title">数据预览（仅显示有效行）：</h4>
            <div style="max-height: 400px; overflow-y: auto; margin-bottom: 16px">
              <el-table :data="previewData.rows" stripe border size="small">
                <el-table-column prop="row_number" label="行" width="50" />
                <el-table-column prop="region_name" label="Region" width="120" />
                <el-table-column prop="plane_type_name" label="网络平面" width="120" />
                <el-table-column prop="scope" label="作用域" width="110" />
                <el-table-column prop="ip_range" label="CIDR" width="140" />
                <el-table-column prop="vlan_id" label="VLAN" width="80" />
                <el-table-column prop="gateway_position" label="网关位置" min-width="140" show-overflow-tooltip />
                <el-table-column prop="gateway_ip" label="网关IP" width="140" />
              </el-table>
            </div>
            <el-tooltip :disabled="!confirmImportDisabledTip" :content="confirmImportDisabledTip" placement="top">
              <span>
                <el-button
                  type="success"
                  size="large"
                  @click="confirmImport"
                  :loading="importing"
                  :disabled="confirmImportDisabled"
                >
                  确认导入 ({{ previewData.valid_rows }} 条)
                </el-button>
              </span>
            </el-tooltip>
          </div>

          <!-- 最终导入结果 -->
          <section v-if="importResult" class="final-result-panel">
            <div class="final-result-header">
              <div class="final-result-heading">
                <el-icon class="final-result-icon" :class="importResult.success ? 'is-success' : 'is-warning'">
                  <CircleCheckFilled v-if="importResult.success" />
                  <WarningFilled v-else />
                </el-icon>
                <div>
                  <div class="result-title">{{ importResultTitle }}</div>
                  <p class="result-desc">{{ importResultDescription }}</p>
                </div>
              </div>
              <div class="result-metrics final-result-metrics">
                <div class="metric-item">
                  <span class="metric-value">{{ importResult.row_results.length }}</span>
                  <span class="metric-label">确认行数</span>
                </div>
                <div class="metric-item is-success">
                  <span class="metric-value">{{ importResult.imported_count }}</span>
                  <span class="metric-label">成功</span>
                </div>
                <div class="metric-item" :class="{ 'is-danger': importResult.error_count > 0 }">
                  <span class="metric-value">{{ importResult.error_count }}</span>
                  <span class="metric-label">失败</span>
                </div>
              </div>
            </div>

            <el-alert
              v-if="importResult.row_results.length === 0"
              :title="sessionResultError || '本次确认没有可处理的数据'"
              type="error"
              :closable="false"
              show-icon
            />

            <template v-else>
              <div class="final-result-toolbar">
                <span class="final-result-table-title">逐行结果</span>
                <el-segmented v-model="resultFilter" :options="resultFilterOptions" size="small" />
              </div>
              <el-table :data="filteredRowResults" border stripe size="small" max-height="520" class="final-result-table">
                <el-table-column label="状态" width="76" fixed="left" align="center">
                  <template #default="{ row }">
                    <el-tag :type="row.status === 'success' ? 'success' : 'danger'" effect="plain" size="small">
                      {{ row.status === 'success' ? '成功' : '失败' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="row" label="Excel 行" width="76" align="center" />
                <el-table-column prop="region_name" label="Region" min-width="130" show-overflow-tooltip />
                <el-table-column label="网络平面 / 作用域" min-width="170">
                  <template #default="{ row }">
                    <div class="result-cell-primary">{{ row.plane_type_name }}</div>
                    <div class="result-cell-secondary">{{ row.scope }}</div>
                  </template>
                </el-table-column>
                <el-table-column label="CIDR / VLAN" width="155">
                  <template #default="{ row }">
                    <div class="result-cell-primary">{{ row.ip_range }}</div>
                    <div class="result-cell-secondary">VLAN {{ row.vlan_id ?? '-' }}</div>
                  </template>
                </el-table-column>
                <el-table-column label="最终结果" min-width="245">
                  <template #default="{ row }">
                    <span v-if="row.status === 'success'" class="row-result-message is-success">已创建网络平面</span>
                    <div v-else class="row-result-message is-failed">
                      <div v-for="error in row.errors" :key="error">{{ error }}</div>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </template>

            <div class="final-result-footer">
              <el-button type="primary" :icon="RefreshLeft" @click="resetImport">继续导入</el-button>
            </div>
          </section>
        </el-tab-pane>

        <el-tab-pane label="导出 Excel" name="export">
          <div class="export-panel">
            <div class="export-copy">
              <el-tag type="success" effect="plain" size="small">导出</el-tag>
              <div>
                <div class="action-title">导出网络平面明细</div>
                <p class="action-desc">按 Region 筛选；留空则导出全部可读数据。</p>
              </div>
            </div>
            <el-form :model="exportForm" label-width="80px" class="export-form">
              <el-form-item label="Region">
                <el-select v-model="exportForm.region_id" placeholder="全部 Region" clearable>
                  <el-option v-for="r in regions" :key="r.id" :label="r.name" :value="r.id" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="handleExport" :loading="exporting" :icon="Download">导出</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { downloadTemplate as downloadTemplateApi, previewImport, confirmImport as confirmImportApi, exportExcel } from '@/api/excel'
import { fetchRegions } from '@/api/regions'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { CircleCheckFilled, Download, RefreshLeft, Upload, WarningFilled } from '@element-plus/icons-vue'
import type {
  ExcelExportParams,
  ImportErrorType,
  ImportPreview,
  ImportResult,
  ImportRowResult,
  ImportRowStatus,
  Region,
} from '@/types'

interface InvolvedRegion {
  name: string
  label: string
  tagType: string
}

interface InvolvedRegionState {
  hasValid: boolean
  hasInvalid: boolean
  hasPermissionError: boolean
}

type ResultFilter = 'all' | ImportRowStatus
const IMPORT_MAX_ROWS = 1000

const appStore = useAppStore()
const canPreviewImport = computed(() => appStore.currentUser?.role !== 'administrator')
const canImport = computed(
  () => appStore.currentUser?.role === 'user' && (appStore.currentUser?.permitted_regions || []).length > 0
)
const importPermissionMainText = computed(() => {
  if (appStore.currentUser?.role === 'administrator') {
    return '管理员可下载模板和导出数据，不能上传或预览 Excel 导入文件。'
  }
  if ((appStore.currentUser?.permitted_regions || []).length === 0) {
    return '当前账号暂无可导入的授权 Region。'
  }
  return '仅可导入已获授权管理的 Region 数据。'
})
const importPermissionTip = computed(() => {
  if (appStore.currentUser?.role === 'administrator') {
    return 'Region 内业务数据导入仅限已授权普通用户。'
  }
  if ((appStore.currentUser?.permitted_regions || []).length === 0) {
    return '可下载模板、预览文件和导出数据。'
  }
  return ''
})
const activeTab = ref('import')

const downloading = ref(false)
const selectedFile = ref<File | null>(null)
const previewLoading = ref(false)
const previewData = ref<ImportPreview | null>(null)
const importing = ref(false)
const importResult = ref<ImportResult | null>(null)
const resultFilter = ref<ResultFilter>('all')
const uploadRef = ref()

const regions = ref<Region[]>([])
const exporting = ref(false)
const exportForm = ref<ExcelExportParams>({ region_id: '' })
const confirmImportDisabled = computed(() => (previewData.value?.valid_rows || 0) === 0 || !canImport.value)
const confirmImportDisabledTip = computed(() => {
  if (!previewData.value) return ''
  if (!canImport.value) return importPermissionTip.value
  if (previewData.value.valid_rows === 0) return '没有可确认导入的有效行'
  return ''
})
const resultFilterOptions = computed(() => [
  { label: `全部 ${importResult.value?.row_results.length || 0}`, value: 'all' },
  { label: `成功 ${importResult.value?.imported_count || 0}`, value: 'success' },
  { label: `失败 ${importResult.value?.error_count || 0}`, value: 'failed' },
])
const filteredRowResults = computed<ImportRowResult[]>(() => {
  const rows = importResult.value?.row_results || []
  if (resultFilter.value === 'all') return rows
  return rows.filter((row) => row.status === resultFilter.value)
})
const importResultTitle = computed(() => {
  if (!importResult.value?.row_results.length) return '导入未完成'
  if (importResult.value.error_count === 0) return '全部导入成功'
  if (importResult.value.imported_count === 0) return '全部导入失败'
  return '部分数据导入成功'
})
const importResultDescription = computed(() => {
  if (!importResult.value?.row_results.length) return '请根据提示重新上传并确认导入。'
  if (importResult.value.error_count === 0) return '所有确认行均已写入系统。'
  return '成功行已写入系统，失败行未写入；请查看逐行结果和失败原因。'
})
const sessionResultError = computed(() =>
  (importResult.value?.errors || []).flatMap((item) => item.errors).join('；')
)
const involvedRegions = computed<InvolvedRegion[]>(() => {
  if (!previewData.value) return []
  const regionMap = new Map<string, InvolvedRegionState>()
  for (const row of previewData.value.rows || []) {
    const current = regionMap.get(row.region_name)
    regionMap.set(row.region_name, { hasValid: true, hasInvalid: Boolean(current?.hasInvalid), hasPermissionError: false })
  }
  for (const row of previewData.value.error_rows || []) {
    if (!row.region_name) continue
    const current = regionMap.get(row.region_name) || { hasValid: false, hasInvalid: false, hasPermissionError: false }
    regionMap.set(row.region_name, {
      hasValid: current.hasValid,
      hasInvalid: row.error_type !== 'permission' || current.hasInvalid,
      hasPermissionError: row.error_type === 'permission' || current.hasPermissionError,
    })
  }
  return Array.from(regionMap.entries())
    .sort(([a], [b]) => a.localeCompare(b, 'zh-CN'))
    .map(([name, state]) => {
      if (state.hasPermissionError) return { name, label: '不可导入', tagType: 'danger' }
      if (state.hasInvalid && state.hasValid) return { name, label: '部分可导入', tagType: 'warning' }
      if (state.hasInvalid) return { name, label: '数据有误', tagType: 'warning' }
      return { name, label: '可导入', tagType: 'success' }
    })
})

function errorTypeMeta(errorType: ImportErrorType) {
  if (errorType === 'permission') return { label: '权限', tagType: 'danger' }
  if (errorType === 'business') return { label: '业务', tagType: 'warning' }
  return { label: '校验', tagType: 'danger' }
}

async function downloadTemplate() {
  downloading.value = true
  try {
    const blob = await downloadTemplateApi()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'dc_network_planner_import_template.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  } finally {
    downloading.value = false
  }
}

function onFileChange(uploadFile: UploadFile) {
  if (!canPreviewImport.value) return
  selectedFile.value = uploadFile.raw ?? null
  previewData.value = null
  importResult.value = null
  resultFilter.value = 'all'
}

async function previewUpload() {
  if (!selectedFile.value || !canPreviewImport.value) return
  previewLoading.value = true
  try {
    previewData.value = await previewImport(selectedFile.value)
  } finally {
    previewLoading.value = false
  }
}

async function confirmImport() {
  if (!previewData.value) return
  importing.value = true
  try {
    const result = await confirmImportApi(previewData.value.preview_id)
    importResult.value = result
    resultFilter.value = 'all'
    if (result.imported_count === 0 && result.error_count > 0) {
      ElMessage.warning('所有行导入失败')
    } else if (result.error_count > 0) {
      ElMessage.warning('部分行导入失败，请查看逐行结果')
    }
  } finally {
    importing.value = false
  }
}

function resetImport() {
  selectedFile.value = null
  previewData.value = null
  importResult.value = null
  resultFilter.value = 'all'
}

async function handleExport() {
  exporting.value = true
  try {
    const params: ExcelExportParams = {}
    if (exportForm.value.region_id) params.region_id = exportForm.value.region_id
    const blob = await exportExcel(params)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'dc_network_planner_export.xlsx'
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } finally {
    exporting.value = false
  }
}

onMounted(async () => {
  const regRes = await fetchRegions({ skip: 0, limit: 500 })
  regions.value = regRes.items || []
})
</script>

<style scoped>
.page-heading { margin-bottom: var(--spacing-lg); }
.page-title { font-size: var(--font-size-xl); font-weight: 700; color: var(--color-text-primary); margin: 0; }
.page-desc { font-size: var(--font-size-sm); color: var(--color-text-tertiary); margin-top: 4px; }

.permission-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  margin-bottom: 16px;
  background: var(--color-primary-lighter);
  border: 1px solid #d2e3fc;
  border-radius: 6px;
}

.permission-strip.is-warning {
  background: #fff7e0;
  border-color: #fde7a1;
}

.permission-main {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  font-weight: 600;
}

.permission-note {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.import-actions {
  display: grid;
  grid-template-columns: minmax(220px, 0.8fr) minmax(360px, 1.2fr);
  gap: 16px;
  margin-bottom: 18px;
}

.action-panel,
.export-panel,
.preview-panel {
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: #fff;
}

.action-panel {
  display: grid;
  grid-template-columns: 52px 1fr;
  min-height: 122px;
  overflow: hidden;
}

.action-index {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 18px;
  background: var(--color-border-light);
  color: var(--color-text-tertiary);
  font-size: var(--font-size-lg);
  font-weight: 700;
}

.action-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.action-title {
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  font-weight: 700;
}

.action-desc {
  margin: 4px 0 12px;
  color: var(--color-text-tertiary);
  font-size: var(--font-size-sm);
  line-height: 1.5;
}

.action-control {
  display: flex;
  align-items: center;
  min-height: 32px;
}

.template-button {
  --el-button-bg-color: #f8fafc;
  --el-button-border-color: #cfd8e3;
  --el-button-text-color: var(--color-primary-dark);
  --el-button-hover-bg-color: var(--color-primary-lighter);
  --el-button-hover-border-color: #b8c9e8;
  --el-button-hover-text-color: var(--color-primary-dark);
  font-weight: 600;
}

.upload-control {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 32px;
}

.choose-file-button {
  --el-button-bg-color: #fff;
  --el-button-border-color: #b8c9e8;
  --el-button-text-color: var(--color-primary-dark);
  --el-button-hover-bg-color: var(--color-primary-lighter);
  --el-button-hover-border-color: var(--color-primary);
  --el-button-hover-text-color: var(--color-primary-dark);
  font-weight: 600;
}

.upload-area {
  flex: 0 0 auto;
  padding: 0;
}

.upload-area :deep(.el-button) {
  flex: 0 0 auto;
}

.preview-button {
  margin-left: 0;
  min-width: 64px;
  font-weight: 600;
}

.preview-button.is-disabled,
.preview-button.is-disabled:hover {
  --el-button-disabled-bg-color: #edf1f5;
  --el-button-disabled-border-color: #d8dee6;
  --el-button-disabled-text-color: #8d98a7;
}

.upload-tip {
  color: var(--color-text-tertiary);
  font-size: 12px;
  margin-top: 4px;
}

.preview-panel {
  padding: 16px;
}

.result-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.result-title {
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  font-weight: 700;
}

.result-desc {
  margin: 4px 0 0;
  color: var(--color-text-tertiary);
  font-size: var(--font-size-sm);
}

.result-metrics {
  display: grid;
  grid-template-columns: repeat(3, 86px);
  gap: 8px;
}

.metric-item {
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-border-light);
}

.metric-item.is-success {
  background: #edf7ee;
  border-color: #d7ecd9;
}

.metric-item.is-danger {
  background: #fcefed;
  border-color: #f6d1cc;
}

.metric-value,
.metric-label {
  display: block;
}

.metric-value {
  color: var(--color-text-primary);
  font-size: 18px;
  font-weight: 700;
  line-height: 1.1;
}

.metric-label {
  margin-top: 2px;
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
}

.region-summary {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.region-summary-label {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.final-result-panel {
  padding-top: 18px;
  border-top: 1px solid var(--color-border);
}

.final-result-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.final-result-heading {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.final-result-icon {
  flex: 0 0 auto;
  margin-top: 1px;
  font-size: 24px;
}

.final-result-icon.is-success {
  color: var(--el-color-success);
}

.final-result-icon.is-warning {
  color: var(--el-color-warning);
}

.final-result-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 32px;
  margin: 16px 0 10px;
}

.final-result-table-title {
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
  font-weight: 600;
}

.final-result-table {
  width: 100%;
}

.result-cell-primary {
  color: var(--color-text-primary);
  line-height: 1.4;
}

.result-cell-secondary {
  margin-top: 2px;
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
  line-height: 1.3;
}

.row-result-message {
  line-height: 1.5;
}

.row-result-message.is-success {
  color: var(--el-color-success-dark-2);
  font-weight: 600;
}

.row-result-message.is-failed {
  color: var(--el-color-danger-dark-2);
}

.final-result-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.sub-title {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.export-panel {
  padding: 18px;
}

.export-copy {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 16px;
}

.export-form {
  display: grid;
  grid-template-columns: minmax(280px, 420px) auto;
  align-items: start;
  gap: 12px;
}

.export-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.export-form :deep(.el-select) {
  width: 100%;
}

.app-tabs :deep(.el-tabs__item) {
  font-size: var(--font-size-base);
  font-weight: 500;
}

@media (max-width: 900px) {
  .permission-strip,
  .result-header,
  .final-result-header {
    align-items: stretch;
    flex-direction: column;
  }

  .permission-note {
    white-space: normal;
  }

  .import-actions,
  .export-form {
    grid-template-columns: 1fr;
  }

  .result-metrics {
    grid-template-columns: repeat(3, 1fr);
  }

  .final-result-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
