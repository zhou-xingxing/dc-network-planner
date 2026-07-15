<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>外部 API 访问令牌</h2>
        <p>查看当前未撤销、未过期的访问令牌，并在必要时立即撤销</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadTokens">刷新</el-button>
    </div>

    <div class="security-note">
      <el-icon><InfoFilled /></el-icon>
      <span>仅显示未撤销、未过期的令牌；所属用户已停用的令牌会保留展示，便于管理员手动撤销。系统不会展示原始 Token 或哈希。</span>
      <strong>{{ tokens.length }} 个当前令牌</strong>
    </div>

    <el-card class="token-card" shadow="never">
      <div class="table-scroll">
        <el-table
          :data="tokens"
          stripe
          border
          v-loading="loading"
          style="width: 100%; min-width: 1110px"
          empty-text="当前没有未撤销、未过期的外部 API 访问令牌"
        >
          <el-table-column label="令牌标识" width="320" resizable>
            <template #default="{ row }">
              <code class="token-id">{{ row.id }}</code>
            </template>
          </el-table-column>
          <el-table-column prop="username" label="所属用户" width="130" resizable />
          <el-table-column label="签发时间" width="210" resizable>
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="过期时间" width="210" resizable>
            <template #default="{ row }">{{ formatDateTime(row.expires_at) }}</template>
          </el-table-column>
          <el-table-column label="所属用户状态" width="130" resizable>
            <template #default="{ row }">
              <el-tag :type="row.owner_is_active ? 'success' : 'info'" effect="plain">
                {{ row.owner_is_active ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right" resizable>
            <template #default="{ row }">
              <el-button size="small" type="danger" @click="handleRevoke(row)">撤销</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { InfoFilled, Refresh } from '@element-plus/icons-vue'
import { fetchExternalAccessTokens, revokeExternalAccessToken } from '@/api/externalAccessTokens'
import type { ExternalAccessToken } from '@/types'
import { formatDateTime } from '@/utils/time'

const tokens = ref<ExternalAccessToken[]>([])
const loading = ref(false)

onMounted(loadTokens)

async function loadTokens() {
  loading.value = true
  try {
    const data = await fetchExternalAccessTokens({ limit: 500 })
    tokens.value = data.items
  } finally {
    loading.value = false
  }
}

async function handleRevoke(token: ExternalAccessToken) {
  await ElMessageBox.confirm(
    `确定撤销用户 ${token.username} 的访问令牌？撤销后将立即失效，且无法恢复。`,
    '确认撤销访问令牌',
    { confirmButtonText: '确认撤销', cancelButtonText: '取消', type: 'warning' },
  )
  await revokeExternalAccessToken(token.id)
  ElMessage.success('访问令牌已撤销')
  await loadTokens()
}
</script>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-header h2 {
  margin: 0;
}

.page-header p {
  margin: 6px 0 0;
  color: var(--color-text-secondary);
}

.security-note {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 11px 14px;
  border: 1px solid color-mix(in srgb, var(--el-color-warning) 28%, transparent);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--el-color-warning-light-9) 72%, transparent);
  color: var(--color-text-secondary);
  font-size: 13px;
}

.security-note > :first-child {
  color: var(--el-color-warning);
  flex: 0 0 auto;
}

.security-note strong {
  margin-left: auto;
  color: var(--color-text-primary);
  font-weight: 600;
  white-space: nowrap;
}

.token-card :deep(.el-card__body) {
  padding: 4px 18px;
}

.table-scroll {
  overflow-x: auto;
}

.token-id {
  padding: 3px 7px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
  color: var(--el-color-primary-dark-2);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}

@media (max-width: 720px) {
  .page-header,
  .security-note {
    align-items: flex-start;
  }

  .page-header {
    gap: 12px;
  }

  .security-note {
    flex-wrap: wrap;
  }

  .security-note strong {
    width: 100%;
    margin-left: 0;
  }
}
</style>
