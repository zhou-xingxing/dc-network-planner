<template>
  <div>
    <div class="page-heading">
      <div>
        <h2 class="page-title">备份配置</h2>
        <p class="page-desc">配置备份目标、定时任务，查看备份执行历史</p>
      </div>
      <el-button v-if="appStore.isAdministrator" type="primary" :loading="running" @click="handleRunBackup">
        <el-icon style="margin-right: 6px"><FolderChecked /></el-icon>立即备份
      </el-button>
    </div>

    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="120px"
      class="backup-form"
      v-loading="loading"
    >
      <el-card shadow="never" class="config-card">
        <template #header>
          <div class="card-header">
            <span>备份目标</span>
            <el-tag type="primary">{{ methodText(form.method) }}</el-tag>
          </div>
        </template>

        <el-form-item label="备份方式" prop="method">
          <el-radio-group v-model="form.method">
            <el-radio-button value="local">本地文件</el-radio-button>
            <el-radio-button value="object_storage">对象存储</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="文件名前缀" prop="backup_file_prefix">
          <el-input
            v-model="form.backup_file_prefix"
            placeholder="dc_network_planner_data_backup_"
            maxlength="50"
            show-word-limit
            clearable
            class="prefix-input"
          />
        </el-form-item>

        <el-form-item v-if="form.method === 'local'" label="本地路径" prop="local_path">
          <el-input v-model="form.local_path" placeholder="./backups" clearable />
        </el-form-item>

        <template v-else>
          <el-form-item label="Endpoint" prop="endpoint_url">
            <el-input v-model="form.endpoint_url" placeholder="https://obs.example.com" clearable />
          </el-form-item>
          <el-form-item label="AK" prop="access_key">
            <el-input v-model="form.access_key" placeholder="Access Key" clearable />
          </el-form-item>
          <el-form-item label="SK" prop="secret_key">
            <el-input
              v-model="form.secret_key"
              type="password"
              show-password
              :placeholder="secretConfigured ? '已配置，留空沿用原值' : 'Secret Key'"
              clearable
            />
          </el-form-item>
          <el-form-item label="Bucket" prop="bucket">
            <el-input v-model="form.bucket" placeholder="dc-network-planner-backup" clearable />
          </el-form-item>
          <el-form-item label="对象前缀">
            <el-input v-model="form.object_prefix" placeholder="dc-network-planner" clearable />
          </el-form-item>
        </template>
      </el-card>

      <el-card shadow="never" class="config-card">
        <template #header>
          <div class="card-header">
            <span>定时任务</span>
            <el-tag :type="form.enabled ? 'success' : 'info'">{{ form.enabled ? '已开启' : '未开启' }}</el-tag>
          </div>
        </template>

        <el-form-item label="启用任务">
          <el-switch v-model="form.enabled" active-text="开启" inactive-text="关闭" />
        </el-form-item>

        <el-form-item label="Cron 表达式" prop="cron_expression">
          <el-input
            v-model="form.cron_expression"
            placeholder="0 2 * * *"
            clearable
            class="cron-input"
          />
          <div class="form-tip">五段式：分 时 日 月 周，秒固定为 0</div>
        </el-form-item>

        <el-form-item label="下次执行">
          <span class="readonly-text">{{ form.enabled ? formatDate(config?.next_run_at) : '未启用' }}</span>
        </el-form-item>
      </el-card>

      <div v-if="appStore.isAdministrator" class="form-actions">
        <el-button type="primary" :loading="saving" @click="handleSave">
          <el-icon style="margin-right: 6px"><Check /></el-icon>保存配置
        </el-button>
        <el-button @click="loadConfig">刷新</el-button>
      </div>
    </el-form>

    <el-card shadow="never" class="history-card">
      <template #header>
        <div class="card-header">
          <span>备份历史</span>
          <el-button :icon="Refresh" text @click="loadRecords" />
        </div>
      </template>

      <el-table :data="records" stripe border v-loading="recordsLoading">
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="method" label="方式" width="120">
          <template #default="{ row }">{{ methodText(row.method) }}</template>
        </el-table-column>
        <el-table-column prop="target" label="目标" min-width="260" show-overflow-tooltip />
        <el-table-column prop="file_size" label="大小" width="120">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column prop="operator" label="操作者" width="130" />
        <el-table-column prop="started_at" label="开始时间" width="180">
          <template #default="{ row }">{{ formatDate(row.started_at) }}</template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误" min-width="200" show-overflow-tooltip />
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadRecords"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { fetchBackupConfig, fetchBackupRecords, runBackup, updateBackupConfig } from '@/api/backup'
import { useAppStore } from '@/stores/app'
import { Check, FolderChecked, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { formatDateTime } from '@/utils/time'
import { computed, onMounted, reactive, ref } from 'vue'
import type { BackupConfig, BackupConfigUpdatePayload, BackupMethod, BackupRecord } from '@/types'

const loading = ref(false)
const appStore = useAppStore()
const BACKUP_FILE_PREFIX_MAX_LENGTH = 50
const saving = ref(false)
const running = ref(false)
const recordsLoading = ref(false)
const config = ref<BackupConfig | null>(null)
const secretConfigured = ref(false)
const formRef = ref<FormInstance>()
const records = ref<BackupRecord[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)

const form = reactive<BackupConfigUpdatePayload>({
  enabled: false,
  cron_expression: '0 2 * * *',
  backup_file_prefix: 'dc_network_planner_data_backup_',
  method: 'local',
  local_path: './backups',
  endpoint_url: '',
  access_key: '',
  secret_key: '',
  bucket: '',
  object_prefix: '',
})

const rules = computed(() => ({
  cron_expression: [
    { required: true, message: '请输入 Cron 表达式', trigger: 'blur' },
    {
      pattern: /^(\S+\s+){4}\S+$/,
      message: '请输入五段式 Cron 表达式',
      trigger: 'blur',
    },
  ],
  backup_file_prefix: [
    { required: true, message: '请输入备份文件名前缀', trigger: 'blur' },
    {
      max: BACKUP_FILE_PREFIX_MAX_LENGTH,
      message: `文件名前缀不能超过 ${BACKUP_FILE_PREFIX_MAX_LENGTH} 个字符`,
      trigger: 'blur',
    },
    {
      pattern: /^[^/\\]+$/,
      message: '文件名前缀不能包含路径分隔符',
      trigger: 'blur',
    },
  ],
  method: [{ required: true, message: '请选择备份方式', trigger: 'change' }],
  local_path: form.method === 'local' ? [{ required: true, message: '请输入本地路径', trigger: 'blur' }] : [],
  endpoint_url: form.method === 'object_storage' ? [{ required: true, message: '请输入 Endpoint', trigger: 'blur' }] : [],
  access_key: form.method === 'object_storage' ? [{ required: true, message: '请输入 AK', trigger: 'blur' }] : [],
  secret_key: form.method === 'object_storage' && !secretConfigured.value
    ? [{ required: true, message: '请输入 SK', trigger: 'blur' }]
    : [],
  bucket: form.method === 'object_storage' ? [{ required: true, message: '请输入 Bucket', trigger: 'blur' }] : [],
}))

function applyConfig(data: BackupConfig) {
  config.value = data
  secretConfigured.value = data.secret_key_configured
  form.enabled = data.enabled
  form.cron_expression = data.cron_expression || '0 2 * * *'
  form.backup_file_prefix = data.backup_file_prefix || 'dc_network_planner_data_backup_'
  form.method = data.method
  form.local_path = data.local_path || './backups'
  form.endpoint_url = data.endpoint_url || ''
  form.access_key = data.access_key || ''
  form.secret_key = ''
  form.bucket = data.bucket || ''
  form.object_prefix = data.object_prefix || ''
}

async function loadConfig() {
  loading.value = true
  try {
    applyConfig(await fetchBackupConfig())
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  await formRef.value?.validate()
  saving.value = true
  try {
    const payload: BackupConfigUpdatePayload = { ...form }
    payload.cron_expression = payload.cron_expression.trim()
    payload.backup_file_prefix = payload.backup_file_prefix.trim()
    if (payload.method === 'local') {
      payload.endpoint_url = ''
      payload.access_key = ''
      payload.secret_key = ''
      payload.bucket = ''
      payload.object_prefix = ''
    }
    applyConfig(await updateBackupConfig(payload))
    ElMessage.success('备份配置已保存')
  } finally {
    saving.value = false
  }
}

async function handleRunBackup() {
  running.value = true
  try {
    const result = await runBackup()
    if (result.status === 'success') {
      ElMessage.success('备份完成')
    } else {
      ElMessage.warning('备份未成功，请查看历史记录')
    }
    await Promise.all([loadConfig(), loadRecords()])
  } finally {
    running.value = false
  }
}

async function loadRecords() {
  recordsLoading.value = true
  try {
    const res = await fetchBackupRecords({
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
    })
    records.value = res.items || []
    total.value = res.total || 0
  } finally {
    recordsLoading.value = false
  }
}

function formatDate(value?: string | null) {
  return formatDateTime(value)
}

function formatSize(value?: number | null) {
  if (!value) return '-'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function methodText(value: BackupMethod | string) {
  return value === 'object_storage' ? '对象存储' : '本地文件'
}

function statusText(value: string) {
  if (value === 'success') return '成功'
  if (value === 'failed') return '失败'
  return '执行中'
}

onMounted(async () => {
  await Promise.all([loadConfig(), loadRecords()])
})
</script>

<style scoped>
.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
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

.config-card,
.history-card {
  margin-bottom: var(--spacing-lg);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.backup-form {
  width: 100%;
}

.readonly-text {
  color: var(--color-text-secondary);
}

.cron-input {
  max-width: 360px;
}

.prefix-input {
  max-width: 360px;
}

.form-tip {
  width: 100%;
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  line-height: 1.5;
  margin-top: 4px;
}

.form-actions {
  display: flex;
  gap: var(--spacing-sm);
  margin: 0 0 var(--spacing-lg) 120px;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--spacing-md);
}
</style>
