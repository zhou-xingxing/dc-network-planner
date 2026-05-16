<template>
  <div>
    <div class="page-heading">
      <div>
        <h2 class="page-title">导入 / 导出</h2>
        <p class="page-desc">通过 Excel 批量导入 Region 网络平面数据，或按条件导出为 Excel</p>
      </div>
    </div>

    <el-card shadow="never">
      <el-tabs v-model="activeTab" class="app-tabs">
        <el-tab-pane label="导入 Excel" name="import">
          <!-- 步骤 1：下载模板 -->
          <div class="step-section">
            <div class="step-label">
              <el-tag size="small" type="primary" round>步骤 1</el-tag>
              <span>下载模板</span>
            </div>
            <p class="step-desc">请先下载模板，按照模板格式填写数据后上传。</p>
            <el-button type="primary" plain @click="downloadTemplate" :loading="downloading">
              <el-icon style="margin-right: 6px"><Download /></el-icon>下载导入模板
            </el-button>
          </div>

          <el-divider />

          <!-- 步骤 2：上传文件 -->
          <div class="step-section">
            <div class="step-label">
              <el-tag size="small" type="primary" round>步骤 2</el-tag>
              <span>上传文件</span>
            </div>
            <p class="step-desc">选择填写好的 Excel 文件进行预览。</p>
            <el-upload
              ref="uploadRef"
              action="#"
              :auto-upload="false"
              :show-file-list="true"
              :limit="1"
              accept=".xlsx"
              :on-change="onFileChange"
              class="upload-area"
            >
              <template #trigger>
                <el-button type="primary">
                  <el-icon style="margin-right: 6px"><Upload /></el-icon>选择文件
                </el-button>
              </template>
              <el-button style="margin-left: 10px" type="success" @click="previewUpload" :loading="previewLoading" :disabled="!selectedFile">
                预览
              </el-button>
              <template #tip>
                <div class="upload-tip">仅支持 .xlsx 文件</div>
              </template>
            </el-upload>
          </div>

          <!-- 预览结果 -->
          <div v-if="previewData" class="step-section">
            <div class="step-label">
              <el-tag size="small" type="primary" round>步骤 3</el-tag>
              <span>确认导入</span>
            </div>
            <el-alert
              :title="`共 ${previewData.total_rows} 行，有效 ${previewData.valid_rows} 行，错误 ${previewData.error_rows.length} 行`"
              :type="previewData.error_rows.length > 0 ? 'warning' : 'success'"
              show-icon
              style="margin-bottom: 16px"
              :closable="false"
            />
            <div v-if="previewData.error_rows.length > 0" style="margin-bottom: 16px">
              <h4 class="sub-title">错误详情：</h4>
              <el-table :data="previewData.error_rows" stripe border size="small">
                <el-table-column prop="row" label="行号" width="80" />
                <el-table-column prop="errors" label="错误" min-width="300">
                  <template #default="{ row }">
                    <el-tag v-for="err in row.errors" :key="err" type="danger" size="small" style="margin: 2px">{{ err }}</el-tag>
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
            <el-button
              type="success"
              size="large"
              @click="confirmImport"
              :loading="importing"
              :disabled="previewData.valid_rows === 0 || !canImport"
            >
              确认导入 ({{ previewData.valid_rows }} 条)
            </el-button>
          </div>

          <!-- 导入结果 -->
          <el-result v-if="importResult" icon="success" :title="`导入完成`" :sub-title="`成功 ${importResult.imported_count} 条，失败 ${importResult.error_count} 条`">
            <template #extra>
              <el-button type="primary" @click="resetImport">继续导入</el-button>
            </template>
          </el-result>
        </el-tab-pane>

        <el-tab-pane label="导出 Excel" name="export">
          <div class="step-section">
            <div class="step-label">
              <el-tag size="small" type="success" round>导出</el-tag>
              <span>选择过滤条件</span>
            </div>
            <p class="step-desc">按 Region 和网络平面过滤要导出的数据，留空则导出全部。</p>
            <el-form :model="exportForm" label-width="100px" class="export-form">
              <el-form-item label="Region">
                <el-select v-model="exportForm.region_id" placeholder="全部 Region" clearable style="width: 300px">
                  <el-option v-for="r in regions" :key="r.id" :label="r.name" :value="r.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="网络平面">
                <el-select v-model="exportForm.plane_type_id" placeholder="全部平面" clearable style="width: 300px">
                  <el-option v-for="pt in planeTypes" :key="pt.id" :label="pt.name" :value="pt.id" />
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

<script setup>
import { computed, ref, onMounted } from 'vue'
import { downloadTemplate as downloadTemplateApi, previewImport, confirmImport as confirmImportApi, exportExcel } from '@/api/excel'
import { fetchRegions } from '@/api/regions'
import { fetchPlaneTypes } from '@/api/networkPlaneTypes'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'
import { Download, Upload } from '@element-plus/icons-vue'

const appStore = useAppStore()
const canImport = computed(
  () => appStore.currentUser?.role === 'user' && (appStore.currentUser?.permitted_regions || []).length > 0
)
const activeTab = ref('import')

const downloading = ref(false)
const selectedFile = ref(null)
const previewLoading = ref(false)
const previewData = ref(null)
const importing = ref(false)
const importResult = ref(null)
const uploadRef = ref(null)

const regions = ref([])
const planeTypes = ref([])
const exporting = ref(false)
const exportForm = ref({ region_id: '', plane_type_id: '' })

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

function onFileChange(uploadFile) {
  selectedFile.value = uploadFile.raw
  previewData.value = null
  importResult.value = null
}

async function previewUpload() {
  if (!selectedFile.value) return
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
    importResult.value = await confirmImportApi(previewData.value.preview_id)
    if (importResult.value.imported_count === 0 && importResult.value.error_count > 0) {
      ElMessage.warning('所有行导入失败')
    }
  } finally {
    importing.value = false
  }
}

function resetImport() {
  selectedFile.value = null
  previewData.value = null
  importResult.value = null
}

async function handleExport() {
  exporting.value = true
  try {
    const params = {}
    if (exportForm.value.region_id) params.region_id = exportForm.value.region_id
    if (exportForm.value.plane_type_id) params.plane_type_id = exportForm.value.plane_type_id
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
  const ptRes = await fetchPlaneTypes({ skip: 0, limit: 500 })
  planeTypes.value = ptRes.items || []
})
</script>

<style scoped>
.page-heading { margin-bottom: var(--spacing-lg); }
.page-title { font-size: var(--font-size-xl); font-weight: 700; color: var(--color-text-primary); margin: 0; }
.page-desc { font-size: var(--font-size-sm); color: var(--color-text-tertiary); margin-top: 4px; }

.step-section { padding: 4px 0; }

.step-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-weight: 600;
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
}

.step-desc {
  color: var(--color-text-tertiary);
  margin-bottom: 12px;
  font-size: var(--font-size-sm);
}

.upload-area {
  padding: 8px 0;
}

.upload-tip {
  color: var(--color-text-tertiary);
  font-size: 12px;
  margin-top: 4px;
}

.sub-title {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.export-form {
  margin-top: 8px;
}

.app-tabs :deep(.el-tabs__item) {
  font-size: var(--font-size-base);
  font-weight: 500;
}
</style>
